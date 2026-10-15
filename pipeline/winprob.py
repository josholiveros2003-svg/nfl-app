"""
Win probability for any game (settings: config/winprob.json).

Everything is measured in points on the scoreboard, then turned into a percentage:

  expected home margin = home field
                       + points per rating point x (home rating - away rating), for
                         Offense, Defense and Special Teams separately
                       + recent form   x (home - away average margin, last 3 games)
                       + record weight x (home - away schedule-adjusted margin)
                       - injury weight x (home injury points - away injury points)

  home win chance = how often a game with that expected margin is won, given that NFL
                    results vary around the expectation by about 13-14 points
                    (a normal / bell curve).

Only information available before kickoff is used: team ratings rebuilt from earlier
games, results before that week, and that week's injury report. That's what makes it
fair to test on past games.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

SETTINGS = json.loads((Path(__file__).resolve().parent.parent / "config" / "winprob.json").read_text())

FEATURES = ["home", "offense", "defense", "special", "form", "adjusted", "lastSeason", "injuries"]
LABELS = {
    "home": "Home field",
    "offense": "Offense rating",
    "defense": "Defense rating",
    "special": "Special teams rating",
    "form": "Recent form",
    "adjusted": "Record & schedule",
    "lastSeason": "Last season",
    "injuries": "Injuries",
}


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# --------------------------------------------------------------------------
# Results before a given week: recent form + schedule-adjusted margin
# --------------------------------------------------------------------------

def team_results(sched) -> dict:
    """{team: [(week, margin, opponent)]} for played games, sorted by week."""
    out = {}
    for g in sched[sched.result.notna()].itertuples():
        out.setdefault(g.home_team, []).append((int(g.week), float(g.result), g.away_team))
        out.setdefault(g.away_team, []).append((int(g.week), -float(g.result), g.home_team))
    return {t: sorted(v) for t, v in out.items()}


def form_and_adjusted(results: dict, team: str, week: int, shrink: bool = True):
    """Recent form = average margin over the last few games before `week`.
    Schedule-adjusted margin = average margin + how good the opponents have been (their average
    margin), which rewards winning against good teams and discounts beating bad ones."""
    n = SETTINGS["recentGames"]
    before = [r for r in results.get(team, []) if r[0] < week]
    if not before:
        return 0.0, 0.0, 0
    form = sum(m for _, m, _ in before[-n:]) / len(before[-n:])
    avg = sum(m for _, m, _ in before) / len(before)
    opp_avgs = []
    for _, _, opp in before:
        ob = [m for w, m, _ in results.get(opp, []) if w < week]
        opp_avgs.append(sum(ob) / len(ob) if ob else 0.0)
    adjusted = avg + sum(opp_avgs) / len(opp_avgs)
    # Early in the season a few games say little, so shrink toward 0 (see settings).
    k = len(before) / (len(before) + SETTINGS["resultsHalfWeightGames"]) if shrink else 1.0
    return form * k, adjusted * k, len(before)


def last_season_margins(prev_sched) -> dict:
    """Each team's schedule-adjusted margin over all of last season (the 'Last season' factor)."""
    res = team_results(prev_sched)
    return {t: form_and_adjusted(res, t, 99, shrink=False)[1] for t in res}


def last_season_weight(games_played: int) -> float:
    """Last season counts fully in Week 1 and fades as this season's games come in."""
    return 1.0 / (1.0 + games_played / SETTINGS["lastSeasonFadeGames"])


# --------------------------------------------------------------------------
# Injuries
# --------------------------------------------------------------------------

def player_importance(group: str | None, madden: float | None, starter: bool) -> float:
    """How many points a team loses without this player (see settings)."""
    inj = SETTINGS["injuries"]
    base = inj["positionPoints"].get(group or "", 0.0)
    if madden is None:
        quality = inj["unknownQuality"]
    else:
        quality = (madden - inj["qualityFloor"]) / inj["qualityScale"]
        quality = max(inj["minQuality"], min(inj["maxQuality"], quality))
    return base * quality * (1.0 if starter else inj["nonStarterShare"])


def injuries_for(team: str, week: int, out_by_week: dict, info: dict) -> list:
    """Players missing for `team` in `week`: [{name, pos, status, points}] sorted by impact."""
    inj = SETTINGS["injuries"]
    rows = []
    for pid, status in out_by_week.get((team, week), {}).items():
        p = info.get(pid)
        if not p:
            continue
        pts = player_importance(p["group"], p["madden"], p["starter"]) * inj["statusWeight"].get(status, 0)
        if pts >= inj["minPointsToShow"]:
            rows.append({"id": pid, "name": p["name"], "pos": p["pos"], "status": status, "points": round(pts, 2)})
    return sorted(rows, key=lambda r: -r["points"])


