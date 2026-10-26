"""
Player pages + team rosters.

For every player on a current roster (or with stats this season) this builds:
  - his stats, split into categories that fit his position
    (a QB gets Passing/Rushing/Playing Time, a cornerback gets Coverage/Tackling/...),
  - his rank among players at his position, plus the position average,
  - roster lists for each team, grouped by position and ordered by depth chart.

Fair rankings: like the NFL's official leaderboards, a player must have enough
playing time in a category to be ranked (e.g. QBs need 14 pass attempts per team
game). Players below the bar still see their numbers, just without a rank, and
their rating is pulled toward average ("limited sample"). The bars live in
config/ratings.json, along with every rating weight (see ratings.py).
"""

from __future__ import annotations

import math
import re
from datetime import date

import pandas as pd

from learn import fit, fit_groups, perf_value, set_trust
from ratings import MADDEN as MADDEN_SETTINGS
from ratings import RECENT_GAMES, clean, combine, respread, sample_bar, stat_rating, weights_for

# Detailed position (from rosters/stats) -> position group.
GROUP_OF = {
    "QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB", "WR": "WR", "TE": "TE",
    "OL": "OL", "T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SAF": "DB", "FS": "DB", "SS": "DB",
    "K": "K", "P": "P", "LS": "LS",
}

POS_NAME = {
    "QB": "Quarterback", "RB": "Running back", "FB": "Fullback", "WR": "Wide receiver", "TE": "Tight end",
    "OL": "Offensive line", "T": "Tackle", "OT": "Tackle", "G": "Guard", "C": "Center",
    "DL": "Defensive line", "DE": "Defensive end", "DT": "Defensive tackle", "NT": "Nose tackle",
    "LB": "Linebacker", "ILB": "Inside linebacker", "OLB": "Outside linebacker", "MLB": "Middle linebacker",
    "DB": "Defensive back", "CB": "Cornerback", "S": "Safety", "SAF": "Safety", "FS": "Free safety",
    "SS": "Strong safety", "K": "Kicker", "P": "Punter", "LS": "Long snapper",
}

# Roster sections on the team page, in display order.
ROSTER_SECTIONS = [
    ("QB", "Quarterbacks", {"QB"}), ("RB", "Running Backs", {"RB"}), ("WR", "Wide Receivers", {"WR"}),
    ("TE", "Tight Ends", {"TE"}), ("OL", "Offensive Line", {"OL"}), ("DL", "Defensive Line", {"DL"}),
    ("LB", "Linebackers", {"LB"}), ("DB", "Defensive Backs", {"DB"}), ("ST", "Special Teams", {"K", "P", "LS"}),
]

# Which categories each position gets. "optional" ones only show if he has that kind of stat.
CATEGORIES = {
    "QB": (["passing", "rushing", "playing_time"], []),
    "RB": (["rushing", "receiving", "playing_time"], ["returns"]),
    "WR": (["receiving", "playing_time"], ["rushing", "returns"]),
    "TE": (["receiving", "playing_time"], ["rushing", "returns"]),
    "OL": (["pass_pro", "run_block", "playing_time"], []),
    "DL": (["pass_rush", "tackling", "playing_time"], ["coverage"]),
    "LB": (["tackling", "pass_rush", "coverage", "playing_time"], []),
    "DB": (["coverage", "tackling", "playing_time"], ["pass_rush", "returns"]),
    "K": (["kicking", "playing_time"], []),
    "P": (["punting", "playing_time"], []),
    "LS": (["playing_time"], []),
}

LABELS = {
    "passing": ("Passing", "Throwing the ball: volume, accuracy and efficiency."),
    "rushing": ("Rushing", "Running the ball."),
    "receiving": ("Receiving", "Catching passes and what he does after the catch."),
    "pass_rush": ("Pass Rush", "Getting after the quarterback."),
    "tackling": ("Tackling", "Making stops and creating fumbles."),
    "coverage": ("Coverage", "Defending passes and taking the ball away."),
    "kicking": ("Kicking", "Field goals and extra points."),
    "punting": ("Punting", "Flipping field position with punts."),
    "returns": ("Returns", "Bringing back kickoffs and punts."),
    "playing_time": ("Playing Time", "How much he's on the field, and penalties."),
    "pass_pro": ("Pass Protection", "How well his team protects the QB. Free data doesn't track "
                 "individual blocks, so these are team numbers while he's on the line."),
    "run_block": ("Run Blocking", "How well his team runs the ball. Free data doesn't track "
                  "individual blocks, so these are team numbers while he's on the line."),
}

# Offensive line categories borrow these team offense stats: (team category, stat id).
OL_TEAM_STATS = {
    "pass_pro": [("passing", "sacks"), ("passing", "epa_db"), ("passing", "net_ypa")],
    "run_block": [("rushing", "ypc"), ("rushing", "stuffed"), ("rushing", "rush_success"), ("rushing", "rush_epa")],
}

# The three stats shown on each category's summary card (the most telling ones).
KEY_STATS = {
    "passing": ["rating", "pass_ypg", "pass_td"],
    "rushing": ["rush_ypg", "ypc", "rush_td"],
    "receiving": ["rec_ypg", "rec", "rec_td"],
    "pass_rush": ["sacks", "qb_hits", "tfl"],
    "tackling": ["tackles", "tfl", "ff"],
    "coverage": ["ints", "pd", "def_td"],
    "kicking": ["fg_pct", "fg_made", "fg_long"],
    "punting": ["net", "gross", "in20"],
    "returns": ["kr_avg", "pr_avg", "ret_td"],
    "playing_time": ["snap_share", "snaps_pg", "penalties"],
    "pass_pro": ["sacks", "epa_db", "net_ypa"],
    "run_block": ["ypc", "stuffed", "rush_success"],
}

