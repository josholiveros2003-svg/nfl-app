"""
Box scores: for every played game, each team's stats and each player's stats.

Every number comes with the league average and a percentile (0-100, 100 = best), so the app
can color it green / amber / red like the ranks elsewhere:
  team stats    compared with every team's games this season
  player stats  compared with every game this season by players at the same position who
                did that thing (e.g. WR receiving yards among WRs who were targeted)
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right

import pandas as pd

from players import GROUP_OF

# A position needs this many games in a section before it gets its own average; smaller ones
# (e.g. a QB catching a pass) are compared with everyone in that section instead.
MIN_POSITION_GAMES = 15


def _n(x) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(x) else x


def _div(a, b):
    return a / b if b else None


def percentile(sorted_vals: list, v, better: str | None):
    """Where v sits among sorted_vals, 0-100 with 100 = best (ties count half)."""
    if v is None or not sorted_vals or not better:
        return None
    lo, hi = bisect_left(sorted_vals, v), bisect_right(sorted_vals, v)
    p = (lo + (hi - lo) / 2) / len(sorted_vals) * 100
    return round(p if better == "high" else 100 - p)


def fmt(v, kind: str) -> str:
    if v is None:
        return "—"
    if kind == "avg":  # averages: one decimal, two when under 1 (so 0.04 interceptions isn't "0.0")
        return f"{v:,.2f}" if 0 < abs(v) < 1 else f"{v:,.1f}"
    if kind == "int":
        return f"{round(v):,}"
    if kind == "d1":
        return f"{v:,.1f}"
    if kind == "pct":
        return f"{v * 100:.0f}%"
    if kind == "time":
        m, s = divmod(int(round(v)), 60)
        return f"{m}:{s:02d}"
    return str(v)


# --------------------------------------------------------------------------
# Team stats
# --------------------------------------------------------------------------

def _secs(s) -> int:
    try:
        m, sec = str(s).split(":")
        return int(m) * 60 + int(sec)
    except ValueError:
        return 0


def team_line(pbp_team: pd.DataFrame, points: float) -> dict:
    """Raw numbers for one team in one game. pbp_team: every play where this team had the ball."""
    scrim = pbp_team[pbp_team.play_type.isin(["pass", "run"])]
    passes = scrim[scrim.play_type == "pass"]
    runs = scrim[scrim.play_type == "run"]
    sacks = _n(passes.sack.sum())
    sack_yds = -_n(passes.loc[passes.sack == 1, "yards_gained"].sum())
    drives = scrim.groupby("fixed_drive").agg(closest=("yardline_100", "min"), result=("fixed_drive_result", "first"))
    rz = drives[drives.closest <= 20]
    top = scrim.drop_duplicates("fixed_drive")["drive_time_of_possession"].dropna().map(_secs).sum()
    return {
        "pts": points,
        "fd": _n(pbp_team.first_down.sum()),
        "yds": _n(scrim.yards_gained.sum()),
        "plays": len(scrim),
        "cmp": _n(passes.complete_pass.sum()),
        "att": _n(passes.complete_pass.sum() + passes.incomplete_pass.sum() + passes.interception.sum()),
        "pass_yds": _n(passes.passing_yards.sum()) - sack_yds,
        "rush_yds": _n(runs.yards_gained.sum()),
        "rush_att": len(runs),
        "third_c": _n(pbp_team.third_down_converted.sum()),
        "third_a": _n(pbp_team.third_down_converted.sum() + pbp_team.third_down_failed.sum()),
        "fourth_c": _n(pbp_team.fourth_down_converted.sum()),
        "fourth_a": _n(pbp_team.fourth_down_converted.sum() + pbp_team.fourth_down_failed.sum()),
        "rz": len(rz),
        "rz_td": int((rz.result == "Touchdown").sum()),
        "to": _n(passes.interception.sum()) + _n(scrim.fumble_lost.sum()),
        "sacks": sacks,
        "sack_yds": sack_yds,
        "top": float(top),
    }


def _frac(c, a):
    return f"{int(c)}/{int(a)}"


# id, label, better, value(line), display(line), kind of the value (for the average)
TEAM_STATS = [
    ("points", "Points", "high", lambda x: x["pts"], lambda x: fmt(x["pts"], "int"), "d1"),
    ("first_downs", "First downs", "high", lambda x: x["fd"], lambda x: fmt(x["fd"], "int"), "d1"),
    ("total_yards", "Total yards", "high", lambda x: x["yds"], lambda x: fmt(x["yds"], "int"), "d1"),
    ("ypp", "Yards per play", "high", lambda x: _div(x["yds"], x["plays"]),
     lambda x: fmt(_div(x["yds"], x["plays"]), "d1"), "d1"),
    ("pass_yds", "Passing yards", "high", lambda x: x["pass_yds"], lambda x: fmt(x["pass_yds"], "int"), "d1"),
    ("completions", "Completions", "high", lambda x: _div(x["cmp"], x["att"]),
     lambda x: _frac(x["cmp"], x["att"]), "pct"),
    ("rush_yds", "Rushing yards", "high", lambda x: x["rush_yds"], lambda x: fmt(x["rush_yds"], "int"), "d1"),
    ("ypc", "Yards per carry", "high", lambda x: _div(x["rush_yds"], x["rush_att"]),
     lambda x: fmt(_div(x["rush_yds"], x["rush_att"]), "d1"), "d1"),
    ("third", "Third downs", "high", lambda x: _div(x["third_c"], x["third_a"]),
     lambda x: _frac(x["third_c"], x["third_a"]), "pct"),
    ("fourth", "Fourth downs", "high", lambda x: _div(x["fourth_c"], x["fourth_a"]),
     lambda x: _frac(x["fourth_c"], x["fourth_a"]), "pct"),
    ("red_zone", "Red zone TDs", "high", lambda x: _div(x["rz_td"], x["rz"]),
     lambda x: _frac(x["rz_td"], x["rz"]), "pct"),
    ("turnovers", "Turnovers", "low", lambda x: x["to"], lambda x: fmt(x["to"], "int"), "d1"),
    ("sacks", "Sacks allowed", "low", lambda x: x["sacks"],
     lambda x: f"{int(x['sacks'])} ({int(x['sack_yds'])} yds)" if x["sacks"] else "0", "d1"),
    ("top", "Time of possession", "high", lambda x: x["top"], lambda x: fmt(x["top"], "time"), "time"),
]


def team_box(lines: dict, pen: dict) -> dict:
    """{(game_id, team): [team stat cells]} for every played game, with averages and percentiles."""
    for key, line in lines.items():
        line["pen"], line["pen_yds"] = pen.get(key, (0, 0))
    stats = TEAM_STATS + [("penalties", "Penalties", "low", lambda x: x["pen_yds"],
                           lambda x: f"{int(x['pen'])} for {int(x['pen_yds'])}", "yds")]
    out = {key: [] for key in lines}
    for sid, label, better, value, display, kind in stats:
        vals = {key: value(line) for key, line in lines.items()}
        pop = sorted(v for v in vals.values() if v is not None)
        avg = sum(pop) / len(pop) if pop else None
        avg_disp = f"{avg:.1f} yds" if kind == "yds" and avg is not None else fmt(avg, "avg" if kind == "d1" else kind)
        for key, line in lines.items():
            out[key].append({"id": sid, "label": label, "better": better, "d": display(line),
                             "p": percentile(pop, vals[key], better), "avg": avg_disp})
    return out


# --------------------------------------------------------------------------
# Player stats
# --------------------------------------------------------------------------

def passer_rating(cmp, att, yds, td, ints):
    if not att:
        return None
    clamp = lambda v: max(0.0, min(2.375, v))
    a = clamp((cmp / att - 0.3) * 5)
    b = clamp((yds / att - 3) * 0.25)
    c = clamp(td / att * 20)
    d = clamp(2.375 - ints / att * 25)
    return (a + b + c + d) / 6 * 100


def _col(cid, label, value, display=None, kind="d1", better="high"):
    return {"id": cid, "label": label, "value": value, "display": display or (lambda r: fmt(value(r), "int")),
            "kind": kind, "better": better}


SECTIONS = [
    {"id": "passing", "label": "Passing", "when": lambda r: r.attempts > 0, "sort": "attempts", "cols": [
        _col("catt", "C/ATT", lambda r: _div(r.completions, r.attempts), lambda r: _frac(r.completions, r.attempts), "pct"),
        _col("yds", "YDS", lambda r: r.passing_yards),
        _col("td", "TD", lambda r: r.passing_tds),
        _col("int", "INT", lambda r: r.passing_interceptions, better="low"),
        _col("rtg", "RTG", lambda r: passer_rating(r.completions, r.attempts, r.passing_yards, r.passing_tds,
                                                   r.passing_interceptions),
             lambda r: fmt(passer_rating(r.completions, r.attempts, r.passing_yards, r.passing_tds,
                                         r.passing_interceptions), "d1")),
    ]},
    {"id": "rushing", "label": "Rushing", "when": lambda r: r.carries > 0, "sort": "carries", "cols": [
        _col("car", "CAR", lambda r: r.carries),
        _col("yds", "YDS", lambda r: r.rushing_yards),
        _col("avg", "AVG", lambda r: _div(r.rushing_yards, r.carries), lambda r: fmt(_div(r.rushing_yards, r.carries), "d1")),
        _col("td", "TD", lambda r: r.rushing_tds),
    ]},
    {"id": "receiving", "label": "Receiving", "when": lambda r: r.targets > 0, "sort": "receiving_yards", "cols": [
        _col("rec", "REC", lambda r: r.receptions),
        _col("tgt", "TGT", lambda r: r.targets),
        _col("yds", "YDS", lambda r: r.receiving_yards),
        _col("td", "TD", lambda r: r.receiving_tds),
    ]},
    {"id": "defense", "label": "Defense",
     "when": lambda r: (r.def_tackles_solo + r.def_tackle_assists + r.def_sacks + r.def_interceptions
                        + r.def_pass_defended + r.def_tackles_for_loss) > 0,
     "sort": "tackles_total", "cols": [
        _col("tkl", "TKL", lambda r: r.def_tackles_solo + r.def_tackle_assists),
        _col("sck", "SCK", lambda r: r.def_sacks, lambda r: f"{r.def_sacks:g}"),
        _col("tfl", "TFL", lambda r: r.def_tackles_for_loss, lambda r: f"{r.def_tackles_for_loss:g}"),
        _col("int", "INT", lambda r: r.def_interceptions),
        _col("pd", "PD", lambda r: r.def_pass_defended),
    ]},
    {"id": "kicking", "label": "Kicking", "when": lambda r: r.fg_att + r.pat_att > 0, "sort": "fg_att", "cols": [
        _col("fg", "FG", lambda r: _div(r.fg_made, r.fg_att), lambda r: _frac(r.fg_made, r.fg_att), "pct"),
        _col("lng", "LNG", lambda r: r.fg_long if r.fg_made else None,
             lambda r: fmt(r.fg_long, "int") if r.fg_made else "—"),
        _col("xp", "XP", lambda r: _div(r.pat_made, r.pat_att), lambda r: _frac(r.pat_made, r.pat_att), "pct"),
        _col("pts", "PTS", lambda r: r.fg_made * 3 + r.pat_made),
    ]},
    {"id": "punting", "label": "Punting", "when": lambda r: r.pt_att > 0, "sort": "pt_att", "cols": [
        _col("no", "NO", lambda r: r.pt_att, better=None),
        _col("avg", "AVG", lambda r: _div(r.pt_yards, r.pt_att), lambda r: fmt(_div(r.pt_yards, r.pt_att), "d1")),
        _col("net", "NET", lambda r: _div(r.pt_net_yards, r.pt_att), lambda r: fmt(_div(r.pt_net_yards, r.pt_att), "d1")),
        _col("in20", "IN 20", lambda r: r.pt_inside_20),
    ]},
]

NUMERIC = ["attempts", "completions", "passing_yards", "passing_tds", "passing_interceptions", "carries",
           "rushing_yards", "rushing_tds", "receptions", "targets", "receiving_yards", "receiving_tds",
           "def_tackles_solo", "def_tackle_assists", "def_sacks", "def_tackles_for_loss", "def_interceptions",
           "def_pass_defended", "fg_made", "fg_att", "fg_long", "pat_made", "pat_att", "pt_att", "pt_yards",
           "pt_net_yards", "pt_inside_20"]


def player_box(weekly: pd.DataFrame, game_ids: set, has_page: set) -> dict:
    """{game_id: {team: [sections]}} for every played game."""
    w = weekly[(weekly.season_type == "REG") & weekly.game_id.isin(game_ids)].copy()
    for c in NUMERIC:
        w[c] = pd.to_numeric(w[c], errors="coerce").fillna(0.0) if c in w else 0.0
    w["tackles_total"] = w.def_tackles_solo + w.def_tackle_assists
    w["grp"] = w.position.map(GROUP_OF).fillna(w.position_group.map(GROUP_OF)).fillna(w.position)

    out: dict = {}
    for sec in SECTIONS:
        rows = w[w.apply(sec["when"], axis=1)] if len(w) else w
        # Population per column per position (or everyone, for rare positions).
        pops: dict = {}
        for col in sec["cols"]:
            vals = [(g, col["value"](r)) for g, r in zip(rows.grp, rows.itertuples())]
            everyone = sorted(v for _, v in vals if v is not None)
            by_group: dict = {}
            for g, v in vals:
                if v is not None:
                    by_group.setdefault(g, []).append(v)
            pops[col["id"]] = {"*": everyone, **{g: sorted(v) for g, v in by_group.items()
                                                 if len(v) >= MIN_POSITION_GAMES}}
        # Positions with enough games are compared with their own position; the rest with everyone ("*").
        own = set.intersection(*(set(p) for p in pops.values())) - {"*"}
        avg_of = lambda pop, kind: fmt(sum(pop) / len(pop) if pop else None, "pct" if kind == "pct" else "avg")
        avgs = {g: [avg_of(pops[c["id"]][g], c["kind"]) for c in sec["cols"]] for g in own | {"*"}}
        for r in rows.sort_values(sec["sort"], ascending=False).itertuples():
            ag = r.grp if r.grp in own else "*"
            cells = [{"d": col["display"](r), "p": percentile(pops[col["id"]][ag], col["value"](r), col["better"])}
                     for col in sec["cols"]]
            team_secs = out.setdefault(r.game_id, {}).setdefault(r.team, {})
            team_secs.setdefault(sec["id"], {
                "id": sec["id"], "label": sec["label"],
                "cols": [{"id": c["id"], "label": c["label"], "better": c["better"]} for c in sec["cols"]],
                # League average per column, by position ("*" = everyone in this section).
                "avgs": avgs,
                "rows": [],
            })["rows"].append({
                "id": r.player_id, "name": r.player_display_name, "pos": r.position, "ag": ag,
                "link": r.player_id in has_page, "cells": cells,
            })
    # Keep only the averages for positions that appear in each section.
    for teams in out.values():
        for secs in teams.values():
            for sec in secs.values():
                sec["avgs"] = {g: v for g, v in sec["avgs"].items() if any(r["ag"] == g for r in sec["rows"])}
    return {gid: {t: list(secs.values()) for t, secs in teams.items()} for gid, teams in out.items()}


# --------------------------------------------------------------------------
# Both together
# --------------------------------------------------------------------------

def box_scores(pbp: pd.DataFrame, sched: pd.DataFrame, weekly: pd.DataFrame, has_page: set) -> dict:
    """{game_id: {"teams": [...], "players": {"home": [...], "away": [...]}}} for played games
    that have play-by-play."""
    played = sched[sched.home_score.notna() & sched.game_id.isin(set(pbp.game_id.unique()))]
    lines, pen = {}, {}
    for g in played.itertuples():
        gp = pbp[pbp.game_id == g.game_id]
        for team, pts in ((g.home_team, g.home_score), (g.away_team, g.away_score)):
            lines[(g.game_id, team)] = team_line(gp[gp.posteam == team], float(pts))
            flags = gp[(gp.penalty == 1) & (gp.penalty_team == team)]
            pen[(g.game_id, team)] = (len(flags), _n(flags.penalty_yards.sum()))
    teams = team_box(lines, pen)
    players = player_box(weekly, set(played.game_id), has_page)

    out = {}
    for g in played.itertuples():
        home, away = teams[(g.game_id, g.home_team)], teams[(g.game_id, g.away_team)]
        out[g.game_id] = {
            "teams": [{"id": h["id"], "label": h["label"], "better": h["better"], "avg": h["avg"],
                       "home": {"d": h["d"], "p": h["p"]}, "away": {"d": a["d"], "p": a["p"]}}
                      for h, a in zip(home, away)],
            "players": {"home": players.get(g.game_id, {}).get(g.home_team, []),
                        "away": players.get(g.game_id, {}).get(g.away_team, [])},
        }
    return out