def unavailable_by_week(injuries, weekly_rosters) -> dict:
    """{(team, week): {player id: status}} from injury reports (Out/Doubtful) and injured reserve."""
    out = {}
    res = weekly_rosters[weekly_rosters.status == "RES"]
    for r in res.itertuples():
        if isinstance(r.gsis_id, str):
            out.setdefault((r.team, int(r.week)), {})[r.gsis_id] = "IR"
    rep = injuries[injuries.report_status.isin(["Out", "Doubtful"])]
    for r in rep.itertuples():
        if isinstance(r.gsis_id, str):
            out.setdefault((r.team, int(r.week)), {})[r.gsis_id] = r.report_status
    return out


# --------------------------------------------------------------------------
# One game
# --------------------------------------------------------------------------

def game_features(home: str, away: str, week: int, neutral: bool, ratings: dict, results: dict,
                  out_by_week: dict, info: dict, prior: dict) -> tuple[dict, dict]:
    """Feature differences (home minus away, so positive favors the home team) + details."""
    rh, ra = ratings[home], ratings[away]
    fh, adj_h, gh = form_and_adjusted(results, home, week)
    fa, adj_a, ga = form_and_adjusted(results, away, week)
    inj_h = injuries_for(home, week, out_by_week, info)
    inj_a = injuries_for(away, week, out_by_week, info)
    ih = sum(r["points"] for r in inj_h)
    ia = sum(r["points"] for r in inj_a)
    lh = prior.get(home, 0.0) * last_season_weight(gh)
    la = prior.get(away, 0.0) * last_season_weight(ga)
    feats = {
        "home": 0.0 if neutral else 1.0,
        "offense": rh["offense"] - ra["offense"],
        "defense": rh["defense"] - ra["defense"],
        "special": rh["special"] - ra["special"],
        "form": fh - fa,
        "adjusted": adj_h - adj_a,
        "lastSeason": lh - la,
        "injuries": ia - ih,  # the away team missing more helps the home team
    }
    details = {
        "ratings": {"home": rh, "away": ra},
        "form": {"home": round(fh, 1), "away": round(fa, 1)},
        "adjusted": {"home": round(adj_h, 1), "away": round(adj_a, 1)},
        "lastSeason": {"home": round(lh, 1), "away": round(la, 1)},
        "games": {"home": gh, "away": ga},
        "injuries": {"home": inj_h, "away": inj_a, "homePoints": round(ih, 2), "awayPoints": round(ia, 2)},
    }
    return feats, details


def predict(feats: dict, weights: dict | None = None, sigma: float | None = None):
    """Expected home margin, home win probability, and each factor's contribution (points)."""
    w = weights or SETTINGS["weights"]
    sd = sigma or SETTINGS["marginSD"]
    contrib = {f: w[f] * feats[f] for f in FEATURES}
    margin = sum(contrib.values())
    return margin, phi(margin / sd), contrib


# --------------------------------------------------------------------------
# Testing against real results
# --------------------------------------------------------------------------

def fit(rows: list) -> tuple[dict, float]:
    """Least-squares fit of actual home margins on the features (lightly regularized)."""
    X = np.array([[r["feats"][f] for f in FEATURES] for r in rows], dtype=float)
    y = np.array([r["margin"] for r in rows], dtype=float)
    lam = SETTINGS["fitting"]["ridge"]
    scale = X.std(axis=0)
    scale[scale == 0] = 1
    Xs = X / scale
    A = Xs.T @ Xs + lam * np.eye(len(FEATURES))
    beta = np.linalg.solve(A, Xs.T @ y) / scale
    resid = y - X @ beta
    return {f: float(b) for f, b in zip(FEATURES, beta)}, float(resid.std())


def evaluate(rows: list, probs: list) -> dict:
    """How often the favorite won, calibration by confidence band, and Brier score."""
    picks = [(p, r["margin"]) for p, r in zip(probs, rows) if r["margin"] != 0]
    correct = sum((p > 0.5) == (m > 0) for p, m in picks)
    brier = sum((p - (1.0 if m > 0 else 0.0)) ** 2 for p, m in picks) / len(picks)
    bands = []
    for lo, hi in [(50, 60), (60, 70), (70, 80), (80, 101)]:
        sel = [(max(p, 1 - p), (p > 0.5) == (m > 0)) for p, m in picks if lo <= max(p, 1 - p) * 100 < hi]
        if sel:
            bands.append({"band": f"{lo}-{min(hi, 100)}%", "games": len(sel),
                          "predicted": round(100 * sum(x for x, _ in sel) / len(sel), 1),
                          "actual": round(100 * sum(1 for _, ok in sel if ok) / len(sel), 1)})
    return {"games": len(picks), "correct": correct, "accuracy": round(100 * correct / len(picks), 1),
            "brier": round(brier, 4), "calibration": bands}


