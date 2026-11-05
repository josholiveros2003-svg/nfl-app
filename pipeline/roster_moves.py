"""
Keeps every player on the right team: trades, releases, waiver claims and signings, in season
and in the offseason.

nflverse's roster file is the base because it has the NFL ids all the stats use, but it lags.
Three signals are combined, and the newest information wins:

  1. A depth chart that just moved a player. Teams often update these before anything else, so
     if a player recently moved from team A's chart to team B's while ESPN's roster still says
     A (or nothing), he's on team B.
  2. ESPN's live rosters, for everyone else.
  3. Not on any ESPN roster: he's a free agent, unless nflverse and a current depth chart both
     still have him on the same team (ESPN's roster page sometimes misses a fresh waiver claim).

The changes are added as new rows marked as the newest "week", so all the code that reads "each
player's latest row" picks them up, while snap-count matching can still see his old team.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pandas as pd

from espn_live import app_team

# A depth chart move only overrides ESPN's roster this long; after that, a disagreement more
# likely means the depth chart is the stale one.
DEPTH_MOVE_DAYS = 14

LATEST_WEEK = 99
HAS_TEAM = {"ACT", "INA", "RES", "DEV", "EXE", "SUS"}
RESERVE_WORDS = ("reserve", "pup", "physically", "non-football", "nfi")
POSITION_FIX = {"PK": "K"}


def _espn_id(v) -> str | None:
    try:
        return str(int(float(v)))
    except (TypeError, ValueError):
        return None


def _name_key(name) -> str:
    return re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(name).lower()))


def _last_name(name) -> str:
    parts = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(name).lower()).split()
    return re.sub(r"[^a-z]", "", parts[-1]) if parts else ""


def match_ids(latest: pd.DataFrame, depth: pd.DataFrame, rosters: dict) -> dict:
    """{espn id: NFL id}. Many players have no ESPN id in nflverse's roster file, so also use
    the depth charts' ids, then name + birthdate, then last name + birthdate."""
    ids = {}
    for e, g in zip(latest.espn_id, latest.gsis_id):
        if _espn_id(e):
            ids[_espn_id(e)] = g
    d = depth.dropna(subset=["gsis_id", "espn_id"]).drop_duplicates("espn_id")
    for e, g in zip(d.espn_id, d.gsis_id):
        if _espn_id(e):
            ids.setdefault(_espn_id(e), g)

    def unique(keys, values):
        found = {}
        for k, g in zip(keys, values):
            found.setdefault(k, set()).add(g)
        return {k: next(iter(v)) for k, v in found.items() if len(v) == 1}

    births = latest.birth_date.astype(str).str[:10]
    by_name = unique(zip(latest.full_name.map(_name_key), births), latest.gsis_id)
    by_last = unique(zip(latest.full_name.map(_last_name), births), latest.gsis_id)
    for espn, p in rosters.items():
        if espn not in ids and p["birth"]:
            g = by_name.get((_name_key(p["name"]), p["birth"])) or by_last.get((_last_name(p["name"]), p["birth"]))
            if g:
                ids[espn] = g
    return ids


def _depth_now(depth: pd.DataFrame, live_depth: dict | None, ids: dict) -> dict:
    """{NFL id: [teams whose current depth chart lists him]}. Live if we have it, else nflverse's latest."""
    if live_depth:
        out = {}
        for espn, teams in live_depth.items():
            if espn in ids:
                out[ids[espn]] = teams
        return out
    d = depth.dropna(subset=["gsis_id"])
    d = d[d.dt == d.groupby("team").dt.transform("max")]
    out = {}
    for g, t in zip(d.gsis_id, d.team):
        teams = out.setdefault(g, [])
        if app_team(t) not in teams:
            teams.append(app_team(t))
    return out


def _depth_move(history: pd.DataFrame | None, team: str, cutoff: str, now: str) -> str | None:
    """If a player recently landed on this team's depth chart, the team he came from."""
    if history is None:
        return None
    other = history[history.team != team]
    if other.empty:
        return None
    previous = other.iloc[-1]
    arrived = history[(history["dt"] > previous["dt"]) & (history.team == team)]["dt"]
    first_seen = arrived.iloc[0] if len(arrived) else now  # only the live chart has him there so far
    return previous["team"] if first_seen >= cutoff else None


