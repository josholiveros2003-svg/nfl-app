"""
League averages for every rating, so the app can show "avg 74" under each one.

Every rating object (rt) gets a key "a" naming who it's compared with:
  team, team.<unit>, team.<unit>.<category>, team.<unit>.<category>.<stat>   all 32 teams
  pos.<group>, pos.<group>.<category>, pos.<group>.<category>.<stat>        every rated player at that position
  rank.<list id>                                                            all 32 teams (position-group lists)

The app turns rating ingredients into a 0-100 number with the Settings sliders, so one stored
average would go stale as soon as a slider moves. Instead, public/data/averages.json stores the
average ingredients. Peers are split into buckets by which factors they have (a missing factor
changes the blend); inside a bucket a rating is a straight-line function of its ingredients, so
blending each bucket's averages and weighting by head count gives the exact average rating.
"""

from __future__ import annotations


class Averages:
    def __init__(self):
        self.groups: dict[str, list[dict]] = {}
        self.seen: set[int] = set()

    def add(self, key: str, rt: dict | None):
        """Tag one rating with its peer group (each rating object counts once)."""
        if not rt or rt.get("m") is None or not rt.get("g") or id(rt) in self.seen:
            return
        self.seen.add(id(rt))
        rt["a"] = key
        self.groups.setdefault(key, []).append(rt)

    def add_team(self, team_rt: dict | None, unit_ratings: dict, units: dict):
        self.add("team", team_rt)
        for u, v in unit_ratings.items():
            self.add(f"team.{u}", v["rt"])
        for u, cats in units.items():
            for cat in cats:
                self.add(f"team.{u}.{cat['id']}", cat.get("rt"))
                for s in cat["stats"]:
                    self.add(f"team.{u}.{cat['id']}.{s['id']}", s.get("rt"))

    def add_player(self, doc: dict):
        g = doc["group"]
        self.add(f"pos.{g}", doc.get("rt"))
        for cat in doc["categories"]:
            self.add(f"pos.{g}.{cat['id']}", cat.get("rt"))
            for s in cat["stats"]:
                self.add(f"pos.{g}.{cat['id']}.{s['id']}", s.get("rt"))

    def to_json(self) -> dict:
        """{key: [{n, m, g, res?}, ...]}, one entry per bucket."""
        out = {}
        for key, rts in self.groups.items():
            buckets: dict[tuple, list[dict]] = {}
            for rt in rts:
                pattern = (tuple(v is None for v in rt["g"]), rt.get("res") is not None)
                buckets.setdefault(pattern, []).append(rt)
            rows = []
            for (nulls, has_res), b in buckets.items():
                n = len(b)
                row = {"n": n, "m": round(sum(r["m"] for r in b) / n, 3),
                       "g": [None if nulls[i] else round(sum(r["g"][i] for r in b) / n, 3) for i in range(len(nulls))]}
                if has_res:
                    row["res"] = round(sum(r["res"] for r in b) / n, 3)
                rows.append(row)
            out[key] = rows
        return out
