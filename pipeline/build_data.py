"""
Builds the JSON files the app reads, using free nflverse data.

What it does, step by step:
  1. Downloads this season's play-by-play (every snap of every game), the
     schedule, team colors/logos and rosters from nflverse's GitHub releases.
  2. Adds up each team's offense, defense and special teams stats.
  3. Ranks all 32 teams on every stat (1 = best in the league).
  4. Writes one small JSON file per team into public/data/ for the app.

Run it with:  pipeline/.venv/bin/python pipeline/build_data.py
Optional:     --season 2025   (defaults to the current NFL season)
"""

from __future__ import annotations

import argparse
import io
import json
import math
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests

from context import Context, expected_starters, burdens, team_contexts, team_strength, unavailable
from learn import fit, fit_groups, repool, set_trust
from winprob import FEATURES as WP_FEATURES, LABELS as WP_LABELS, SETTINGS as WP_SETTINGS
from winprob import backtest, game_features, last_season_margins, phi, predict, team_results, unavailable_by_week
from madden import load_madden
from players import CATEGORIES, GROUP_OF, build_players, season_players, training_rows
from ratings import MADDEN, RECENT_GAMES, blend_default, rate_teams, strip_fmt, team_baselines, weights_for
from ratings import SETTINGS as RATINGS_SETTINGS
from rankings import league_components, records_before, unit_lists

RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "public" / "data"


# --------------------------------------------------------------------------
# Downloading
# --------------------------------------------------------------------------

def fetch(path: str, with_date: bool = False):
    url = f"{RELEASES}/{path}"
    print(f"  downloading {url}")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    if with_date:
        return r.content, r.headers.get("Last-Modified")
    return r.content


def current_season(today: date) -> int:
    # The NFL season starts in September and ends in February,
    # so January/February games belong to the previous year's season.
    return today.year if today.month >= 9 else today.year - 1


def optional_parquet(path: str, columns: list) -> pd.DataFrame:
    try:
        return pd.read_parquet(io.BytesIO(fetch(path)))
    except (requests.RequestException, ValueError) as e:
        print(f"  WARNING: couldn't load {path} ({e}); continuing without it")
        return pd.DataFrame(columns=columns)


def load(season: int):
    raw, modified = fetch(f"pbp/play_by_play_{season}.parquet", with_date=True)
    pbp = pd.read_parquet(io.BytesIO(raw))
    games = pd.read_csv(io.BytesIO(fetch("schedules/games.csv")))
    teams = pd.read_csv(io.BytesIO(fetch("teams/teams_colors_logos.csv")))
    roster = pd.read_csv(io.BytesIO(fetch(f"rosters/roster_{season}.csv")), low_memory=False)
    extra = {
        # Official-style player totals, one row per player per game.
        "weekly": pd.read_parquet(io.BytesIO(fetch(f"stats_player/stats_player_week_{season}.parquet"))),
        # How many plays each player was on the field for.
        "snaps": pd.read_parquet(io.BytesIO(fetch(f"snap_counts/snap_counts_{season}.parquet"))),
        # Who starts and who backs up, at every position.
        "depth": pd.read_parquet(io.BytesIO(fetch(f"depth_charts/depth_charts_{season}.parquet"))),
        # Weekly injury reports (Out / Doubtful / Questionable). Optional: if nflverse hasn't
        # posted it, this run skips the injury factor instead of failing.
        "injuries": optional_parquet(f"injuries/injuries_{season}.parquet",
                                     ["gsis_id", "week", "report_status"]),
        # Each team's roster every week, including who was on injured reserve.
        "weekly_rosters": optional_parquet(f"weekly_rosters/roster_weekly_{season}.parquet",
                                           ["gsis_id", "week", "status"]),
    }
    return pbp, games, teams, roster, modified, extra


def load_last_season(season: int) -> dict:
    """Last season's full stats, used only to learn how stats connect to Madden ratings."""
    return {
        "pbp": pd.read_parquet(io.BytesIO(fetch(f"pbp/play_by_play_{season}.parquet"))),
        "roster": pd.read_csv(io.BytesIO(fetch(f"rosters/roster_{season}.csv")), low_memory=False),
        "weekly": pd.read_parquet(io.BytesIO(fetch(f"stats_player/stats_player_week_{season}.parquet"))),
        "snaps": pd.read_parquet(io.BytesIO(fetch(f"snap_counts/snap_counts_{season}.parquet"))),
        # For testing the win-probability model on last season's games:
        "injuries": optional_parquet(f"injuries/injuries_{season}.parquet", ["gsis_id", "week", "report_status", "team"]),
        "weekly_rosters": optional_parquet(f"weekly_rosters/roster_weekly_{season}.parquet",
                                           ["gsis_id", "week", "status", "team"]),
        "depth": pd.read_parquet(io.BytesIO(fetch(f"depth_charts/depth_charts_{season}.parquet"))),
    }


UNIT_KEYS = ("offense", "defense", "special")


def played_frame(sched, team: str, game_ids: set) -> pd.DataFrame:
    """A team's games (from its point of view) that have results and play-by-play."""
    h = sched[sched.home_team == team].assign(opp=lambda x: x.away_team, home=True,
                                               pf=lambda x: x.home_score, pa=lambda x: x.away_score)
    a = sched[sched.away_team == team].assign(opp=lambda x: x.home_team, home=False,
                                               pf=lambda x: x.away_score, pa=lambda x: x.home_score)
    s = pd.concat([h, a]).sort_values("week")
    return s[s.pf.notna() & s.game_id.isin(game_ids)]


def ratings_asof(season, week, pbp, sched, team_ids, people, baselines, model) -> dict:
    """Each team's Offense/Defense/Special Teams ratings using only games before `week`
    (so a past game is judged only on what was known before kickoff)."""
    p = pbp[pbp.week < week]
    if p.empty:
        return {t: {u: baselines[t][u] for u in UNIT_KEYS} for t in team_ids}
    gids = set(p.game_id)
    scrim = p[p.play_type.isin(["pass", "run"])]
    units, gp = {}, {}
    for t in team_ids:
        played = played_frame(sched, t, gids)
        gp[t] = len(played)
        units[t] = build_team(t, p, scrim, len(played), played, people)
    snap = repool(model, team_rows(units, gp, season, baselines))
    zero = {t: {u: {"opp_z": 0.0, "inj_z": 0.0} for u in UNIT_KEYS} for t in team_ids}
    rated = rate_teams(snap, season, units, units, gp, zero, baselines)
    out = {}
    for t in team_ids:
        out[t] = {u: round(blend_default(rated[t]["units"][u]["rt"]), 1) for u in UNIT_KEYS}
        # Category ratings too (e.g. "offense.passing"), for week-to-week movement in the rankings.
        out[t]["cats"] = {f"{u}.{c['id']}": round(blend_default(c["rt"]), 1)
                          for u in UNIT_KEYS for c in units[t][u] if c.get("rt")}
    return out