def backtest(rows: list) -> dict:
    """Honest testing: each week's games are predicted by a model fitted on all *other* weeks
    (leave-one-week-out), so no game is predicted by a model that saw its result."""
    played = [r for r in rows if r["margin"] is not None]
    weeks = sorted({(r["season"], r["week"]) for r in played})
    margins = {}
    for sw in weeks:
        train = [r for r in played if (r["season"], r["week"]) != sw]
        w, _ = fit(train)
        for r in played:
            if (r["season"], r["week"]) == sw:
                margins[r["id"]] = predict(r["feats"], w, 1.0)[0]
    # Blend in the betting line (the "analyst opinion" factor): find the share that works best on
    # held-out games, together with the margin-to-percentage spread.
    best, curve = None, {}
    for share in np.arange(0.0, 1.0001, 0.05):
        pairs = [((1 - share) * margins[r["id"]] + share * (r["spread"] if r.get("spread") is not None else margins[r["id"]]),
                  r["margin"]) for r in played]
        sigma = best_sigma(pairs)
        loss = log_loss(pairs, sigma)
        picks = [(phi(m / sigma), a) for m, a in pairs if a != 0]
        curve[f"{share:.2f}"] = {"accuracy": round(100 * sum((p > 0.5) == (a > 0) for p, a in picks) / len(picks), 1),
                                 "brier": round(sum((p - (a > 0)) ** 2 for p, a in picks) / len(picks), 4)}
        if best is None or loss < best[0]:
            best = (loss, float(share), sigma)
    _, market_share, sigma = best
    blended = {r["id"]: (1 - market_share) * margins[r["id"]] +
               market_share * (r["spread"] if r.get("spread") is not None else margins[r["id"]]) for r in played}
    probs = {k: phi(m / sigma) for k, m in blended.items()}
    model_only_sigma = best_sigma([(margins[r["id"]], r["margin"]) for r in played])
    model_only = {k: phi(m / model_only_sigma) for k, m in margins.items()}
    out = {}
    for label, sel in [("all", played)] + [(str(s), [r for r in played if r["season"] == s])
                                            for s in sorted({r["season"] for r in played})]:
        out[label] = {
            "model": evaluate(sel, [probs[r["id"]] for r in sel]),
            "modelWithoutMarket": evaluate(sel, [model_only[r["id"]] for r in sel]),
            "homeTeam": evaluate(sel, [0.57 for _ in sel]),
            "vegas": evaluate([r for r in sel if r.get("spread") is not None],
                              [phi(r["spread"] / SETTINGS["marginSD"]) for r in sel if r.get("spread") is not None]),
        }
    fitted, sd = fit(played)
    out["fittedWeights"] = {k: round(v, 3) for k, v in fitted.items()}
    out["fittedMarginSD"] = round(sd, 2)
    out["calibratedMarginSD"] = sigma
    out["fittedMarketWeight"] = round(market_share, 2)
    # The spread that goes with the blend actually used (config/winprob.json -> market.weight).
    used = SETTINGS["market"]["weight"]
    out["marginSDForMarketWeight"] = best_sigma([((1 - used) * margins[r["id"]] + used * (
        r["spread"] if r.get("spread") is not None else margins[r["id"]]), r["margin"]) for r in played])
    out["marketBlendCurve"] = curve
    return out


def log_loss(pairs, sigma) -> float:
    loss = 0.0
    for m, actual in pairs:
        if actual == 0:
            continue
        p = min(max(phi(m / sigma), 1e-6), 1 - 1e-6)
        loss -= math.log(p if actual > 0 else 1 - p)
    return loss


def best_sigma(pairs) -> float:
    """The margin-to-percentage spread with the lowest log loss on held-out games."""
    best, best_loss = 13.5, float("inf")
    for sigma in np.arange(9.0, 22.01, 0.25):
        loss = 0.0
        for m, actual in pairs:
            if actual == 0:
                continue
            p = min(max(phi(m / sigma), 1e-6), 1 - 1e-6)
            loss -= math.log(p if actual > 0 else 1 - p)
        if loss < best_loss:
            best, best_loss = float(sigma), loss
    return best
