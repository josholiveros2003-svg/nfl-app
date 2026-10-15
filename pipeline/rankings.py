"""
Power rankings (settings: config/rankings.json).

League power rankings blend three parts, each compared across all 32 teams:
  - Results: every game scored (half win/loss, half capped margin) against what an AVERAGE
    team would be expected to do in that exact spot (that opponent, home or away, that
    opponent's injuries). Averaged per game, so byes don't matter, and shrunk toward the
    middle for teams with few games.
  - Team rating: the 0-100 team rating, lowered for key players out right now.
  - Recent form: the last few games' results, most recent counting most.
The app blends them with the Settings sliders; this module provides the pieces for this
week and for last week (so the app can show how far each team moved).

Team-unit rankings (Offense, Offensive Line, ...) reuse the ratings we already have.
"""

from __future__ import annotations

import json
from pathlib import Path

from ratings import SETTINGS as RATINGS, combine, weights_for
from winprob import SETTINGS as WP, injuries_for, phi, predict

SETTINGS = json.loads((Path(__file__).resolve().parent.parent / "config" / "rankings.json").read_text())


# --------------------------------------------------------------------------
# League power rankings
# --------------------------------------------------------------------------

def average_team_chance(row: dict, team: str) -> float:
    """Chance an average team would have had in `team`'s spot in this game."""
    d = row["details"]
    home = row["home"] == team
    me, opp = ("home", "away") if home else ("away", "home")
    avg = RATINGS["madden"]["teamBaseline"]["mean"]
    ro = d["ratings"][opp]
    # Feature differences from the home team's point of view, with an average team in our seat.
    sign = 1 if home else -1
    feats = {
        "home": 0.0 if row["neutral"] else 1.0,
        "offense": sign * (avg - ro["offense"]),
        "defense": sign * (avg - ro["defense"]),
        "special": sign * (avg - ro["special"]),
        "form": sign * (0 - d["form"][opp]),
        "adjusted": sign * (0 - d["adjusted"][opp]),
        "lastSeason": sign * (0 - d["lastSeason"][opp]),
        # The opponent's missing players help whoever plays them.
        "injuries": sign * d["injuries"][f"{opp}Points"],
    }
    p_home = predict(feats)[1]
    return p_home if home else 1 - p_home


def game_score(margin: float) -> float:
    cfg = SETTINGS["results"]
    capped = max(-cfg["marginCap"], min(cfg["marginCap"], margin))
    # One-score games count as partial wins/losses; 8+ points is a full win or loss.
    won = 0.5 + 0.5 * max(-1.0, min(1.0, margin / cfg["closeGameMargin"]))
    return cfg["winLossShare"] * won + (1 - cfg["winLossShare"]) * phi(capped / cfg["marginScale"])


def team_games(rows: list, team: str, through_week: int, records: dict) -> list:
    """A team's played games up to `through_week`, each scored against an average team."""
    out = []
    for r in sorted(rows, key=lambda x: x["week"]):
        if r["margin"] is None or r["week"] > through_week or team not in (r["home"], r["away"]):
            continue
        home = r["home"] == team
        opp = r["away"] if home else r["home"]
        margin = r["margin"] if home else -r["margin"]
        pf, pa = (r["homeScore"], r["awayScore"]) if home else (r["awayScore"], r["homeScore"])
        expected = average_team_chance(r, team)
        out.append({"week": r["week"], "opp": opp, "home": home, "neutral": r["neutral"], "pf": pf, "pa": pa,
                    "result": "W" if margin > 0 else "L" if margin < 0 else "T",
                    "oppRecord": records.get((opp, r["week"]), "0-0"),
                    "avgChance": round(expected, 3), "quality": round(game_score(margin) - expected, 3)})
    return out


def results_and_form(games: list) -> tuple[float, float]:
    n = len(games)
    if not n:
        return 0.0, 0.0
    res_cfg, form_cfg = SETTINGS["results"], SETTINGS["form"]
    results = sum(g["quality"] for g in games) / n * n / (n + res_cfg["halfWeightGames"])
    last = games[-form_cfg["games"]:]
    weights = form_cfg["recencyWeights"][-len(last):]
    form = sum(w * g["quality"] for w, g in zip(weights, last)) / sum(weights)
    return results, form


def records_before(sched) -> dict:
    """{(team, week): 'W-L' record going into that week}."""
    played = sched[sched.result.notna()].sort_values("week")
    out = {}
    teams = set(sched.home_team) | set(sched.away_team)
    for week in sorted(sched.week.unique()):
        before = played[played.week < week]
        for t in teams:
            w = int(((before.home_team == t) & (before.result > 0)).sum() + ((before.away_team == t) & (before.result < 0)).sum())
            l = int(((before.home_team == t) & (before.result < 0)).sum() + ((before.away_team == t) & (before.result > 0)).sum())
            tie = int((((before.home_team == t) | (before.away_team == t)) & (before.result == 0)).sum())
            out[(t, int(week))] = f"{w}-{l}" + (f"-{tie}" if tie else "")
    return out


def snapshot_overall(snap: dict) -> float:
    w = weights_for("team", "units")
    return sum(w[u] * snap[u] for u in w) / sum(w.values())