def player_info(roster, madden: dict, starters: dict) -> dict:
    """Who each player is, for weighing injuries: position group, Madden rating, starter or not."""
    starter_ids = {pid for ps in starters.values() for pid, _, _ in ps}
    r = roster.dropna(subset=["gsis_id"]).sort_values("week").drop_duplicates("gsis_id", keep="last")
    out = {}
    for x in r.itertuples():
        pos = x.depth_chart_position if isinstance(x.depth_chart_position, str) else x.position
        out[x.gsis_id] = {"name": x.full_name, "pos": pos, "group": GROUP_OF.get(x.position) or GROUP_OF.get(pos),
                          "madden": madden.get(x.gsis_id), "starter": x.gsis_id in starter_ids}
    return out


def winprob_games(season, sched, pbp, team_ids, people, baselines, model, out_by_week, info, prior):
    """Every regular-season game with its pre-game features (and result, if played).
    Also returns the weekly 'as of' team ratings it built: {week: {team: ratings}}."""
    results = team_results(sched)
    last_played = int(sched[sched.result.notna()].week.max()) if sched.result.notna().any() else 0
    latest_report = max((w for (_, w) in out_by_week), default=0)
    snaps, rows = {}, []
    for g in sched.sort_values(["week", "gameday", "game_id"]).itertuples():
        week = int(g.week)
        as_of = min(week, last_played + 1)  # future games use the latest ratings
        if as_of not in snaps:
            snaps[as_of] = ratings_asof(season, as_of, pbp, sched, team_ids, people, baselines, model)
        # Injury reports exist only up to the current week; further ahead, only injured reserve is known.
        inj = out_by_week
        if week > latest_report:
            inj = {(t, week): {pid: st for pid, st in v.items() if st == "IR"}
                   for (t, w), v in out_by_week.items() if w == latest_report}
        feats, details = game_features(g.home_team, g.away_team, week, g.location == "Neutral",
                                       snaps[as_of], results, inj, info, prior)
        rows.append({"id": g.game_id, "season": season, "week": week, "date": g.gameday,
                     "home": g.home_team, "away": g.away_team,
                     "homeScore": None if pd.isna(g.home_score) else int(g.home_score),
                     "awayScore": None if pd.isna(g.away_score) else int(g.away_score),
                     "margin": None if pd.isna(g.result) else float(g.result),
                     "spread": None if pd.isna(g.spread_line) else float(g.spread_line),
                     "neutral": g.location == "Neutral", "feats": feats, "details": details})
    return rows, snaps


def game_doc(r: dict) -> dict:
    """What the app needs for one game: teams, score, pre-game win probability, and why."""
    margin, p_home, contrib = predict(r["feats"])
    d = r["details"]
    rh, ra = d["ratings"]["home"], d["ratings"]["away"]
    h, a = r["home"], r["away"]
    detail = {
        "home": "Neutral site, so no home edge" if r["neutral"] else f"{h} is at home",
        "offense": f"Offense rating {rh['offense']:.0f} ({h}) vs {ra['offense']:.0f} ({a})",
        "defense": f"Defense rating {rh['defense']:.0f} ({h}) vs {ra['defense']:.0f} ({a})",
        "special": f"Special teams rating {rh['special']:.0f} ({h}) vs {ra['special']:.0f} ({a})",
        "form": f"Last {WP_SETTINGS['recentGames']} games, average margin: {d['form']['home']:+.1f} ({h}) vs "
                f"{d['form']['away']:+.1f} ({a})",
        "adjusted": f"Season margin adjusted for opponents: {d['adjusted']['home']:+.1f} ({h}) vs "
                    f"{d['adjusted']['away']:+.1f} ({a})",
        "lastSeason": f"Last season's adjusted margin (fading as this season goes on): {d['lastSeason']['home']:+.1f} "
                      f"({h}) vs {d['lastSeason']['away']:+.1f} ({a})",
        "injuries": f"Missing players worth {d['injuries']['homePoints']:.1f} points ({h}) vs "
                    f"{d['injuries']['awayPoints']:.1f} ({a})",
    }
    factors = sorted(({"id": f, "label": WP_LABELS[f], "points": round(contrib[f], 2), "detail": detail[f]}
                      for f in WP_FEATURES), key=lambda x: -abs(x["points"]))
    played = r["margin"] is not None
    return {
        "id": r["id"], "season": r["season"], "week": r["week"], "date": r["date"],
        "home": h, "away": a, "neutral": r["neutral"], "played": played,
        "homeScore": r["homeScore"], "awayScore": r["awayScore"],
        "prob": {"home": round(p_home, 3), "away": round(1 - p_home, 3)},
        "margin": round(margin, 1),
        "factors": factors,
        "injuries": {"home": d["injuries"]["home"], "away": d["injuries"]["away"]},
        "correct": None if not played or r["margin"] == 0 else (p_home > 0.5) == (r["margin"] > 0),
    }


def results_component(game_docs: dict, team_ids) -> dict:
    """Wins and losses in context: each played game scored against the pre-game win chance
    (which already reflects opponent strength, home field and both teams' injuries)."""
    cfg = RATINGS_SETTINGS["team"]["results"]
    share, scale = cfg["winLossShare"], cfg["marginScale"]
    out = {}
    for t in team_ids:
        rows = []
        for g in sorted(game_docs.values(), key=lambda x: x["week"]):
            if not g["played"] or t not in (g["home"], g["away"]):
                continue
            home = g["home"] == t
            pf, pa = (g["homeScore"], g["awayScore"]) if home else (g["awayScore"], g["homeScore"])
            margin = pf - pa
            won = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
            score = share * won + (1 - share) * phi(margin / scale)
            expected = g["prob"]["home" if home else "away"]
            rows.append({"week": g["week"], "opp": g["away"] if home else g["home"], "home": home,
                         "pf": pf, "pa": pa, "result": "W" if margin > 0 else "L" if margin < 0 else "T",
                         "expected": round(expected, 3), "over": score - expected})
        n = len(rows)
        weight = n / (n + cfg["halfWeightGames"]) if n else 0.0
        per_game = cfg["pointsPerWinAboveExpected"] * weight / n if n else 0.0
        for r in rows:
            r["points"] = round(r.pop("over") * per_game, 1)
        out[t] = {
            "points": round(sum(r["points"] for r in rows), 1),
            "wins": sum(1 for r in rows if r["result"] == "W"),
            "losses": sum(1 for r in rows if r["result"] == "L"),
            "expectedWins": round(sum(r["expected"] for r in rows), 1),
            "games": rows,
        }
    return out


def schedule_doc(sched, game_docs: dict, records: dict, last_played: int, season: int) -> dict:
    """Every game by week: teams, records going in, kickoff, score and win chances."""
    weeks = {}
    for g in sched.sort_values(["week", "gameday", "gametime", "game_id"]).itertuples():
        d = game_docs.get(g.game_id, {})
        weeks.setdefault(int(g.week), []).append({
            "id": g.game_id, "date": g.gameday, "weekday": g.weekday, "time": g.gametime,
            "away": g.away_team, "home": g.home_team, "neutral": g.location == "Neutral",
            "awayRecord": records.get((g.away_team, int(g.week)), "0-0"),
            "homeRecord": records.get((g.home_team, int(g.week)), "0-0"),
            "awayScore": None if pd.isna(g.away_score) else int(g.away_score),
            "homeScore": None if pd.isna(g.home_score) else int(g.home_score),
            "prob": d.get("prob"), "correct": d.get("correct"),
        })
    total = max(weeks) if weeks else 1
    return {"season": season, "currentWeek": min(last_played + 1, total), "weeks": weeks}


