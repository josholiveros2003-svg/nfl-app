"""
The betting market's view of each team (fills the "analyst opinion" slot for teams).

Every game's point spread and over/under total say how many points the market expects
each team to score: home = (total + spread) / 2, away = (total - spread) / 2. From all
of this season's lines (including upcoming games, which are the market's current view,
and with recent weeks counting more) we work out, for each team:
  - offense: points it scores beyond an average team, and
  - defense: points it holds opponents below average,
then put those on the 0-100 team-rating scale (average 77).

Betting lines are effectively the combined opinion of the sharpest analysts with money
on it, which is why they predict games better than any single expert.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

SETTINGS = json.loads((Path(__file__).resolve().parent.parent / "config" / "winprob.json").read_text())["market"]


def market_strengths(sched, team_ids, scale_mean: float, scale_sd: float):
    """{team: {"offense", "defense", "overall" (0-100 ratings), "pointsFor", "pointsAgainst", "margin"}}
    or {} if no lines are available yet."""
    lines = sched[sched.spread_line.notna() & sched.total_line.notna()]
    if lines.empty:
        return {}
    idx = {t: i for i, t in enumerate(team_ids)}
    n = len(team_ids)
    latest = int(lines.week.max())
    rows, ys, ws = [], [], []
    for g in lines.itertuples():
        home_pts = (g.total_line + g.spread_line) / 2
        away_pts = (g.total_line - g.spread_line) / 2
        w = SETTINGS["recencyDecay"] ** (latest - int(g.week))
        neutral = 0.0 if g.location == "Neutral" else 1.0
        # columns: offense (n), defense (n), league average, home edge
        for team, opp, pts, home in ((g.home_team, g.away_team, home_pts, neutral), (g.away_team, g.home_team, away_pts, -neutral)):
            x = np.zeros(2 * n + 2)
            x[idx[team]] = 1.0          # my offense adds points
            x[n + idx[opp]] = -1.0      # their defense takes points away
            x[2 * n] = 1.0              # league average
            x[2 * n + 1] = home / 2     # half the home edge goes to each side's score
            rows.append(x)
            ys.append(pts)
            ws.append(w)
    X, y, w = np.array(rows), np.array(ys), np.sqrt(np.array(ws))
    lam = SETTINGS["ridge"]
    A = (X * w[:, None]).T @ (X * w[:, None]) + lam * np.diag([1.0] * (2 * n) + [0.0, 0.0])
    beta = np.linalg.solve(A, (X * w[:, None]).T @ (y * w))
    off, dfn = beta[:n], beta[n:2 * n]
    margin = off + dfn

    def to_scale(v):
        mu, sd = float(v.mean()), float(v.std()) or 1.0
        return {t: round(scale_mean + scale_sd * (float(v[i]) - mu) / sd, 1) for t, i in idx.items()}

    o_r, d_r, m_r = to_scale(off), to_scale(dfn), to_scale(margin)
    return {t: {"offense": o_r[t], "defense": d_r[t], "overall": m_r[t],
                "pointsFor": round(float(off[i]), 1), "pointsAgainst": round(float(dfn[i]), 1),
                "margin": round(float(margin[i]), 1)}
            for t, i in idx.items()}


def describe(m: dict, unit: str) -> str:
    if unit == "offense":
        return (f"The betting market rates this offense {m['offense']:.0f}: it expects them to score "
                f"{abs(m['pointsFor']):.1f} points {'more' if m['pointsFor'] >= 0 else 'fewer'} than an average offense.")
    if unit == "defense":
        return (f"The betting market rates this defense {m['defense']:.0f}: it expects them to allow "
                f"{abs(m['pointsAgainst']):.1f} points {'fewer' if m['pointsAgainst'] >= 0 else 'more'} than an average defense.")
    return (f"The betting market rates this team {m['overall']:.0f}: about {abs(m['margin']):.1f} points "
            f"{'better' if m['margin'] >= 0 else 'worse'} than an average team on a neutral field, from this "
            f"season's point spreads and totals (recent weeks count most).")


def blend(model_margin: float, spread: float | None, weight: float) -> float:
    """Final expected home margin: the model's, pulled toward the betting line."""
    if spread is None or (isinstance(spread, float) and math.isnan(spread)):
        return model_margin
    return (1 - weight) * model_margin + weight * spread
