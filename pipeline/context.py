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


def expected_starters(depth: pd.DataFrame, season_start: str) -> dict:
    """Starters from each team's last depth chart before Week 1: {team: [(id, side, weight)]}."""
    d = depth.dropna(subset=["gsis_id"]).copy()
    pre = d[d.dt < season_start]
    out = {}
    for team, rows in d.groupby("team"):
        snap = pre[pre.team == team]
        snap = snap[snap.dt == snap.dt.max()] if len(snap) else rows[rows.dt == rows.dt.min()]
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
            starters.setdefault(r.gsis_id, (side, weight))
        out[team] = [(pid, side, w) for pid, (side, w) in starters.items()]
    return out


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