def team_rows(all_units: dict, gp: dict, season: int, baselines: dict) -> list:
    """Team units paired with their Madden baselines, for learn.py."""
    return [{"id": f"{t}-{season}", "season": season, "group": unit, "M": baselines.get(t, {}).get(unit),
             "games": gp[t], "cats": {c["id"]: {**c, "qualified": gp[t] > 0} for c in cats}}
            for t, units in all_units.items() for unit, cats in units.items()]


def model_report(model, groups: dict) -> dict:
    """How well stats explain Madden, per position/unit, saved for reference."""
    out = {}
    for group, cats in groups.items():
        fit = model.group_fit.get(group, {})
        out[group] = {
            "r2": None if fit.get("r2") is None else round(fit["r2"], 2), "players": fit.get("n"),
            "topStats": fit.get("top", []),
            "categories": {c: {"r2": None if model.cat_fit.get((group, c), {}).get("r2") is None
                               else round(model.cat_fit[(group, c)]["r2"], 2),
                               "learned": model.learned.get((group, c), False),
                               "weights": {k: round(v, 3) for k, v in model.weights.get((group, c), {}).items() if v > 0}}
                           for c in cats},
        }
    return out


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def num(series) -> float:
    """Sum a column, treating blanks as 0."""
    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def div(a, b):
    return a / b if b else None


def mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()) if len(s) else None


def stat(id, label, value, fmt="d1", better="high", hint=None, display=None):
    """One row in a category. `better` says whether a high or low number is good
    (used for ranking); None means the stat isn't ranked."""
    if value is not None and isinstance(value, float) and math.isnan(value):
        value = None
    return {
        "id": id,
        "label": label,
        "value": value,
        "fmt": fmt,
        "better": better,
        "hint": hint,
        "display": display,
    }


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
    if fmt == "time":
        m, s = divmod(int(round(v)), 60)
        return f"{m}:{s:02d}"
    return str(v)


HINTS = {
    "epa": "Expected Points Added: how much each play changed the team's chances "
           "of scoring, on average. 0 is average; positive is good for the offense.",
    "epa_def": "Expected Points Added allowed per play. Lower (more negative) means "
               "the defense is better at stopping drives.",
    "success": "Share of plays that kept the offense 'on schedule' (gained enough "
               "yards for the down and distance).",
    "red_zone": "When the offense got inside the opponent's 20-yard line, how often "
                "the drive ended in a touchdown.",
    "net_ypa": "Passing yards per dropback, after subtracting yards lost to sacks.",
    "adot": "Average depth of target: how far downfield passes travel in the air.",
    "net_punt": "Punt distance minus the return and touchback yards.",
}


# --------------------------------------------------------------------------
# Stat calculations
# --------------------------------------------------------------------------

def scrimmage_numbers(p: pd.DataFrame) -> dict:
    """Raw numbers from a set of offensive plays (runs and passes). Used for a
    team's own offense AND for what its defense allowed."""
    passes = p[p.play_type == "pass"]
    runs = p[p.play_type == "run"]
    att = num(passes.complete_pass) + num(passes.incomplete_pass) + num(passes.interception)
    sacks = num(passes.sack)
    sack_yds = -num(passes.loc[passes.sack == 1, "yards_gained"])
    gross = num(passes.passing_yards)
    dropbacks = p[p.qb_dropback == 1]
    designed_runs = p[p.rush == 1]
    targets = passes[(passes.sack != 1) & passes.air_yards.notna()]
    return {
        "plays": len(p),
        "yards": num(p.yards_gained),
        "epa": mean(p.epa),
        "success": mean(p.success),
        "att": att,
        "cmp": num(passes.complete_pass),
        "gross_pass": gross,
        "net_pass": gross - sack_yds,
        "pass_td": num(passes.pass_touchdown),
        "ints": num(passes.interception),
        "sacks": sacks,
        "sack_yds": sack_yds,
        "dropbacks": len(dropbacks),
        "epa_db": mean(dropbacks.epa),
        "explosive_pass": int((pd.to_numeric(passes.passing_yards, errors="coerce") >= 20).sum()),
        "adot": mean(targets.air_yards),
        "yac": num(passes.yards_after_catch),
        "rush_att": len(runs),
        "rush_yds": num(runs.yards_gained),
        "rush_td": num(runs.rush_touchdown),
        "rush_epa": mean(designed_runs.epa),
        "rush_success": mean(designed_runs.success),
        "explosive_run": int((runs.yards_gained >= 10).sum()),
        "stuffed": div(int((designed_runs.yards_gained <= 0).sum()), len(designed_runs)),
        "fumbles_lost": num(p.fumble_lost),
        "qb_hits": num(p.qb_hit),
        "tfl": num(p.tackled_for_loss),
    }


def red_zone(p: pd.DataFrame):
    drives = p.groupby(["game_id", "fixed_drive"]).agg(
        closest=("yardline_100", "min"), result=("fixed_drive_result", "first")
    )
    rz = drives[drives.closest <= 20]
    return len(rz), int((rz.result == "Touchdown").sum())


def time_of_possession(p: pd.DataFrame):
    drives = p.drop_duplicates(["game_id", "fixed_drive"])["drive_time_of_possession"].dropna()

    def secs(s):
        try:
            m, sec = str(s).split(":")
            return int(m) * 60 + int(sec)
        except ValueError:
            return 0

    return float(drives.map(secs).sum())


def down_rate(p: pd.DataFrame, which: str):
    conv = num(p[f"{which}_down_converted"])
    fail = num(p[f"{which}_down_failed"])
    return conv, conv + fail


def frac_display(made, att):
    pct = f" ({made / att * 100:.0f}%)" if att else ""
    return f"{int(made)}/{int(att)}{pct}"


# --------------------------------------------------------------------------
# Leaders (top players in a category)
# --------------------------------------------------------------------------

class People:
    def __init__(self, roster: pd.DataFrame, pbp: pd.DataFrame):
        r = roster.dropna(subset=["gsis_id"]).sort_values("week").drop_duplicates("gsis_id", keep="last")
        self.info = r.set_index("gsis_id")[["full_name", "position", "headshot_url", "jersey_number"]].to_dict("index")
        # Fallback names straight from the play-by-play (e.g. "P.Mahomes").
        self.short = {}
        for col in [c for c in pbp.columns if c.endswith("_player_id")]:
            name_col = col.replace("_player_id", "_player_name")
            if name_col in pbp.columns:
                pairs = pbp[[col, name_col]].dropna().drop_duplicates(col)
                self.short.update(dict(zip(pairs[col], pairs[name_col])))

    def card(self, pid, line, value):
        i = self.info.get(pid, {})
        headshot = i.get("headshot_url")
        jersey = i.get("jersey_number")
        return {
            "id": pid,
            "name": i.get("full_name") or self.short.get(pid, "Unknown"),
            "pos": i.get("position") if isinstance(i.get("position"), str) else None,
            "jersey": int(jersey) if isinstance(jersey, (int, float)) and not math.isnan(jersey) else None,
            "headshot": headshot if isinstance(headshot, str) else None,
            "line": line,
            "value": value,
        }


