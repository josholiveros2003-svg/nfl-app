"""
Context for ratings: how tough the opponents were, and how injuries affected things.

Opponent strength
  Each team's offense and defense get an "EPA per play" grade from the season so far.
  For any set of games we average the grades of the opponents faced, e.g. an offense
  that played three great defenses had a tough schedule.

Injuries
  Before the season, each team's depth chart lists its expected starters. For every
  week we count how many of those starters were unavailable (listed Out or Doubtful
  on the injury report, or on injured reserve). A quarterback counts as 3 starters.
  Playing short-handed earns credit; facing short-handed opponents loses some.

Both are turned into "z-scores" (how many standard deviations above/below a typical
team's schedule), which the rating math converts into rating points.
"""

from __future__ import annotations

import pandas as pd

SIDES = ("offense", "defense", "special")


def team_strength(scrim: pd.DataFrame):
    """EPA per play for each offense, and EPA per play allowed by each defense."""
    off = scrim.groupby("posteam").epa.mean().to_dict()
    dfn = scrim.groupby("defteam").epa.mean().to_dict()
    return off, dfn


def _chart_starters(snap: pd.DataFrame) -> dict:
    """Who starts on one team's depth chart: {id: (side, weight, position)}."""
    slots = snap.groupby(["pos_grp", "pos_abb"]).pos_slot.nunique().rename("n_slots")
    snap = snap.join(slots, on=["pos_grp", "pos_abb"])
    snap = snap[snap.pos_rank <= snap.n_slots]
    starters = {}
    for r in snap.itertuples():
        if r.pos_grp == "Special Teams":
            if r.pos_abb not in ("PK", "P"):
                continue
            side = "special"
        elif str(r.pos_grp).endswith(" D"):
            side = "defense"
        else:
            side = "offense"
        weight = 3.0 if r.pos_abb == "QB" else 1.0
        starters.setdefault(r.gsis_id, (side, weight, r.pos_abb))
    return starters


def _preseason_chart(depth: pd.DataFrame, team: str, season_start: str) -> pd.DataFrame:
    """A team's last depth chart before Week 1 (or its earliest, if it has none)."""
    rows = depth[depth.team == team]
    pre = rows[rows.dt < season_start]
    return pre[pre.dt == pre.dt.max()] if len(pre) else rows[rows.dt == rows.dt.min()]


def expected_starters(depth: pd.DataFrame, season_start: str) -> dict:
    """Starters from each team's last depth chart before Week 1: {team: [(id, side, weight)]}."""
    d = depth.dropna(subset=["gsis_id"])
    return {team: [(pid, side, w) for pid, (side, w, _) in _chart_starters(_preseason_chart(d, team, season_start)).items()]
            for team in d.team.unique()}


# Depth chart spots -> position groups, so a new left guard can replace an old right guard.
_POSITION_GROUPS = {
    "QB": ("QB",), "RB": ("RB", "HB"), "FB": ("FB",), "WR": ("WR",), "TE": ("TE",),
    "OL": ("LT", "LG", "C", "RG", "RT", "T", "G", "OT", "OG"),
    "DL": ("LDE", "RDE", "DE", "LDT", "RDT", "DT", "NT", "DL"),
    "LB": ("LB", "SLB", "WLB", "MLB", "ILB", "OLB", "LILB", "RILB", "LOLB", "ROLB"),
    "DB": ("CB", "LCB", "RCB", "NB", "S", "FS", "SS", "DB"),
    "K": ("PK",), "P": ("P",),
}
_GROUP_OF_SPOT = {spot: g for g, spots in _POSITION_GROUPS.items() for spot in spots}