def league_components(rows: list, team_ids, current_rating: dict, snaps: dict, out_by_week: dict,
                      info: dict, records: dict, team_records: dict) -> dict:
    """Everything the app needs to rank the league now and as of last week."""
    played_weeks = [r["week"] for r in rows if r["margin"] is not None]
    last = max(played_weeks) if played_weeks else 0
    now_week = last + 1  # the upcoming week: whose injuries matter "right now"
    # Use this week's injury reports if they're out yet, otherwise the latest ones.
    inj_week = now_week if any(w == now_week for (_, w) in out_by_week) else last
    out = {}
    for t in team_ids:
        g_now = team_games(rows, t, last, records)
        g_prev = [g for g in g_now if g["week"] < last]
        res_now, form_now = results_and_form(g_now)
        res_prev, form_prev = results_and_form(g_prev)
        inj_now = injuries_for(t, inj_week, out_by_week, info)
        inj_prev = injuries_for(t, last, out_by_week, info)
        # Last week's rating = today's, minus how much the team's rating changed with last week's game.
        drift = 0.0
        if now_week in snaps and last in snaps:
            drift = snapshot_overall(snaps[now_week][t]) - snapshot_overall(snaps[last][t])
        out[t] = {
            "record": team_records[t],
            "now": {"results": round(res_now, 4), "form": round(form_now, 4), "rating": round(current_rating[t], 1),
                    "injuryPoints": round(sum(p["points"] for p in inj_now), 2)},
            "prev": {"results": round(res_prev, 4), "form": round(form_prev, 4),
                     "rating": round(current_rating[t] - drift, 1),
                     "injuryPoints": round(sum(p["points"] for p in inj_prev), 2)},
            "injuries": inj_now[:6],
            "games": g_now,
        }
    return {"lastPlayedWeek": last, "teams": out}


# --------------------------------------------------------------------------
# Team-unit rankings
# --------------------------------------------------------------------------

# (id, label, how to get it, one-line description)
UNIT_LISTS = [
    ("offense", "Offense", ("unit", "offense"), "Whole offense"),
    ("defense", "Defense", ("unit", "defense"), "Whole defense"),
    ("special", "Special Teams", ("unit", "special"), "Kicking, punting, returns and coverage"),
    ("quarterback", "Quarterback", ("group", ["QB"]), "Starting QB's player rating"),
    ("passing", "Passing Offense", ("cat", "offense", "passing"), "Team passing stats"),
    ("rushing", "Rushing Offense", ("cat", "offense", "rushing"), "Team running stats"),
    ("receiving_corps", "Receiving Corps", ("group", ["WR", "TE"]), "Starting WRs and TE"),
    ("offensive_line", "Offensive Line", ("group", ["OL"]), "Starting five linemen"),
    ("defensive_line", "Defensive Line", ("group", ["DL"]), "Starting defensive linemen"),
    ("linebackers", "Linebackers", ("group", ["LB"]), "Starting linebackers"),
    ("secondary", "Secondary", ("group", ["DB"]), "Starting cornerbacks and safeties"),
    ("pass_defense", "Pass Defense", ("cat", "defense", "pass_defense"), "Team pass defense stats"),
    ("run_defense", "Run Defense", ("cat", "defense", "run_defense"), "Team run defense stats"),
    ("kicking", "Kicking", ("cat", "special", "kicking"), "Field goals and extra points"),
    ("punting", "Punting", ("cat", "special", "punting"), "Punting"),
    ("returns", "Returns", ("cat", "special", "returns"), "Kick and punt returns"),
]


def _group_rt(roster_sections: list, sections: list):
    """Average of a team's starters at these positions (e.g. the starting five linemen)."""
    players = [p for sec in roster_sections if sec["id"] in sections for p in sec["players"]
               if p.get("rt") and not p.get("tag")]
    starters = [p for p in players if p["starter"]] or sorted(players, key=lambda p: -p["rt"]["m"])[:3]
    if not starters:
        return None, []
    m = sum(p["rt"]["m"] for p in starters) / len(starters)
    rt = combine([(1, p["rt"]) for p in starters], m)
    return rt, [{"id": p["id"], "name": p["name"], "pos": p["pos"]} for p in starters]


def unit_lists(team_docs: dict, snaps: dict, last_week: int) -> list:
    """Every team-unit ranking: each team's rating object, starters (for player groups) and
    how many places it moved since last week (for lists we can rebuild week by week)."""
    now_week, out = last_week + 1, []
    for lid, label, how, desc in UNIT_LISTS:
        teams, now_vals, prev_vals = {}, {}, {}
        for t, doc in team_docs.items():
            players = []
            if how[0] == "unit":
                rt = doc["unitRatings"][how[1]]["rt"]
            elif how[0] == "cat":
                cat = next((c for c in doc["units"][how[1]] if c["id"] == how[2]), None)
                rt = cat["rt"] if cat else None
            else:
                rt, players = _group_rt(doc["roster"], how[1])
            teams[t] = {"rt": rt, "starters": players}
            if how[0] != "group" and now_week in snaps and last_week in snaps:
                key = how[1] if how[0] == "unit" else f"{how[1]}.{how[2]}"
                pick = (lambda s: s[key]) if how[0] == "unit" else (lambda s: s["cats"].get(key))
                now_vals[t], prev_vals[t] = pick(snaps[now_week][t]), pick(snaps[last_week][t])
        if now_vals:
            rank = lambda vals: {t: i + 1 for i, t in enumerate(sorted(vals, key=lambda x: -(vals[x] or 0)))}
            rn, rp = rank(now_vals), rank(prev_vals)
            for t in teams:
                teams[t]["move"] = rp[t] - rn[t]
        out.append({"id": lid, "label": label, "kind": how[0], "description": desc, "teams": teams})
    return out