def top(people, df, key, sort_col, line_fn, n=3):
    if df.empty:
        return []
    df = df.dropna(subset=[key])
    df = df[df[sort_col] > 0].sort_values(sort_col, ascending=False).head(n)
    return [people.card(row[key], line_fn(row), float(row[sort_col])) for _, row in df.iterrows()]


def stack(frames):
    """Combine several (player_id, credit) frames into one total per player."""
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["pid", "v"])
    return pd.concat(frames).groupby("pid", as_index=False)["v"].sum()


def credit(df, col, amount=1.0, team_col=None, team=None):
    sub = df[df[col].notna()]
    if team_col:
        sub = sub[sub[team_col] == team]
    return pd.DataFrame({"pid": sub[col], "v": amount})


# --------------------------------------------------------------------------
# Building one team
# --------------------------------------------------------------------------

def build_team(t, pbp, scrim, games_played, sched, people):
    off_p = scrim[scrim.posteam == t]
    def_p = scrim[scrim.defteam == t]
    o = scrimmage_numbers(off_p)
    d = scrimmage_numbers(def_p)
    gp = games_played

    pf = float(sched.pf.sum())
    pa = float(sched.pa.sum())

    o_rz, o_rz_td = red_zone(off_p)
    d_rz, d_rz_td = red_zone(def_p)
    o3, o3a = down_rate(pbp[pbp.posteam == t], "third")
    d3, d3a = down_rate(pbp[pbp.defteam == t], "third")
    o4, o4a = down_rate(pbp[pbp.posteam == t], "fourth")
    d4, d4a = down_rate(pbp[pbp.defteam == t], "fourth")

    non_st = pbp[(pbp.special_teams_play != 1) & (pbp.penalty == 1) & (pbp.penalty_team == t)]
    off_pen = non_st[non_st.posteam == t]
    def_pen = non_st[non_st.defteam == t]

    first_downs = num(pbp.loc[pbp.posteam == t, "first_down"])
    first_downs_allowed = num(pbp.loc[pbp.defteam == t, "first_down"])
    top_secs = time_of_possession(off_p)

    def_tds = int(((scrim.defteam == t) & (scrim.td_team == t)).sum())

    # ---------------- Offense ----------------
    o_pass = off_p[off_p.play_type == "pass"]
    o_run = off_p[off_p.play_type == "run"]

    passers = o_pass.groupby("passer_player_id").agg(
        cmp=("complete_pass", "sum"), inc=("incomplete_pass", "sum"), ints=("interception", "sum"),
        yds=("passing_yards", "sum"), td=("pass_touchdown", "sum"),
    ).reset_index()
    passers["att"] = passers.cmp + passers.inc + passers.ints
    rushers = o_run.groupby("rusher_player_id").agg(
        att=("play_id", "count"), yds=("yards_gained", "sum"), td=("rush_touchdown", "sum"),
    ).reset_index()
    targeted = o_pass[o_pass.receiver_player_id.notna()]
    receivers = targeted.groupby("receiver_player_id").agg(
        tgt=("play_id", "count"), rec=("complete_pass", "sum"),
        yds=("receiving_yards", "sum"), td=("pass_touchdown", "sum"),
    ).reset_index()

    offense = [
        {
            "id": "overview", "label": "Overview",
            "blurb": "The big picture: how much this offense scores and moves the ball.",
            "stats": [
                stat("ppg", "Points per game", div(pf, gp)),
                stat("ypg", "Yards per game", div(o["yards"], gp)),
                stat("ypp", "Yards per play", div(o["yards"], o["plays"]), "d2"),
                stat("epa", "EPA per play", o["epa"], "epa", hint=HINTS["epa"]),
                stat("success", "Success rate", o["success"], "pct", hint=HINTS["success"]),
                stat("to", "Turnovers", o["ints"] + o["fumbles_lost"], "int", "low",
                     hint="Interceptions thrown plus fumbles lost."),
                stat("top", "Time of possession / game", div(top_secs, gp), "time"),
            ],
            "leaders": [],
        },
        {
            "id": "passing", "label": "Passing",
            "blurb": "Throwing the ball: volume, accuracy, efficiency and protection.",
            "stats": [
                stat("pass_ypg", "Passing yards per game", div(o["net_pass"], gp),
                     hint="Net passing yards (sack yardage subtracted)."),
                stat("cmp_pct", "Completion %", div(o["cmp"], o["att"]), "pct",
                     display=f"{fmt_value(div(o['cmp'], o['att']), 'pct')}  ({int(o['cmp'])}/{int(o['att'])})"),
                stat("net_ypa", "Net yards per attempt", div(o["net_pass"], o["att"] + o["sacks"]), "d2",
                     hint=HINTS["net_ypa"]),
                stat("pass_td", "Passing TDs", o["pass_td"], "int"),
                stat("ints", "Interceptions thrown", o["ints"], "int", "low"),
                stat("sacks", "Sacks taken", o["sacks"], "int", "low"),
                stat("epa_db", "EPA per dropback", o["epa_db"], "epa", hint=HINTS["epa"]),
                stat("explosive_pass", "Completions of 20+ yards", o["explosive_pass"], "int"),
            ],
            "leaders": [{
                "title": "Passing yards",
                "players": top(people, passers, "passer_player_id", "yds",
                               lambda r: f"{int(r.cmp)}/{int(r.att)} · {int(r.yds):,} yds · {int(r.td)} TD · {int(r.ints)} INT"),
            }],
        },
        {
            "id": "rushing", "label": "Rushing",
            "blurb": "Running the ball, including quarterback scrambles.",
            "stats": [
                stat("rush_ypg", "Rushing yards per game", div(o["rush_yds"], gp)),
                stat("ypc", "Yards per carry", div(o["rush_yds"], o["rush_att"]), "d2"),
                stat("rush_att_pg", "Carries per game", div(o["rush_att"], gp), better=None),
                stat("rush_td", "Rushing TDs", o["rush_td"], "int"),
                stat("explosive_run", "Runs of 10+ yards", o["explosive_run"], "int"),
                stat("stuffed", "Stuffed rate", o["stuffed"], "pct", "low",
                     hint="Share of designed runs stopped at or behind the line."),
                stat("rush_epa", "EPA per designed run", o["rush_epa"], "epa", hint=HINTS["epa"]),
                stat("rush_success", "Run success rate", o["rush_success"], "pct", hint=HINTS["success"]),
            ],
            "leaders": [{
                "title": "Rushing yards",
                "players": top(people, rushers, "rusher_player_id", "yds",
                               lambda r: f"{int(r.att)} car · {int(r.yds):,} yds · {int(r.td)} TD"),
            }],
        },
        {
            "id": "receiving", "label": "Receiving",
            "blurb": "Who's catching the ball and what they do after the catch.",
            "stats": [
                stat("rec_pg", "Receptions per game", div(o["cmp"], gp), better=None),
                stat("adot", "Avg. depth of target", o["adot"], "d1", better=None, hint=HINTS["adot"]),
                stat("yac_pg", "Yards after catch per game", div(o["yac"], gp)),
                stat("ypr", "Yards per reception", div(o["gross_pass"], o["cmp"]), "d1"),
            ],
            "leaders": [{
                "title": "Receiving yards",
                "players": top(people, receivers, "receiver_player_id", "yds",
                               lambda r: f"{int(r.rec)} rec ({int(r.tgt)} tgt) · {int(r.yds):,} yds · {int(r.td)} TD", n=5),
            }],
        },
        {
            "id": "situational", "label": "Situational",
            "blurb": "Clutch downs and scoring chances.",
            "stats": [
                stat("third", "3rd down conversion %", div(o3, o3a), "pct",
                     display=f"{fmt_value(div(o3, o3a), 'pct')}  ({int(o3)}/{int(o3a)})"),
                stat("fourth", "4th down conversion %", div(o4, o4a), "pct",
                     display=f"{fmt_value(div(o4, o4a), 'pct')}  ({int(o4)}/{int(o4a)})"),
                stat("rz", "Red zone TD %", div(o_rz_td, o_rz), "pct", hint=HINTS["red_zone"],
                     display=f"{fmt_value(div(o_rz_td, o_rz), 'pct')}  ({o_rz_td}/{o_rz})"),
                stat("fd_pg", "First downs per game", div(first_downs, gp)),
                stat("pen_pg", "Penalties per game (on offense)", div(len(off_pen), gp), "d1", "low"),
                stat("pen_yds_pg", "Penalty yards per game (on offense)", div(num(off_pen.penalty_yards), gp), "d1", "low"),
            ],
            "leaders": [],
        },
    ]

    # ---------------- Defense ----------------
    sacks_df = stack([
        credit(def_p, "sack_player_id"),
        credit(def_p, "half_sack_1_player_id", 0.5),
        credit(def_p, "half_sack_2_player_id", 0.5),
    ])
    ints_df = stack([credit(def_p, "interception_player_id")])
    tackle_cols = [("solo_tackle_1_player_id", "solo_tackle_1_team"), ("solo_tackle_2_player_id", "solo_tackle_2_team"),
                   ("assist_tackle_1_player_id", "assist_tackle_1_team"), ("assist_tackle_2_player_id", "assist_tackle_2_team"),
                   ("assist_tackle_3_player_id", "assist_tackle_3_team"), ("assist_tackle_4_player_id", "assist_tackle_4_team"),
                   ("tackle_with_assist_1_player_id", "tackle_with_assist_1_team"),
                   ("tackle_with_assist_2_player_id", "tackle_with_assist_2_team")]
    tackles_df = stack([credit(def_p, c, 1.0, tc, t) for c, tc in tackle_cols])
    tfl_df = stack([credit(def_p, "tackle_for_loss_1_player_id"), credit(def_p, "tackle_for_loss_2_player_id", 1.0)])

    def simple(df, unit):
        # "1 sack", "2.5 sacks"
        return lambda r: f"{r.v:g} {unit if r.v == 1 or unit.isupper() else unit + 's'}"

    defense = [
        {
            "id": "overview", "label": "Overview",
            "blurb": "How well this defense keeps opponents off the scoreboard.",
            "stats": [
                stat("papg", "Points allowed per game", div(pa, gp), "d1", "low"),
                stat("yapg", "Yards allowed per game", div(d["yards"], gp), "d1", "low"),
                stat("ypp", "Yards allowed per play", div(d["yards"], d["plays"]), "d2", "low"),
                stat("epa", "EPA allowed per play", d["epa"], "epa", "low", hint=HINTS["epa_def"]),
                stat("success", "Success rate allowed", d["success"], "pct", "low", hint=HINTS["success"]),
                stat("takeaways", "Takeaways", d["ints"] + d["fumbles_lost"], "int",
                     hint="Interceptions plus fumbles recovered from the opponent's offense."),
                stat("def_td", "Defensive TDs", def_tds, "int"),
            ],
            "leaders": [{
                "title": "Tackles",
                "players": top(people, tackles_df, "pid", "v", simple(tackles_df, "tackle"), n=5),
            }],
        },
        {
            "id": "pass_defense", "label": "Pass Defense",
            "blurb": "Stopping the pass: coverage and pressure on the quarterback.",
            "stats": [
                stat("pass_ypg", "Passing yards allowed per game", div(d["net_pass"], gp), "d1", "low"),
                stat("cmp_pct", "Completion % allowed", div(d["cmp"], d["att"]), "pct", "low"),
                stat("net_ypa", "Net yards per attempt allowed", div(d["net_pass"], d["att"] + d["sacks"]), "d2", "low",
                     hint=HINTS["net_ypa"]),
                stat("pass_td", "Passing TDs allowed", d["pass_td"], "int", "low"),
                stat("ints", "Interceptions", d["ints"], "int"),
                stat("sacks", "Sacks", d["sacks"], "int"),
                stat("sack_rate", "Sack rate", div(d["sacks"], d["dropbacks"]), "pct",
                     hint="Share of opponent dropbacks that ended in a sack."),
                stat("qb_hits", "QB hits", d["qb_hits"], "int"),
                stat("epa_db", "EPA allowed per dropback", d["epa_db"], "epa", "low", hint=HINTS["epa_def"]),
            ],
            "leaders": [
                {"title": "Sacks", "players": top(people, sacks_df, "pid", "v", simple(sacks_df, "sack"))},
                {"title": "Interceptions", "players": top(people, ints_df, "pid", "v", simple(ints_df, "INT"))},
            ],
        },
        {
            "id": "run_defense", "label": "Run Defense",
            "blurb": "Stopping the run.",
            "stats": [
                stat("rush_ypg", "Rushing yards allowed per game", div(d["rush_yds"], gp), "d1", "low"),
                stat("ypc", "Yards per carry allowed", div(d["rush_yds"], d["rush_att"]), "d2", "low"),
                stat("rush_td", "Rushing TDs allowed", d["rush_td"], "int", "low"),
                stat("explosive_run", "Runs of 10+ allowed", d["explosive_run"], "int", "low"),
                stat("stuffed", "Stuff rate", d["stuffed"], "pct",
                     hint="Share of designed runs stopped at or behind the line."),
                stat("tfl", "Tackles for loss", d["tfl"], "int"),
                stat("rush_epa", "EPA allowed per designed run", d["rush_epa"], "epa", "low", hint=HINTS["epa_def"]),
            ],
            "leaders": [
                {"title": "Tackles for loss", "players": top(people, tfl_df, "pid", "v", simple(tfl_df, "TFL"))},
            ],
        },
        {
            "id": "situational", "label": "Situational",
            "blurb": "Getting off the field on big downs and in the red zone.",
            "stats": [
                stat("third", "3rd down % allowed", div(d3, d3a), "pct", "low",
                     display=f"{fmt_value(div(d3, d3a), 'pct')}  ({int(d3)}/{int(d3a)})"),
                stat("fourth", "4th down % allowed", div(d4, d4a), "pct", "low",
                     display=f"{fmt_value(div(d4, d4a), 'pct')}  ({int(d4)}/{int(d4a)})"),
                stat("rz", "Red zone TD % allowed", div(d_rz_td, d_rz), "pct", "low", hint=HINTS["red_zone"],
                     display=f"{fmt_value(div(d_rz_td, d_rz), 'pct')}  ({d_rz_td}/{d_rz})"),
                stat("fd_pg", "First downs allowed per game", div(first_downs_allowed, gp), "d1", "low"),
                stat("pen_pg", "Penalties per game (on defense)", div(len(def_pen), gp), "d1", "low"),
                stat("pen_yds_pg", "Penalty yards per game (on defense)", div(num(def_pen.penalty_yards), gp), "d1", "low"),
            ],
            "leaders": [],
        },
    ]

    # ---------------- Special teams ----------------
    # Note: on kickoffs nflverse lists the RECEIVING team as `posteam`.
    fg = pbp[(pbp.field_goal_attempt == 1) & (pbp.posteam == t)]
    fg_made = fg[fg.field_goal_result == "made"]
    xp = pbp[(pbp.extra_point_attempt == 1) & (pbp.posteam == t)]
    xp_made = int((xp.extra_point_result == "good").sum())

    def fg_range(lo, hi):
        r = fg[(fg.kick_distance >= lo) & (fg.kick_distance <= hi)]
        m = int((r.field_goal_result == "made").sum())
        return m, len(r)

    short_m, short_a = fg_range(0, 39)
    mid_m, mid_a = fg_range(40, 49)
    long_m, long_a = fg_range(50, 99)

    punts = pbp[(pbp.punt_attempt == 1) & (pbp.posteam == t)]
    n_punts = len(punts)
    net_punt = div(num(punts.kick_distance) - num(punts.return_yards) - 20 * num(punts.touchback), n_punts)

    kr = pbp[(pbp.kickoff_attempt == 1) & (pbp.posteam == t) & pbp.kickoff_returner_player_id.notna()]
    pr = pbp[(pbp.punt_attempt == 1) & (pbp.defteam == t) & pbp.punt_returner_player_id.notna()]
    kr_allowed = pbp[(pbp.kickoff_attempt == 1) & (pbp.defteam == t) & pbp.kickoff_returner_player_id.notna()]
    pr_allowed = punts[punts.punt_returner_player_id.notna()]
    ret_td = int(((pbp.special_teams_play == 1) & (pbp.return_team == t) & (pbp.return_touchdown == 1)).sum())
    ret_td_allowed = int(((pbp.special_teams_play == 1) & (pbp.return_team != t) & pbp.return_team.notna()
                          & ((pbp.posteam == t) | (pbp.defteam == t)) & (pbp.return_touchdown == 1)).sum())

    kickers = fg.groupby("kicker_player_id").agg(
        att=("play_id", "count"), made=("field_goal_result", lambda s: int((s == "made").sum())),
        long=("kick_distance", lambda s: 0),
    ).reset_index()
    if not kickers.empty:
        longs = fg_made.groupby("kicker_player_id").kick_distance.max()
        kickers["long"] = kickers.kicker_player_id.map(longs).fillna(0)
    punters = punts.groupby("punter_player_id").agg(n=("play_id", "count"), avg=("kick_distance", "mean")).reset_index()
    kr_people = kr.groupby("kickoff_returner_player_id").agg(n=("play_id", "count"), yds=("return_yards", "sum")).reset_index()
    pr_people = pr.groupby("punt_returner_player_id").agg(n=("play_id", "count"), yds=("return_yards", "sum")).reset_index()

    special = [
        {
            "id": "kicking", "label": "Kicking",
            "blurb": "Field goals and extra points.",
            "stats": [
                stat("fg_pct", "Field goal %", div(len(fg_made), len(fg)), "pct",
                     display=frac_display(len(fg_made), len(fg))),
                stat("fg_0_39", "FG under 40 yards", div(short_m, short_a), "pct",
                     display=frac_display(short_m, short_a)),
                stat("fg_40_49", "FG 40–49 yards", div(mid_m, mid_a), "pct",
                     display=frac_display(mid_m, mid_a)),
                stat("fg_50", "FG 50+ yards", div(long_m, long_a), "pct",
                     display=frac_display(long_m, long_a)),
                stat("fg_long", "Longest field goal", float(fg_made.kick_distance.max()) if len(fg_made) else None, "int"),
                stat("xp_pct", "Extra point %", div(xp_made, len(xp)), "pct", display=frac_display(xp_made, len(xp))),
            ],
            "leaders": [{
                "title": "Kicker",
                "players": top(people, kickers, "kicker_player_id", "att",
                               lambda r: f"{int(r.made)}/{int(r.att)} FG · long {int(r.long)}", n=2),
            }],
        },
        {
            "id": "punting", "label": "Punting",
            "blurb": "Flipping field position with punts.",
            "stats": [
                stat("punts_pg", "Punts per game", div(n_punts, gp), "d1", "low",
                     hint="Fewer punts usually means the offense is moving the ball."),
                stat("gross", "Gross punt average", mean(punts.kick_distance), "d1"),
                stat("net", "Net punt average", net_punt, "d1", hint=HINTS["net_punt"]),
                stat("in20", "Punts inside the 20", num(punts.punt_inside_twenty), "int"),
                stat("tb", "Touchbacks", num(punts.touchback), "int", "low"),
            ],
            "leaders": [{
                "title": "Punter",
                "players": top(people, punters, "punter_player_id", "n",
                               lambda r: f"{int(r.n)} punts · {r.avg:.1f} avg", n=2),
            }],
        },
        {
            "id": "returns", "label": "Returns",
            "blurb": "Bringing back kickoffs and punts.",
            "stats": [
                stat("kr_avg", "Kick return average", mean(kr.return_yards), "d1"),
                stat("kr_n", "Kickoffs returned", len(kr), "int", better=None),
                stat("pr_avg", "Punt return average", mean(pr.return_yards), "d1"),
                stat("pr_n", "Punts returned", len(pr), "int", better=None),
                stat("ret_td", "Return TDs", ret_td, "int"),
            ],
            "leaders": [
                {"title": "Kick returns", "players": top(people, kr_people, "kickoff_returner_player_id", "yds",
                                                         lambda r: f"{int(r.n)} ret · {r.yds / r.n:.1f} avg", n=2)},
                {"title": "Punt returns", "players": top(people, pr_people, "punt_returner_player_id", "yds",
                                                         lambda r: f"{int(r.n)} ret · {r.yds / r.n:.1f} avg", n=2)},
            ],
        },
        {
            "id": "coverage", "label": "Coverage",
            "blurb": "Stopping the other team's returners.",
            "stats": [
                stat("kr_allowed", "Kick return avg. allowed", mean(kr_allowed.return_yards), "d1", "low"),
                stat("pr_allowed", "Punt return avg. allowed", mean(pr_allowed.return_yards), "d1", "low"),
                stat("ret_td_allowed", "Return TDs allowed", ret_td_allowed, "int", "low"),
            ],
            "leaders": [],
        },
    ]

    return {"offense": offense, "defense": defense, "special": special}