def starters_after_moves(depth: pd.DataFrame, season_start: str, madden: dict, hurt: set, team_now: dict | None = None,
                         moment: str | None = None) -> tuple[dict, dict]:
    """Each team's Week 1 starters, updated for players who changed teams since then.

    Only moves count. A starter who is merely hurt or benched stays on the list, because
    injuries have their own factor and benchings show up in the stats.
      - A starter on another team now (or, today, on no team) is out.
      - A starter who joined since Week 1 is in, replacing the lowest-rated starter at his
        position who has lost his starting spot. If that starter is only out hurt (hurt: set of
        ids), the newcomer has to be rated higher: a lesser fill-in shouldn't lower the team's
        baseline on top of what the injury factor already charges.
      - Anyone still missing is replaced by the next man on the depth chart.

    team_now: {id: team or None} for today's rosters. moment: for a past date instead, using
    the depth charts of that time, so past games are only judged on what was known then.
    Returns ({team: [(id, side, weight)]}, {team: {"in": [ids], "out": [ids]}})."""
    d = depth.dropna(subset=["gsis_id"])
    if moment is not None:
        d = d[d.dt < moment]
    full = depth.dropna(subset=["gsis_id"])
    charts = {t: rows[rows.dt == rows.dt.max()] for t, rows in d.groupby("team")}
    chart_team = {pid: t for t, rows in charts.items() for pid in rows.gsis_id}

    def team_of(pid, team):
        if team_now is not None:
            return team_now.get(pid)
        return chart_team.get(pid, team)  # off every chart usually means hurt, not gone

    now, moves = {}, {}
    for team in full.team.unique():
        pre_chart = _preseason_chart(full, team, season_start)
        pre = _chart_starters(pre_chart)
        chart = charts.get(team)
        current = _chart_starters(chart) if chart is not None else {}
        was_here = set(full[(full.team == team) & (full.dt < season_start)].gsis_id) | set(pre_chart.gsis_id)
        result = {pid: v for pid, v in pre.items() if team_of(pid, team) == team}
        gone = set(pre) - set(result)
        joined = {pid: v for pid, v in current.items()
                  if pid not in was_here and team_of(pid, team) == team and _GROUP_OF_SPOT.get(v[2])}
        if not gone and not joined:
            now[team] = [(pid, side, w) for pid, (side, w, _) in pre.items()]
            continue

        for group in _POSITION_GROUPS:
            spots = _POSITION_GROUPS[group]
            target = sum(1 for v in pre.values() if v[2] in spots)
            kept = [pid for pid in result if result[pid][2] in spots]
            arrivals = sorted((pid for pid, v in joined.items() if v[2] in spots), key=lambda p: -madden.get(p, 0))
            for pid in arrivals:
                if len(kept) >= target:
                    no_job = sorted((p for p in kept if p not in current), key=lambda p: madden.get(p, 0))
                    healthy = [p for p in no_job if p not in hurt]
                    worse_hurt = [p for p in no_job if p in hurt and madden.get(p, 0) < madden.get(pid, 0)]
                    out = (healthy or worse_hurt or [None])[0]
                    if out is None:
                        continue
                    kept.remove(out)
                    del result[out]
                kept.append(pid)
                result[pid] = joined[pid]
            # Too few: next man up, from the depth chart.
            if len(kept) < target and chart is not None:
                need = target - len(kept)
                rows = chart[chart.pos_abb.isin(spots)].sort_values(["pos_rank", "pos_slot"])
                for r in rows.itertuples():
                    if need and r.gsis_id not in result and team_of(r.gsis_id, team) == team:
                        side = "special" if group in ("K", "P") else "defense" if group in ("DL", "LB", "DB") else "offense"
                        result[r.gsis_id] = (side, 3.0 if group == "QB" else 1.0, r.pos_abb)
                        need -= 1
        now[team] = [(pid, side, w) for pid, (side, w, _) in result.items()]
        moves[team] = {"in": [p for p in result if p not in pre], "out": [p for p in pre if p not in result]}
    return now, moves


def unavailable(injuries: pd.DataFrame, weekly_rosters: pd.DataFrame) -> set:
    """(player id, week) pairs where a player was out injured."""
    inj = injuries[injuries.report_status.isin(["Out", "Doubtful"])]
    res = weekly_rosters[weekly_rosters.status == "RES"]
    pairs = set(zip(inj.gsis_id, inj.week)) | set(zip(res.gsis_id, res.week))
    return {(p, int(w)) for p, w in pairs if isinstance(p, str)}


def burdens(starters: dict, out: set, weeks) -> dict:
    """{(team, week): {side: weighted starters missing}}"""
    result = {}
    for team, players in starters.items():
        for w in weeks:
            b = {s: 0.0 for s in SIDES}
            for pid, side, weight in players:
                if (pid, w) in out:
                    b[side] += weight
            result[(team, w)] = b
    return result