HINTS = {
    "epa": "Expected Points Added: how much his plays changed the team's chances of scoring, "
           "on average. 0 is average; positive is good.",
    "cpoe": "Completion % over expected: how much more (or less) often he completes passes than "
            "an average QB would on the same throws, based on distance, depth and coverage.",
    "rating": "The NFL's official passer rating (0 to 158.3). It blends completion %, yards per "
              "attempt, touchdowns and interceptions. Around 90 is average for a starter.",
    "snap_share": "Share of his team's plays he was on the field for, in games he played.",
    "catch_rate": "Share of passes thrown his way that he caught.",
    "pd": "Passes defended: passes he knocked away or intercepted.",
    "yac": "Yards after catch: yards gained after the ball was caught.",
    "net_punt": "Punt distance minus return and touchback yards.",
    "net_ypa": "Passing yards per dropback, after subtracting yards lost to sacks.",
    "td_rate": "Share of his pass attempts that went for touchdowns.",
    "int_rate": "Share of his pass attempts that were intercepted.",
    "sack_rate": "Share of his dropbacks that ended in a sack.",
}


# --------------------------------------------------------------------------
# Loading + combining player data
# --------------------------------------------------------------------------

def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _name_key(name) -> str:
    return re.sub(r"[^a-z]", "", str(name).lower().replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", ""))


def season_totals(weekly: pd.DataFrame) -> pd.DataFrame:
    """Add up each player's weekly stats into season totals."""
    w = weekly[weekly.season_type == "REG"].copy()
    num_cols = [c for c in w.columns if pd.api.types.is_numeric_dtype(w[c])
                and c not in ("season", "week") and not c.endswith("_list")]
    max_cols = {"fg_long", "pt_long"}
    sums = w.groupby("player_id")[[c for c in num_cols if c not in max_cols | {"passing_cpoe"}]].sum()
    maxes = w.groupby("player_id")[list(max_cols & set(num_cols))].max()
    # CPOE is a per-throw average, so weight each week by attempts.
    cp = w.dropna(subset=["passing_cpoe"])
    cpoe = (cp.passing_cpoe * cp.attempts).groupby(cp.player_id).sum() / cp.groupby("player_id").attempts.sum()
    last = w.sort_values("week").groupby("player_id").last()[["player_display_name", "position", "team", "headshot_url"]]
    games = w.groupby("player_id").game_id.nunique().rename("games")
    out = sums.join(maxes).join(cpoe.rename("passing_cpoe")).join(last).join(games)
    return out


def map_snaps(snaps: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    """Snap counts (one row per player per game) come keyed by Pro Football Reference id;
    match them to NFL ids."""
    s = snaps[snaps.game_type == "REG"].copy()
    by_pfr = roster.dropna(subset=["pfr_id", "gsis_id"]).drop_duplicates("pfr_id").set_index("pfr_id").gsis_id
    by_name = roster.dropna(subset=["gsis_id"]).assign(k=lambda r: r.full_name.map(_name_key) + "|" + r.team)
    by_name = by_name.drop_duplicates("k").set_index("k").gsis_id
    s["gsis_id"] = s.pfr_player_id.map(by_pfr)
    missing = s.gsis_id.isna()
    s.loc[missing, "gsis_id"] = (s.loc[missing, "player"].map(_name_key) + "|" + s.loc[missing, "team"]).map(by_name)
    s = s.dropna(subset=["gsis_id"])
    s["played"] = (s.offense_snaps + s.defense_snaps + s.st_snaps) > 0
    return s


def snap_totals(s: pd.DataFrame) -> pd.DataFrame:
    """Add up per-game snap rows (from map_snaps) per player."""
    def share(col_snaps, col_pct):
        g = s[s[col_snaps] > 0]
        return g.groupby("gsis_id")[col_pct].mean()

    agg = s.groupby("gsis_id").agg(
        offense_snaps=("offense_snaps", "sum"), defense_snaps=("defense_snaps", "sum"),
        st_snaps=("st_snaps", "sum"), snap_games=("played", "sum"),
    )
    agg["offense_pct"] = share("offense_snaps", "offense_pct")
    agg["defense_pct"] = share("defense_snaps", "defense_pct")
    agg["st_pct"] = share("st_snaps", "st_pct")
    return agg


# --------------------------------------------------------------------------
# Games cut short by injury
# --------------------------------------------------------------------------
# A player who gets hurt in the 2nd quarter has a "game" with almost no stats, which drags down
# every per-game number his rating uses. For the rating (not the stats shown), such a game counts
# as the share of a normal game he actually played.
SHORT_GAME = 0.75     # on the field for less than 75% of his usual share of snaps...
HURT_LOOKAHEAD = 2    # ...and on the injury report or IR that week or the next two (covers byes)
MIN_USUAL_SHARE = 0.3  # part-time players' snap counts swing too much to tell


def hurt_weeks(injuries: pd.DataFrame, weekly_rosters: pd.DataFrame) -> set:
    """(player id, week) pairs where a player was on the injury report (any status) or on IR."""
    pairs = set(zip(injuries.gsis_id, injuries.week)) if len(injuries) else set()
    if len(weekly_rosters):
        res = weekly_rosters[weekly_rosters.status == "RES"]
        pairs |= set(zip(res.gsis_id, res.week))
    return {(p, int(w)) for p, w in pairs if isinstance(p, str) and pd.notna(w)}


def injury_shortened(snap_rows: pd.DataFrame, hurt: set) -> dict:
    """{(player id, game id): share of a normal game played} for games cut short by injury."""
    s = snap_rows[snap_rows.played].copy()
    s["share"] = s[["offense_pct", "defense_pct"]].max(axis=1)
    s = s[s.share > 0]
    usual = s.groupby("gsis_id").share.quantile(0.75)
    out = {}
    for r in s.itertuples():
        u = usual.get(r.gsis_id, 0)
        if u < MIN_USUAL_SHARE or r.share >= SHORT_GAME * u:
            continue
        if any((r.gsis_id, int(r.week) + k) in hurt for k in range(HURT_LOOKAHEAD + 1)):
            out[(r.gsis_id, r.game_id)] = max(0.1, r.share / u)
    return out


def _rating_view(p: dict, rows: pd.DataFrame | None, short: dict, pid: str, side: str) -> tuple[dict, int]:
    """A copy of a player's numbers where injury-shortened games count as partial games:
    fewer games to divide by, and snap share from his full games. Returns (numbers, games cut short)."""
    if rows is None or not len(rows):
        return p, 0
    cut = [(gid, short[(pid, gid)]) for gid in rows.game_id if (pid, gid) in short]
    if not cut:
        return p, 0
    q = dict(p)
    lost = sum(1 - f for _, f in cut)
    q["games"] = max(1.0, p["games"] - lost)
    q["snap_games"] = max(1.0, (p.get("snap_games") or 0) - lost)
    if side in ("offense", "defense"):
        full = rows[(rows[f"{side}_snaps"] > 0) & ~rows.game_id.isin([g for g, _ in cut])]
        if len(full):
            q[f"{side}_pct"] = float(full[f"{side}_pct"].mean())
    return q, len(cut)


def depth_info(depth: pd.DataFrame) -> dict:
    """Best depth-chart spot for each player, from each team's latest depth chart."""
    d = depth[depth.dt == depth.groupby("team").dt.transform("max")].dropna(subset=["gsis_id"]).copy()
    # A spot like WR can have several slots with one shared ranking (WR1, WR2, WR3 = starters).
    slots = d.groupby(["team", "pos_grp", "pos_abb"]).pos_slot.nunique().rename("n_slots")
    d = d.join(slots, on=["team", "pos_grp", "pos_abb"])
    d["starter"] = d.pos_rank <= d.n_slots
    d["st"] = d.pos_grp == "Special Teams"
    out = {}
    for pid, rows in d.groupby("gsis_id"):
        out[pid] = {
            "main": rows[~rows.st].sort_values(["pos_rank", "pos_slot"]).head(1).to_dict("records"),
            "st": rows[rows.st].sort_values(["pos_rank", "pos_slot"]).head(1).to_dict("records"),
        }
    return out


# --------------------------------------------------------------------------
# Stats per category
# --------------------------------------------------------------------------

def stat(id, label, value, fmt="d1", better="high", hint=None, display=None):
    if value is not None and isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        value = None
    return {"id": id, "label": label, "value": value, "fmt": fmt, "better": better, "hint": hint, "display": display}


def div(a, b):
    return a / b if b else None


def frac(m, a):
    return f"{int(m)}/{int(a)}" + (f" ({m / a * 100:.0f}%)" if a else "")


def passer_rating(cmp, att, yds, td, ints):
    if not att:
        return None
    clamp = lambda x: max(0.0, min(2.375, x))
    a = clamp((cmp / att - 0.3) * 5)
    b = clamp((yds / att - 3) * 0.25)
    c = clamp(td / att * 20)
    d = clamp(2.375 - ints / att * 25)
    return (a + b + c + d) / 6 * 100


def build_stats(cat: str, p: dict, side: str) -> list:
    g = p.get("games") or 0
    v = lambda k: p.get(k) or 0
    if cat == "passing":
        att, cmp = v("attempts"), v("completions")
        dropbacks = att + v("sacks_suffered")
        return [
            stat("pass_yds", "Passing yards", v("passing_yards"), "int"),
            stat("pass_ypg", "Passing yards per game", div(v("passing_yards"), g)),
            stat("cmp_pct", "Completion %", div(cmp, att), "pct", display=None if not att else
                 f"{cmp / att * 100:.1f}%  ({int(cmp)}/{int(att)})"),
            stat("ypa", "Yards per attempt", div(v("passing_yards"), att), "d2"),
            stat("pass_td", "Passing TDs", v("passing_tds"), "int"),
            stat("ints", "Interceptions", v("passing_interceptions"), "int", "low"),
            stat("rating", "Passer rating", passer_rating(cmp, att, v("passing_yards"), v("passing_tds"),
                                                          v("passing_interceptions")), "d1", hint=HINTS["rating"]),
            stat("sacks", "Sacks taken", v("sacks_suffered"), "int", "low"),
            stat("net_ypa", "Net yards per attempt", div(v("passing_yards") + v("sack_yards_lost"), dropbacks), "d2",
                 hint=HINTS["net_ypa"]),
            stat("td_rate", "TD rate", div(v("passing_tds"), att), "pct", hint=HINTS["td_rate"]),
            stat("int_rate", "Interception rate", div(v("passing_interceptions"), att), "pct", "low", hint=HINTS["int_rate"]),
            stat("sack_rate", "Sack rate", div(v("sacks_suffered"), dropbacks), "pct", "low", hint=HINTS["sack_rate"]),
            stat("epa_db", "EPA per dropback", div(p.get("passing_epa"), dropbacks), "epa", hint=HINTS["epa"]),
            stat("cpoe", "CPOE", p.get("passing_cpoe"), "cpoe", hint=HINTS["cpoe"]),
            stat("pass_20", "Completions of 20+ yards", v("passing_20"), "int"),
        ]
    if cat == "rushing":
        c = v("carries")
        return [
            stat("rush_yds", "Rushing yards", v("rushing_yards"), "int"),
            stat("rush_ypg", "Rushing yards per game", div(v("rushing_yards"), g)),
            stat("carries", "Carries", c, "int", better=None),
            stat("ypc", "Yards per carry", div(v("rushing_yards"), c), "d2"),
            stat("rush_td", "Rushing TDs", v("rushing_tds"), "int"),
            stat("rush_10", "Runs of 10+ yards", v("rushing_10"), "int"),
            stat("rush_fd", "Rushing first downs", v("rushing_first_downs"), "int"),
            stat("rush_epa", "EPA per carry", div(p.get("rushing_epa"), c), "epa", hint=HINTS["epa"]),
            stat("fumbles", "Fumbles lost", v("rushing_fumbles_lost"), "int", "low"),
        ]
    if cat == "receiving":
        t, r = v("targets"), v("receptions")
        return [
            stat("rec_yds", "Receiving yards", v("receiving_yards"), "int"),
            stat("rec_ypg", "Receiving yards per game", div(v("receiving_yards"), g)),
            stat("rec", "Receptions", r, "int"),
            stat("targets", "Targets", t, "int", hint="Passes thrown his way."),
            stat("catch_rate", "Catch rate", div(r, t), "pct", hint=HINTS["catch_rate"]),
            stat("ypr", "Yards per catch", div(v("receiving_yards"), r), "d1"),
            stat("rec_td", "Receiving TDs", v("receiving_tds"), "int"),
            stat("yac", "Yards after catch", v("receiving_yards_after_catch"), "int", hint=HINTS["yac"]),
            stat("rec_20", "Catches of 20+ yards", v("receiving_20"), "int"),
            stat("rec_epa", "EPA per target", div(p.get("receiving_epa"), t), "epa", hint=HINTS["epa"]),
        ]
    if cat == "pass_rush":
        return [
            stat("sacks", "Sacks", v("def_sacks"), "d1"),
            stat("qb_hits", "QB hits", v("def_qb_hits"), "int"),
            stat("tfl", "Tackles for loss", v("def_tackles_for_loss"), "int"),
            stat("sacks_pg", "Sacks per game", div(v("def_sacks"), g), "d2"),
        ]
    if cat == "tackling":
        total = v("def_tackles_solo") + v("def_tackles_with_assist") + v("def_tackle_assists")
        return [
            stat("tackles", "Total tackles", total, "int"),
            stat("tackles_pg", "Tackles per game", div(total, g)),
            stat("solo", "Solo tackles", v("def_tackles_solo"), "int"),
            stat("tfl", "Tackles for loss", v("def_tackles_for_loss"), "int"),
            stat("ff", "Forced fumbles", v("def_fumbles_forced"), "int"),
            stat("fr", "Fumble recoveries", v("fumble_recovery_opp"), "int"),
        ]
    if cat == "coverage":
        return [
            stat("ints", "Interceptions", v("def_interceptions"), "int"),
            stat("pd", "Passes defended", v("def_pass_defended"), "int", hint=HINTS["pd"]),
            stat("int_yds", "Interception return yards", v("def_interception_yards"), "int", better=None),
            stat("def_td", "Defensive TDs", v("def_tds"), "int"),
        ]
    if cat == "kicking":
        long_m = v("fg_made_50_59") + v("fg_made_60_")
        long_a = long_m + v("fg_missed_50_59") + v("fg_missed_60_")
        mid_m = v("fg_made_40_49")
        mid_a = mid_m + v("fg_missed_40_49")
        return [
            stat("fg_pct", "Field goal %", div(v("fg_made"), v("fg_att")), "pct", display=frac(v("fg_made"), v("fg_att"))),
            stat("fg_made", "Field goals made", v("fg_made"), "int"),
            stat("fg_40", "FG 40–49 yards", div(mid_m, mid_a), "pct", display=frac(mid_m, mid_a)),
            stat("fg_50", "FG 50+ yards", div(long_m, long_a), "pct", display=frac(long_m, long_a)),
            stat("fg_long", "Longest field goal", v("fg_long") or None, "int"),
            stat("xp_pct", "Extra point %", div(v("pat_made"), v("pat_att")), "pct", display=frac(v("pat_made"), v("pat_att"))),
        ]
    if cat == "punting":
        n = v("pt_att")
        return [
            stat("punts", "Punts", n, "int", better=None),
            stat("gross", "Gross average", div(v("pt_yards"), n), "d1"),
            stat("net", "Net average", div(v("pt_net_yards"), n), "d1", hint=HINTS["net_punt"]),
            stat("in20", "Inside the 20", v("pt_inside_20"), "int"),
            stat("tb", "Touchbacks", v("pt_touchback"), "int", "low"),
            stat("long", "Longest punt", v("pt_long") or None, "int"),
        ]
    if cat == "returns":
        kr, pr = v("kickoff_returns"), v("punt_returns")
        return [
            stat("kr", "Kick returns", kr, "int", better=None),
            stat("kr_avg", "Kick return average", div(v("kickoff_return_yards"), kr), "d1"),
            stat("pr", "Punt returns", pr, "int", better=None),
            stat("pr_avg", "Punt return average", div(v("punt_return_yards"), pr), "d1"),
            stat("ret_td", "Return TDs", v("special_teams_tds"), "int"),
        ]
    if cat == "playing_time":
        snaps = v(f"{side}_snaps")
        side_name = {"offense": "Offensive", "defense": "Defensive", "st": "Special teams"}[side]
        rows = [
            stat("games", "Games played", max(g, v("snap_games")), "int", better=None),
            stat("snaps", f"{side_name} snaps", snaps, "int"),
            stat("snaps_pg", f"{side_name} snaps per game", div(snaps, v("snap_games")), "d1"),
            stat("snap_share", "Snap share", p.get(f"{side}_pct"), "pct", hint=HINTS["snap_share"]),
        ]
        if side != "st":
            rows.append(stat("st_snaps", "Special teams snaps", v("st_snaps"), "int", better=None))
        rows += [
            stat("penalties", "Penalties", v("penalties"), "int", "low"),
            stat("penalty_yds", "Penalty yards", v("penalty_yards"), "int", "low"),
        ]
        return rows
    raise ValueError(cat)


def side_of(group):
    if group in ("QB", "RB", "WR", "TE", "OL"):
        return "offense"
    if group in ("DL", "LB", "DB"):
        return "defense"
    return "st"


def fmt_value(v, fmt):
    if v is None:
        return "—"
    if fmt == "int":
        return f"{round(v):,}"
    if fmt == "d1":
        return f"{v:,.1f}"
    if fmt == "d2":
        return f"{v:.2f}"
    if fmt == "pct":
        return f"{v * 100:.1f}%"
    if fmt == "epa":
        return f"{v:+.2f}"
    if fmt == "cpoe":
        return f"{v:+.1f}%"
    return str(v)


# --------------------------------------------------------------------------
# Main entry: build every player + team rosters
# --------------------------------------------------------------------------

GROUP_PLURAL = {"QB": "QBs", "RB": "RBs", "WR": "WRs", "TE": "TEs", "OL": "offensive linemen",
                "DL": "defensive linemen", "LB": "LBs", "DB": "DBs", "K": "kickers", "P": "punters",
                "LS": "long snappers"}


def _stats_dict(tot, sn) -> dict:
    """One player's numbers (season or recent) as a plain dict."""
    p = {}
    if tot is not None:
        p.update({k: _clean(v) for k, v in tot.items()})
    if sn is not None:
        p.update({k: _clean(v) for k, v in sn.items()})
    p["games"] = int(max(p.get("games") or 0, p.get("snap_games") or 0))
    p["returns"] = (p.get("kickoff_returns") or 0) + (p.get("punt_returns") or 0)
    p.setdefault("defense_snaps", 0)
    p.setdefault("offense_snaps", 0)
    return p


def _row(df, pid):
    return df.loc[pid] if pid in df.index else None


def _team_stats_for_ol(team_units: dict, team: str | None, cat: str):
    """Pass protection / run blocking for a lineman = his team's offense numbers."""
    unit = team_units.get(team, {}).get("offense") if team else None
    if not unit:
        return None
    out = []
    for cat_id, sid in OL_TEAM_STATS[cat]:
        c = next(c for c in unit if c["id"] == cat_id)
        st = next(x for x in c["stats"] if x["id"] == sid)
        out.append({"id": sid, "label": f"Team {st['label'][0].lower()}{st['label'][1:]}", "value": st["value"],
                    "display": st["display"], "better": st["better"], "hint": st["hint"], "rank": st["rank"],
                    "of": 32, "leagueAvg": st["leagueAvg"], "_team_rt": st.get("rt")})
    return out


def season_players(weekly, snaps, roster, team_games: dict, team_units: dict, ctx=None, hurt: set | None = None):
    """Every player's stats for one season, split into the categories that fit his position.
    Used for this season's pages and for last season's data that the ratings learn from.
    hurt: (player id, week) pairs on the injury report or IR, to spot games cut short by injury."""
    w = weekly[weekly.season_type == "REG"]
    totals = season_totals(w)
    snap_rows = map_snaps(snaps, roster)
    snap = snap_totals(snap_rows)
    short = injury_shortened(snap_rows, hurt or set())
    rows_of = {pid: g for pid, g in snap_rows.groupby("gsis_id")}
    median_games = float(pd.Series(list(team_games.values())).median()) if team_games else 1.0

    # Every game each player appeared in, as (week, team, opponent), for context + recent form.
    g1 = w[["player_id", "game_id", "week", "team", "opponent_team"]].rename(columns={"opponent_team": "opp"})
    g2 = snap_rows[snap_rows.played][["gsis_id", "game_id", "week", "team", "opponent"]].rename(
        columns={"gsis_id": "player_id", "opponent": "opp"})
    appearances = pd.concat([g1, g2]).drop_duplicates(["player_id", "game_id"]).sort_values("week")
    games_of = {pid: list(zip(r.week.astype(int), r.team, r.opp)) for pid, r in appearances.groupby("player_id")}
    last = appearances.groupby("player_id").tail(RECENT_GAMES)
    recent_keys = set(zip(last.player_id, last.game_id))
    w_recent = w[[k in recent_keys for k in zip(w.player_id, w.game_id)]]
    s_recent = snap_rows[[k in recent_keys for k in zip(snap_rows.gsis_id, snap_rows.game_id)]]
    totals_recent = season_totals(w_recent)
    snap_recent = snap_totals(s_recent)

    r = roster.dropna(subset=["gsis_id"]).sort_values("week").drop_duplicates("gsis_id", keep="last").set_index("gsis_id")
    on_roster = set(r.index[r.status.isin(["ACT", "INA", "RES"])])
    ids = sorted(on_roster | set(totals.index))

    players = {}
    for pid in ids:
        info = _row(r, pid)
        tot = _row(totals, pid)
        pos = None
        if info is not None and isinstance(info.depth_chart_position, str):
            pos = info.depth_chart_position
        if pos is None and info is not None and isinstance(info.position, str):
            pos = info.position
        if pos is None and tot is not None:
            pos = tot.position
        group = GROUP_OF.get(info.position if info is not None and isinstance(info.position, str) else "", None) \
            or GROUP_OF.get(pos or "", None)
        if group is None:
            continue
        team = None
        if info is not None and pid in on_roster:
            team = info.team
        elif tot is not None:
            team = tot.team
        if team == "LAR":
            team = "LA"

        side = side_of(group)
        p = _stats_dict(tot, _row(snap, pid))
        p["snaps"] = p.get(f"{side}_snaps") or 0
        pr = _stats_dict(_row(totals_recent, pid), _row(snap_recent, pid))
        pr["snaps"] = pr.get(f"{side}_snaps") or 0
        # What the rating uses: the same numbers, with games cut short by injury counted partially.
        mine = rows_of.get(pid)
        p_rate, n_short = _rating_view(p, mine, short, pid, side)
        recent_rows = None if mine is None else mine[[(pid, g) in recent_keys for g in mine.game_id]]
        pr_rate, _ = _rating_view(pr, recent_rows, short, pid, side)

        core, optional = CATEGORIES[group]
        cats = list(core[:-1])
        for opt in optional:
            if opt == "pass_rush":
                has = (p.get("def_sacks") or 0) + (p.get("def_qb_hits") or 0) > 0
            elif opt == "coverage":
                has = (p.get("def_interceptions") or 0) + (p.get("def_pass_defended") or 0) > 0
            else:
                has = (p.get(sample_bar(opt, group)[0]) or 0) > 0
            if has:
                cats.append(opt)
        cats.append(core[-1])

        tg = team_games.get(team, median_games) or median_games
        categories = []
        for cat in cats:
            col, per_team_game, noun = sample_bar(cat, group)
            need = max(1, math.ceil(per_team_game * tg))
            have = p.get(col) or 0
            team_based = cat in OL_TEAM_STATS
            stats = _team_stats_for_ol(team_units, team, cat) if team_based else build_stats(cat, p, side)
            if stats is None:
                continue
            label, blurb = LABELS[cat]
            categories.append({
                "id": cat, "label": label, "blurb": blurb, "key": KEY_STATS[cat],
                "teamBased": team_based,
                "qualified": bool(have >= need),
                "qualNote": None if have >= need else
                f"Limited sample: needs {need:,} {noun} to be ranked against other "
                f"{GROUP_PLURAL[group]} (has {int(have):,}). Until he plays more, his rating here "
                f"stays close to his Madden rating.",
                "stats": stats,
                "_rate": None if team_based else build_stats(cat, p_rate, side),
                "_recent": None if team_based else build_stats(cat, pr_rate, side),
                "_have": have,
                "_bar": per_team_game,
            })

        # Context: opponents faced and injuries, on the same scale as teams.
        cside = "special" if side == "st" else side
        games = games_of.get(pid, [])
        if games and ctx is not None:
            raw = ctx.raw(games)[cside]
            z = ctx.z(raw, cside)
            texts = ctx.describe(raw, cside)
            weeks = [g[0] for g in games[-RECENT_GAMES:]]
            n = len(weeks)
            texts["recent"] = (f"Recent form uses his last {n} game{'s' if n != 1 else ''} "
                               f"(week{'s' if n != 1 else ''} {', '.join(str(x) for x in weeks)}).")
        else:
            z, texts = {"opp": 0.0, "inj": 0.0}, None

        if n_short:
            for cat in categories:
                for st in cat["stats"]:
                    if st["id"] == "games":
                        st["display"] = f"{int(st['value'])} ({n_short} cut short by injury)"
            texts = dict(texts or {})
            texts["short"] = (f"{n_short} game{'s' if n_short != 1 else ''} cut short by injury "
                              f"count{'s' if n_short == 1 else ''} as partial games here, so missed snaps "
                              f"don't drag down his per-game numbers.")

        players[pid] = {"id": pid, "group": group, "pos": pos, "team": team, "_info": info, "_tot": tot,
                        "_onRoster": pid in on_roster, "_p": p, "_pr": pr, "_prate": p_rate, "_prrate": pr_rate,
                        "_z": z, "context": texts, "categories": categories}
    return players


def training_rows(players: dict, season: int, madden: dict) -> list:
    """Players' stats paired with their Madden rating, for learn.py."""
    return [{"id": pid, "season": season, "group": pl["group"], "M": madden.get(pid),
             "games": pl["_prate"]["games"],
             "cats": {c["id"]: ({**c, "stats": c["_rate"]} if c.get("_rate") else c) for c in pl["categories"]}}
            for pid, pl in players.items()]


def build_players(weekly, snaps, depth, roster, team_info: dict, team_games: dict, today: date, ctx,
                  team_units: dict, season: int, madden: dict, last_season_rows: list, hurt: set | None = None):
    """Returns (player_docs: {id: doc}, rosters: {team: [sections]}, model)."""
    players = season_players(weekly, snaps, roster, team_games, team_units, ctx, hurt)
    depths = depth_info(depth)

    # Learn how stats connect to Madden (last season's full stats + this season so far).
    rows = last_season_rows + training_rows(players, season, madden)
    model = fit(rows, lambda group, cid: weights_for("players", "stats", cid))
    fit_groups(model, rows, {g: core for g, (core, _) in CATEGORIES.items()}, {k: v[0] for k, v in LABELS.items()})
    set_trust(model, MADDEN_SETTINGS["minTrust"]["players"])

    for pid, pl in players.items():
        info, tot = pl.pop("_info"), pl.pop("_tot")
        headshot = None
        for src in (info, tot):
            if src is not None and isinstance(src.get("headshot_url"), str):
                headshot = src.get("headshot_url")
                break
        name = None
        if info is not None and isinstance(info.full_name, str):
            name = info.full_name
        elif tot is not None:
            name = tot.player_display_name

        d = depths.get(pid, {})
        spot = (d.get("st") if pl["group"] in ("K", "P", "LS") else d.get("main")) or []
        depth_label, starter, depth_key = None, False, (9, 99, 99)
        if spot:
            sp = spot[0]
            starter = bool(sp["starter"])
            depth_label = f"Starter · {sp['pos_abb']}" if starter else f"Depth #{int(sp['pos_rank'])} · {sp['pos_abb']}"
            depth_key = (0, int(sp["pos_rank"]), int(sp["pos_slot"]))

        pl.update({
            "name": name or "Unknown", "posName": POS_NAME.get(pl["pos"], pl["pos"]),
            "jersey": _int(info.jersey_number) if info is not None else None,
            "headshot": headshot,
            "height": _height(info.height) if info is not None else None,
            "weight": _int(info.weight) if info is not None else None,
            "college": info.college if info is not None and isinstance(info.college, str) else None,
            "experience": _int(info.years_exp) if info is not None else None,
            "age": _age(info.birth_date, today) if info is not None else None,
            "status": info.status if info is not None and pl["_onRoster"] else None,
            "depth": depth_label, "starter": starter, "_depth_key": depth_key,
        })

    _rank_players(players)
    _rate_players(players, model, season, madden)
    _finalize(players)
    rosters = _rosters(players)

    docs = {}
    for pid, pl in players.items():
        info = team_info.get(pl["team"])
        doc = {k: v for k, v in pl.items() if not k.startswith("_")}
        doc["categories"] = [{k: v for k, v in c.items() if not k.startswith("_")} for c in pl["categories"]]
        doc["teamName"] = info["name"] if info else None
        doc["teamColor"] = info["color"] if info else "#333333"
        doc["teamColor2"] = info["color2"] if info else "#555555"
        doc["teamLogo"] = info["logo"] if info else None
        doc["rankGroup"] = pl["group"]
        doc["rankGroupPlural"] = GROUP_PLURAL[pl["group"]]
        docs[pid] = doc
    return docs, rosters, model


def _int(v):
    try:
        f = float(v)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None


def _height(v):
    h = _int(v)
    return f"{h // 12}'{h % 12}\"" if h else None


def _age(birth, today):
    try:
        b = date.fromisoformat(str(birth)[:10])
    except ValueError:
        return None
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def _pools(players: dict) -> dict:
    """{(group, category): [(player id, category index)]} of players who reached the bar."""
    pools = {}
    for pid, pl in players.items():
        for ci, cat in enumerate(pl["categories"]):
            if cat["qualified"] and not cat["teamBased"]:
                pools.setdefault((pl["group"], cat["id"]), []).append((pid, ci))
    return pools


def _members(players, group, cat_id):
    """Everyone at this position with this category (ranked or not)."""
    for pid, pl in players.items():
        if pl["group"] != group:
            continue
        for ci, cat in enumerate(pl["categories"]):
            if cat["id"] == cat_id:
                yield pid, ci


def _rank_players(players: dict):
    """Rank each stat among qualified players in the same position group; position averages for all."""
    for pl in players.values():
        for cat in pl["categories"]:
            if cat["teamBased"]:
                if not cat["qualified"]:
                    for s in cat["stats"]:
                        s["rank"] = None
                continue
            for s in cat["stats"]:
                s["rank"], s["of"], s["leagueAvg"] = None, None, None

    for (group, cat_id), members in _pools(players).items():
        everyone = list(_members(players, group, cat_id))
        n_stats = len(players[members[0][0]]["categories"][members[0][1]]["stats"])
        for si in range(n_stats):
            vals = {pid: players[pid]["categories"][ci]["stats"][si]["value"] for pid, ci in members}
            vals = {k: v for k, v in vals.items() if v is not None}
            if not vals:
                continue
            series = pd.Series(vals, dtype=float)
            sample = players[members[0][0]]["categories"][members[0][1]]["stats"][si]
            avg = fmt_value(float(series.mean()), sample["fmt"])
            ranks = {}
            if sample["better"]:
                ranks = series.rank(ascending=(sample["better"] == "low"), method="min").astype(int).to_dict()
            for pid, ci in everyone:
                s = players[pid]["categories"][ci]["stats"][si]
                s["leagueAvg"] = avg
                if pid in ranks:
                    s["rank"], s["of"] = ranks[pid], len(series)


def no_madden_baselines(players: dict, madden: dict) -> dict:
    """Estimated baseline per position for players without a Madden rating (see settings)."""
    pct = MADDEN_SETTINGS["noMaddenPercentile"] / 100
    by_group = {}
    for pid, pl in players.items():
        if pid in madden:
            by_group.setdefault(pl["group"], []).append(madden[pid])
    return {g: float(pd.Series(v).quantile(pct)) for g, v in by_group.items()}


def _rate_players(players: dict, model, season: int, madden: dict):
    """Madden baseline + stat-based adjustment for every stat, category and player (see ratings.py)."""
    estimated = no_madden_baselines(players, madden)
    half = MADDEN_SETTINGS["playerHalfWeightGames"]
    by_cat, by_group = {}, {}
    for pid, pl in players.items():
        nm = pid not in madden
        M = madden.get(pid, estimated.get(pl["group"], 65.0))
        pl["madden"] = None if nm else madden[pid]
        pl["_M"], pl["_nm"] = M, nm
        for cat in pl["categories"]:
            have, bar = cat["_have"], cat["_bar"]
            share = have / (have + bar * half) if have else 0.0
            learned = model.weights.get((pl["group"], cat["id"]), {})
            recent = {s["id"]: s for s in cat["_recent"]} if cat["_recent"] else {}
            rate = {s["id"]: s for s in cat["_rate"]} if cat["_rate"] else {}
            for s in cat["stats"]:
                tb = cat["teamBased"]
                pv = perf_value(rate.get(s["id"], s), pl["_prate"]["games"], tb)
                rs = recent.get(s["id"])
                rv = None if tb or rs is None else perf_value(rs, pl["_prrate"]["games"])
                s.pop("_team_rt", None)
                s["rt"] = stat_rating(model, season, pl["group"], cat["id"], s, pv, rv, M, share,
                                      pl["_z"]["opp"], pl["_z"]["inj"], nm)
                s["w"] = round(learned.get(s["id"], 0) * 100, 1)
            cat["rt"] = combine([(s["w"], s["rt"]) for s in cat["stats"]], M, nm, ltd=not cat["qualified"])
            by_cat.setdefault((pl["group"], cat["id"]), []).append(cat)

    # Re-spread each roll-up level (measured on players with a full sample at that position).
    for cats in by_cat.values():
        respread([c["rt"] for c in cats], [c["rt"] for c in cats if c["qualified"]])

    for pid, pl in players.items():
        pos_w = weights_for("players", "positions", pl["group"])
        for cat in pl["categories"]:
            cat["w"] = pos_w.get(cat["id"], 0)
        weighted = [(c["w"], c) for c in pl["categories"] if c["w"]]
        total = sum(w for w, _ in weighted) or 1
        mostly_limited = sum(w for w, c in weighted if not c["qualified"]) / total >= 0.5
        pl["rt"] = combine([(c["w"], c["rt"]) for c in pl["categories"]], pl["_M"], pl["_nm"], ltd=mostly_limited)
        by_group.setdefault(pl["group"], []).append(pl["rt"])
    for rts in by_group.values():
        respread(rts, [rt for rt in rts if not rt.get("ltd")])

    for pl in players.values():
        clean(pl["rt"])
        for cat in pl["categories"]:
            clean(cat["rt"])
            for s in cat["stats"]:
                clean(s["rt"])


def _finalize(players: dict):
    for pl in players.values():
        for cat in pl["categories"]:
            for s in cat["stats"]:
                if "fmt" in s:
                    if s["display"] is None:
                        s["display"] = fmt_value(s["value"], s["fmt"])
                    del s["fmt"]


def _roster_line(pl):
    """A short stat summary shown next to each name on the roster."""
    p, g = pl["_p"], pl["group"]
    v = lambda k: int(p.get(k) or 0)
    if g == "QB" and v("attempts"):
        return f"{v('passing_yards'):,} pass yds · {v('passing_tds')} TD · {v('passing_interceptions')} INT"
    if g == "RB" and (v("carries") or v("receptions")):
        return f"{v('rushing_yards'):,} rush yds · {v('receiving_yards'):,} rec yds"
    if g in ("WR", "TE") and v("targets"):
        return f"{v('receptions')} rec · {v('receiving_yards'):,} yds · {v('receiving_tds')} TD"
    if g in ("DL", "LB", "DB"):
        tk = v("def_tackles_solo") + v("def_tackles_with_assist") + v("def_tackle_assists")
        parts = [f"{tk} tkl"]
        if p.get("def_sacks"):
            parts.append(f"{p['def_sacks']:g} sacks")
        if v("def_interceptions"):
            parts.append(f"{v('def_interceptions')} INT")
        return " · ".join(parts) if tk or len(parts) > 1 else None
    if g == "K" and v("fg_att"):
        return f"{v('fg_made')}/{v('fg_att')} FG"
    if g == "P" and v("pt_att"):
        return f"{v('pt_att')} punts · {(p.get('pt_yards') or 0) / v('pt_att'):.1f} avg"
    if v("snaps"):
        return f"{v('snaps')} snap{'' if v('snaps') == 1 else 's'}"
    return None


def _rosters(players: dict) -> dict:
    by_team = {}
    for pid, pl in players.items():
        if not pl["_onRoster"] or not pl["team"]:
            continue
        by_team.setdefault(pl["team"], []).append(pl)
    out = {}
    for team, pls in by_team.items():
        sections = []
        for sid, label, groups in ROSTER_SECTIONS:
            members = [pl for pl in pls if pl["group"] in groups]
            # Depth chart order first (starters, then backups), then playing time.
            st_order = {"K": 0, "P": 1, "LS": 2}
            members.sort(key=lambda pl: (pl["status"] == "RES", st_order.get(pl["group"], 0) if sid == "ST" else 0,
                                         pl["_depth_key"], -(pl["_p"].get("snaps") or 0), pl["name"]))
            sections.append({"id": sid, "label": label, "players": [{
                "id": pl["id"], "name": pl["name"], "pos": pl["pos"], "jersey": pl["jersey"],
                "headshot": pl["headshot"], "depth": pl["depth"], "starter": pl["starter"],
                "tag": "IR" if pl["status"] == "RES" else None, "line": _roster_line(pl), "rt": pl["rt"],
            } for pl in members]})
        out[team] = sections
    return out