# --------------------------------------------------------------------------
# Ranking + output
# --------------------------------------------------------------------------

def add_ranks(all_units: dict):
    """all_units[team][unit] = [categories]. Adds rank (1-32) and league average."""
    sample = next(iter(all_units.values()))
    for unit, cats in sample.items():
        for ci, cat in enumerate(cats):
            for si, s in enumerate(cat["stats"]):
                vals = {t: u[unit][ci]["stats"][si]["value"] for t, u in all_units.items()}
                present = pd.Series({t: v for t, v in vals.items() if v is not None}, dtype=float)
                avg = float(present.mean()) if len(present) else None
                ranks = {}
                if s["better"] and len(present):
                    ranks = present.rank(ascending=(s["better"] == "low"), method="min").astype(int).to_dict()
                for t, u in all_units.items():
                    row = u[unit][ci]["stats"][si]
                    row["rank"] = ranks.get(t)
                    row["leagueAvg"] = fmt_value(avg, row["fmt"])
                    if row["display"] is None:
                        row["display"] = fmt_value(row["value"], row["fmt"])


def recent_text(played) -> str:
    weeks = [str(int(w)) for w in played.sort_values("week").week.tail(RECENT_GAMES)]
    n = len(weeks)
    return f"Recent form uses the team's last {n} game{'s' if n != 1 else ''} (week{'s' if n != 1 else ''} {', '.join(weeks)})."