class Context:
    """Opponent + injury context for any list of games, on one scale shared by teams and players."""

    def __init__(self, team_games: dict, off_epa: dict, def_epa: dict, burden: dict):
        self.off_epa, self.def_epa, self.burden = off_epa, def_epa, burden
        self.team_raw = {t: self.raw(games) for t, games in team_games.items()}
        self.dist = {}
        for side in SIDES:
            for kind in ("opp", "inj"):
                vals = pd.Series([v[side][kind] for v in self.team_raw.values() if v[side][kind] is not None])
                sd = float(vals.std(ddof=0)) if len(vals) > 1 else 0.0
                self.dist[(side, kind)] = (float(vals.mean()) if len(vals) else 0.0, sd)

    def _b(self, team, week, side):
        b = self.burden.get((team, week))
        if not b:
            return 0.0
        return sum(b.values()) if side == "all" else b[side]

    def raw(self, games):
        """games: list of (week, team, opponent). Returns raw difficulty + injury numbers per side."""
        out = {}
        for side in SIDES:
            opp_vals, inj_vals, own, theirs = [], [], [], []
            for week, team, opp in games:
                if side == "offense":  # tougher = better defenses (less EPA allowed)
                    d = -self.def_epa.get(opp, 0.0)
                    mine, other = self._b(team, week, "offense"), self._b(opp, week, "defense")
                elif side == "defense":  # tougher = better offenses
                    d = self.off_epa.get(opp, 0.0)
                    mine, other = self._b(team, week, "defense"), self._b(opp, week, "offense")
                else:
                    d = self.off_epa.get(opp, 0.0) - self.def_epa.get(opp, 0.0)
                    mine, other = self._b(team, week, "all"), self._b(opp, week, "all")
                opp_vals.append(d)
                inj_vals.append(mine - other)
                own.append(mine)
                theirs.append(other)
            n = len(games)
            out[side] = {
                "opp": sum(opp_vals) / n if n else None,
                "inj": sum(inj_vals) / n if n else None,
                "own_missing": sum(own) / n if n else 0.0,
                "opp_missing": sum(theirs) / n if n else 0.0,
            }
        return out

    def z(self, raw_side: dict, side: str):
        """How unusual these games were vs. a typical team's schedule (0 = typical)."""
        res = {}
        for kind in ("opp", "inj"):
            mu, sd = self.dist[(side, kind)]
            v = raw_side[kind]
            res[kind] = 0.0 if v is None or not sd else max(-2.5, min(2.5, (v - mu) / sd))
        return res

    def describe(self, raw_side: dict, side: str, team_rank: int | None = None) -> dict:
        noun = {"offense": "defenses", "defense": "offenses", "special": "opponents"}[side]
        z = self.z(raw_side, side)
        if team_rank is not None:
            opp = f"Faced the {_ordinal(team_rank)}-toughest {noun} so far (out of 32)."
        else:
            level = "tougher than average" if z["opp"] > 0.5 else "easier than average" if z["opp"] < -0.5 \
                else "about average"
            opp = f"The {noun} he faced were {level} for this season."
        side_word = {"offense": "on offense", "defense": "on defense", "special": "overall"}[side]
        opp_side = {"offense": "defenses", "defense": "offenses", "special": "teams"}[side]
        inj = (f"His team was missing {raw_side['own_missing']:.1f} expected starters per game {side_word}; "
               f"opposing {opp_side} were missing {raw_side['opp_missing']:.1f}. (A QB counts as 3.)")
        if team_rank is not None:
            inj = inj.replace("His team was", "This team was")
        return {"opp": opp, "inj": inj}


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def team_contexts(ctx: Context) -> dict:
    """{team: {side: {"opp_z", "inj_z", "opp", "inj"}}} with schedule ranks."""
    out = {t: {} for t in ctx.team_raw}
    for side in SIDES:
        order = sorted((t for t in ctx.team_raw if ctx.team_raw[t][side]["opp"] is not None),
                       key=lambda t: -ctx.team_raw[t][side]["opp"])
        rank = {t: i + 1 for i, t in enumerate(order)}
        for t, raw in ctx.team_raw.items():
            z = ctx.z(raw[side], side)
            text = ctx.describe(raw[side], side, rank.get(t))
            out[t][side] = {"opp_z": z["opp"], "inj_z": z["inj"], **text}
    return out