def _status(p: dict, old: str | None) -> str:
    """ESPN's list -> nflverse's status codes."""
    if p["group"] == "practiceSquad":
        return "DEV"
    if p["group"] == "suspended":
        return "SUS"
    # ESPN can keep an injured-reserve player in its regular offense/defense lists, with the
    # "Injured Reserve" label only on the player, so check the label on every list.
    if any(w in str(s).lower() for s in p["injuries"] for w in RESERVE_WORDS):
        return "RES"
    if p["group"] == "injuredReserveOrOut":
        return "RES" if old == "RES" else "ACT"
    return old if old in ("INA", "EXE") else "ACT"


def _new_player(espn: str, p: dict) -> dict:
    """A player nflverse doesn't list yet (a new signing or draft pick)."""
    return {
        "gsis_id": f"espn-{espn}", "espn_id": espn, "full_name": p["name"], "first_name": p["first"],
        "last_name": p["last"], "position": POSITION_FIX.get(p["pos"], p["pos"]), "depth_chart_position": None,
        "jersey_number": p["jersey"], "height": p["height"], "weight": p["weight"], "college": p["college"],
        "years_exp": p["years"], "birth_date": p["birth"], "headshot_url": p["headshot"],
    }


def apply_live_moves(roster: pd.DataFrame, depth: pd.DataFrame, live: dict | None,
                     now: datetime | None = None) -> tuple[pd.DataFrame, list[str]]:
    """The roster table with every known move added, plus a plain list of what changed."""
    now = now or datetime.now(timezone.utc)
    now_s, cutoff = (t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in (now, now - timedelta(days=DEPTH_MOVE_DAYS)))
    latest = roster.dropna(subset=["gsis_id"]).sort_values("week").drop_duplicates("gsis_id", keep="last")
    by_id = {r["gsis_id"]: r for r in latest.to_dict("records")}
    rosters = live["rosters"] if live else {}
    ids = match_ids(latest, depth, rosters)
    espn_of = {g: e for e, g in ids.items()}
    espn_by_gsis = {ids[e]: p for e, p in rosters.items() if e in ids}
    depth_now = _depth_now(depth, live["depth"] if live else None, ids)

    # Depth chart history, only for players whose chart disagrees with their roster team.
    def roster_team(g):
        if g in espn_by_gsis:
            return espn_by_gsis[g]["team"]
        r = by_id.get(g)
        return app_team(r["team"]) if r is not None and (not live) and r["status"] in HAS_TEAM else None

    disputed = {g for g, teams in depth_now.items() if roster_team(g) not in teams}
    h = depth[depth.gsis_id.isin(disputed)][["gsis_id", "dt", "team"]].drop_duplicates().sort_values("dt")
    h = h.assign(team=h.team.map(app_team))
    histories = {g: rows for g, rows in h.groupby("gsis_id")}

    rows, moves = [], []

    def record(g, base, team, status, why):
        r = by_id.get(g)
        if r is not None and app_team(r["team"]) == team and r["status"] == status:
            return
        rows.append({**base, "team": team, "status": status, "week": LATEST_WEEK})
        name = base.get("full_name")
        old = f"{app_team(r['team'])} ({r['status']})" if r is not None else "new"
        moves.append(f"{name}: {old} -> {team} ({status}), {why}")

    # Everyone on a list somewhere, including players nflverse doesn't have yet.
    for espn, p in rosters.items():
        if espn not in ids:
            record(f"espn-{espn}", _new_player(espn, p), p["team"], _status(p, None), "ESPN roster")

    for g, r in by_id.items():
        p = espn_by_gsis.get(g)
        teams = depth_now.get(g, [])
        now_team = app_team(r["team"]) if r["status"] in HAS_TEAM else None
        # 1. A depth chart just moved him, and his roster team is where he was, or nowhere.
        moved_to = None
        if g in disputed:
            for t in teams:
                came_from = _depth_move(histories.get(g), t, cutoff, now_s)
                if came_from and (p is None or p["team"] == came_from) and (p is not None or live or now_team == came_from):
                    moved_to = t
                    break
        if moved_to:
            record(g, r, moved_to, "ACT", "depth chart")
        elif p is not None:
            record(g, r, p["team"], _status(p, r["status"]), "ESPN roster")
        elif live and now_team and now_team not in teams:
            record(g, r, app_team(r["team"]), "CUT", "not on any roster")

    if not rows:
        return roster, moves
    return pd.concat([roster, pd.DataFrame(rows)], ignore_index=True), moves