def to_plain(o):
    """Turn numpy numbers/booleans into plain Python ones so they can be saved as JSON."""
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(f"Can't save {type(o).__name__} as JSON")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season(date.today()))
    args = ap.parse_args()
    season = args.season
    print(f"Building data for the {season} season")

    pbp, games, teams, roster, modified, extra = load(season)

    # Regular season only for now (playoffs can be added later).
    pbp = pbp[pbp.season_type == "REG"].copy()
    sched = games[(games.season == season) & (games.game_type == "REG")].copy()

    team_ids = sorted(set(sched.home_team) | set(sched.away_team))
    teams = teams[teams.team_abbr.isin(team_ids)].drop_duplicates("team_abbr").set_index("team_abbr")
    scrim = pbp[pbp.play_type.isin(["pass", "run"])]
    people = People(roster, pbp)

    # Only count games that have play-by-play data so per-game stats line up.
    pbp_games = set(pbp.game_id.unique())

    def team_schedule(t):
        h = sched[sched.home_team == t].assign(opp=lambda x: x.away_team, home=True,
                                                pf=lambda x: x.home_score, pa=lambda x: x.away_score)
        a = sched[sched.away_team == t].assign(opp=lambda x: x.home_team, home=False,
                                                pf=lambda x: x.away_score, pa=lambda x: x.home_score)
        return pd.concat([h, a]).sort_values("week")

    all_units, schedules, games_played, played_by_team = {}, {}, {}, {}
    for t in team_ids:
        s = team_schedule(t)
        schedules[t] = s
        played = s[s.pf.notna() & s.game_id.isin(pbp_games)]
        games_played[t] = len(played)
        played_by_team[t] = played
        all_units[t] = build_team(t, pbp, scrim, len(played), played, people)

    add_ranks(all_units)

    # ---- Ratings ----
    # Recent form: the same team stats, using only each team's last few games.
    recent_units, recent_gp = {}, {}
    for t in team_ids:
        last = played_by_team[t].sort_values("week").tail(RECENT_GAMES)
        ids = set(last.game_id)
        rp = pbp[pbp.game_id.isin(ids)]
        recent_units[t] = build_team(t, rp, rp[rp.play_type.isin(["pass", "run"])], len(last), last, people)
        recent_gp[t] = len(last)

    # Opponent strength + injuries.
    off_epa, def_epa = team_strength(scrim)
    team_games = {t: [(int(g.week), t, g.opp) for g in played_by_team[t].itertuples()] for t in team_ids}
    season_start = str(sched.gameday.min())
    starters = expected_starters(extra["depth"], season_start)
    missing = unavailable(extra["injuries"], extra["weekly_rosters"])
    weeks = sorted({int(w) for w in pbp.week.unique()})
    ctx = Context(team_games, off_epa, def_epa, burdens(starters, missing, weeks))
    team_ctx = team_contexts(ctx)

    # ---- Madden baselines ----
    madden_table = load_madden(roster, teams.reset_index())
    madden = dict(zip(madden_table.gsis_id, madden_table.madden.astype(float)))
    pos_group = {r.gsis_id: GROUP_OF.get(r.position) for r in roster.itertuples() if isinstance(r.gsis_id, str)}
    by_group = {}
    for pid, m in madden.items():
        by_group.setdefault(pos_group.get(pid), []).append(m)
    est = {g: float(pd.Series(v).quantile(MADDEN["noMaddenPercentile"] / 100)) for g, v in by_group.items() if g}
    fallback = {pid: est.get(pos_group.get(pid), 65.0) for ps in starters.values() for pid, _, _ in ps}
    baselines = team_baselines(starters, madden, fallback)

    # ---- Last season, to learn from ----
    last = load_last_season(season - 1)
    lpbp = last["pbp"][last["pbp"].season_type == "REG"]
    lsched = games[(games.season == season - 1) & (games.game_type == "REG")]
    lscrim = lpbp[lpbp.play_type.isin(["pass", "run"])]
    lpeople = People(last["roster"], lpbp)
    last_units, last_gp, last_games = {}, {}, {}
    for t in team_ids:
        h = lsched[lsched.home_team == t].assign(opp=lambda x: x.away_team, pf=lambda x: x.home_score, pa=lambda x: x.away_score)
        a = lsched[lsched.away_team == t].assign(opp=lambda x: x.home_team, pf=lambda x: x.away_score, pa=lambda x: x.home_score)
        played = pd.concat([h, a])
        played = played[played.pf.notna() & played.game_id.isin(set(lpbp.game_id))]
        last_gp[t] = len(played)
        last_units[t] = build_team(t, lpbp, lscrim, len(played), played, lpeople)
    add_ranks(last_units)

    # ---- Team ratings: learn, then rate ----
    team_model = fit(team_rows(last_units, last_gp, season - 1, baselines) +
                     team_rows(all_units, games_played, season, baselines),
                     lambda unit, cid: weights_for("team", "stats", unit, cid))
    unit_cats = {u: [c["id"] for c in cats] for u, cats in all_units[team_ids[0]].items()}
    fit_groups(team_model, team_rows(last_units, last_gp, season - 1, baselines) +
               team_rows(all_units, games_played, season, baselines), unit_cats, {})
    set_trust(team_model, MADDEN["minTrust"]["teams"])
    team_ratings = rate_teams(team_model, season, all_units, recent_units, games_played, team_ctx, baselines)
    strip_fmt(all_units)
    strip_fmt(last_units)

    last_players = season_players(last["weekly"], last["snaps"], last["roster"], last_gp, last_units)
    last_rows = training_rows(last_players, season - 1, madden)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "teams").mkdir(exist_ok=True)
    # Use nflverse's file date (not the clock) so files only change when the data does.
    try:
        updated = parsedate_to_datetime(modified).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        updated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    through_week = int(pbp.week.max()) if len(pbp) else 0

    team_info = {t: {"name": teams.loc[t].team_name, "color": teams.loc[t].team_color,
                     "color2": teams.loc[t].team_color2, "logo": teams.loc[t].team_logo_espn} for t in team_ids}
    player_docs, rosters, player_model = build_players(extra["weekly"], extra["snaps"], extra["depth"], roster,
                                                       team_info, games_played, date.today(), ctx, all_units,
                                                       season, madden, last_rows)
    (OUT_DIR / "ratings_model.json").write_text(json.dumps({
        "teams": model_report(team_model, unit_cats),
        "players": model_report(player_model, {g: core + opt for g, (core, opt) in CATEGORIES.items()}),
        "maddenMatched": len(madden),
        "trust": {"teams": team_model.trust, "players": player_model.trust},
    }, indent=1, default=to_plain))

    # ---- Win probability: every game this season and last, then an honest test ----
    out_now = unavailable_by_week(extra["injuries"], extra["weekly_rosters"])
    all_reg = games[games.game_type == "REG"]
    info_now = player_info(roster, madden, starters)
    games_now, snaps_now = winprob_games(season, sched, pbp, team_ids, people, baselines, team_model, out_now,
                              info_now,
                              last_season_margins(all_reg[all_reg.season == season - 1]))
    # Last season: no preseason Madden existed for it in our data, so every team starts even.
    flat = {t: {k: MADDEN["teamBaseline"]["mean"] for k in (*UNIT_KEYS, "overall")} for t in team_ids}
    lstarters = expected_starters(last["depth"], str(lsched.gameday.min()))
    games_last, _ = winprob_games(season - 1, lsched, lpbp, team_ids, lpeople, flat, team_model,
                               unavailable_by_week(last["injuries"], last["weekly_rosters"]),
                               player_info(last["roster"], madden, lstarters),
                               last_season_margins(all_reg[all_reg.season == season - 2]))
    wp_report = backtest(games_last + games_now)
    (OUT_DIR / "winprob_report.json").write_text(json.dumps(wp_report, indent=1, default=to_plain))
    print("  win probability test:", json.dumps({k: v["model"]["accuracy"] for k, v in wp_report.items()
                                                 if isinstance(v, dict) and "model" in v}))

    # One file per game this season: pre-game win probability and why.
    game_docs = {r["id"]: game_doc(r) for r in games_now}
    games_dir = OUT_DIR / "games"
    games_dir.mkdir(exist_ok=True)
    for old in games_dir.glob("*.json"):
        old.unlink()
    for gid, gdoc in game_docs.items():
        (games_dir / f"{gid}.json").write_text(json.dumps(gdoc, separators=(",", ":"), default=to_plain))

    # Wins and losses in context become part of each team's overall rating.
    team_results_ctx = results_component(game_docs, team_ids)
    for t in team_ids:
        if team_ratings[t]["rt"]:
            team_ratings[t]["rt"]["res"] = team_results_ctx[t]["points"]

    # Team leader lists show each player's overall rating too.
    for units in all_units.values():
        for cats in units.values():
            for cat in cats:
                for leader in cat["leaders"]:
                    for pl in leader["players"]:
                        pl["rt"] = player_docs.get(pl["id"], {}).get("rt")

    # One file per player. Clear out old files first so released players don't linger.
    players_dir = OUT_DIR / "players"
    players_dir.mkdir(exist_ok=True)
    for old in players_dir.glob("*.json"):
        old.unlink()
    for pid, pdoc in player_docs.items():
        pdoc = {"season": season, "throughWeek": through_week, "updated": updated, **pdoc}
        (players_dir / f"{pid}.json").write_text(json.dumps(pdoc, separators=(",", ":"), default=to_plain))

    # A small list of every player, for searching (e.g. the Compare screen).
    player_index = sorted(
        ({"id": pid, "name": d["name"], "team": d["team"], "pos": d["pos"], "group": d["group"],
          "jersey": d["jersey"], "starter": d["starter"], "rt": d.get("rt")}
         for pid, d in player_docs.items()),
        key=lambda x: (x["name"], x["id"]))
    (OUT_DIR / "players.json").write_text(json.dumps(player_index, separators=(",", ":"), default=to_plain))

    index, team_docs = [], {}
    for t in team_ids:
        info = teams.loc[t]
        s = schedules[t]
        done = s[s.pf.notna()]
        w = int((done.pf > done.pa).sum())
        l = int((done.pf < done.pa).sum())
        tie = int((done.pf == done.pa).sum())
        record = f"{w}-{l}" + (f"-{tie}" if tie else "")
        team = {
            "rt": team_ratings[t]["rt"],
            "madden": baselines[t].get("overall"),
            "abbr": t,
            "name": info.team_name,
            "nickname": info.team_nick,
            "conference": info.team_conf,
            "division": info.team_division,
            "color": info.team_color,
            "color2": info.team_color2,
            "logo": info.team_logo_espn,
            "record": record,
        }
        index.append(team)
        games_out = [{
            "id": g.game_id,
            "week": int(g.week),
            "date": g.gameday,
            "opp": g.opp,
            "home": bool(g.home),
            "pf": None if pd.isna(g.pf) else int(g.pf),
            "pa": None if pd.isna(g.pa) else int(g.pa),
            "result": None if pd.isna(g.pf) else ("W" if g.pf > g.pa else "L" if g.pf < g.pa else "T"),
            # This team's chance to win, as the model saw it before kickoff.
            "wp": None if g.game_id not in game_docs else
            game_docs[g.game_id]["prob"]["home" if g.home else "away"],
        } for g in s.itertuples()]
        doc = {"season": season, "throughWeek": through_week, "updated": updated,
               "team": team, "games": games_out, "units": all_units[t], "roster": rosters.get(t, []),
               "unitRatings": team_ratings[t]["units"],
               "results": team_results_ctx[t],
               "context": {side: {"opp": c["opp"], "inj": c["inj"], "recent": recent_text(played_by_team[t])}
                           for side, c in team_ctx[t].items()}}
        (OUT_DIR / "teams" / f"{t}.json").write_text(json.dumps(doc, separators=(",", ":"), default=to_plain))
        team_docs[t] = doc

    # ---- Power rankings ----
    records = records_before(sched)
    current_rating = {t: blend_default(team_ratings[t]["rt"]) - team_ratings[t]["rt"].get("res", 0) for t in team_ids}
    league = league_components(games_now, team_ids, current_rating, snaps_now, out_now, info_now, records,
                               {t["abbr"]: t["record"] for t in index})
    rankings_doc = {"season": season, "throughWeek": through_week, "updated": updated, "league": league,
                    "units": unit_lists(team_docs, snaps_now, league["lastPlayedWeek"])}
    (OUT_DIR / "rankings.json").write_text(json.dumps(rankings_doc, separators=(",", ":"), default=to_plain))

    # ---- This season's schedule, week by week ----
    (OUT_DIR / "schedule.json").write_text(json.dumps(
        schedule_doc(sched, game_docs, records, league["lastPlayedWeek"], season), separators=(",", ":"),
        default=to_plain))

    (OUT_DIR / "teams.json").write_text(json.dumps(
        {"season": season, "throughWeek": through_week, "updated": updated, "teams": index},
        separators=(",", ":")))
    print(f"Wrote {len(index)} teams and {len(player_docs)} players through week {through_week} to {OUT_DIR}")


if __name__ == "__main__":
    main()
