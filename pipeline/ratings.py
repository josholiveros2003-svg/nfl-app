"""
0-100 ratings that start from Madden and move with real results.

For one stat of one player (teams work the same way):
  1. Baseline M = his Madden NFL 27 launch rating.
  2. Stat-implied rating T = where his per-game stat sits among peers (z-score), put on
     Madden's scale for his position: T = Madden average + z x Madden spread.
  3. What an M-rated player would normally produce: E = Madden average + R x (M - average),
     where R is how strongly that stat tracks Madden (learned in learn.py).
  4. Adjustment = share x trust x (T - E)
       share = how much he's played: volume / (volume + 6 games' worth of the playing-time bar)
       trust = how well stats explain Madden at his position (with a minimum; see settings)
  5. Rating = M + adjustment.

The five "context" factors are five versions of that adjustment (this season, opponent-
adjusted, injury-adjusted, analyst (empty), last 3 games). The app blends them with the
Settings sliders, so the pipeline stores all five. Categories, units, players and teams
are weighted averages of the adjustments below them, so everything rolls up like the
drill-down: rating = baseline + weighted adjustment.

Stored format (rt): {"m": baseline, "g": [5 adjustments], "s": stats' share of the rating,
"ltd": limited sample, "nm": no Madden rating (estimated baseline)}.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "ratings.json"
SETTINGS = json.loads(SETTINGS_PATH.read_text())

MADDEN = SETTINGS["madden"]
FACTORS = {f["id"]: f for f in SETTINGS["context"]["factors"]}
OPP_PTS = FACTORS["opponents"]["pointsPerStdDev"]
INJ_PTS = FACTORS["injuries"]["pointsPerStdDev"]
RECENT_GAMES = FACTORS["recent"]["games"]

# Stats stored as season totals that should be judged per game.
NOT_COUNTS = {"fg_long", "long", "games"}
EXTRA_COUNTS = {"sacks"}  # pass-rush sacks are shown with a decimal (half sacks) but are still a count


def is_count(stat_id: str, fmt: str) -> bool:
    return (fmt == "int" and stat_id not in NOT_COUNTS) or stat_id in EXTRA_COUNTS


def per_game(value, stat_id, fmt, games):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if is_count(stat_id, fmt):
        return value / games if games else None
    return value


def weights_for(*path):
    """Look up a weights block, e.g. weights_for('team', 'units')."""
    node = SETTINGS
    for key in path:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    return node.get("weights", {}) if isinstance(node, dict) else {}


def sample_bar(cat_id: str, group: str):
    bars = SETTINGS["players"]["sampleBars"]["bars"]
    return bars.get(f"{cat_id}:{group}") or bars[cat_id]


def r1(x):
    return None if x is None else round(x, 1)


def stat_rating(model, season, group, cat_id, stat, value, recent_value, M, share, opp_z, inj_z, nm=False):
    """The rating ingredients for one stat (see the module docstring)."""
    if not stat["better"] or M is None:
        return None
    mu_m, sd_m = model.mdist.get(group, (75.0, 7.0))
    R = model.stat_r.get((group, cat_id, stat["id"]), 0.0)
    w = share * model.trust.get(group, MADDEN["minTrust"]["players"])
    z = model.z(season, group, cat_id, stat, value)
    if z is None or w <= 0:
        adj = adj_recent = opp = inj = 0.0
    else:
        expected = mu_m + R * (M - mu_m)
        adj = w * (mu_m + sd_m * z - expected)
        zr = model.z(season, group, cat_id, stat, recent_value)
        adj_recent = adj if zr is None else w * (mu_m + sd_m * zr - expected)
        opp = adj + w * OPP_PTS * opp_z
        inj = adj + w * INJ_PTS * inj_z
    rt = {"m": round(M, 1), "g": [r1(adj), r1(opp), r1(inj), None, r1(adj_recent)], "s": round(w, 2),
          "_z": z}  # how good the stat is vs peers (used to re-spread roll-ups; removed before saving)
    if nm:
        rt["nm"] = True
    return rt


def combine(children, M, nm=False, ltd=False):
    """Weighted average of child adjustments, on top of baseline M. children: [(weight, rt)]."""
    if M is None:
        return None
    items = [(w, rt) for w, rt in children if rt and w and w > 0]
    if not items:
        g, s, z = [0.0, 0.0, 0.0, None, 0.0], 0.0, None
    else:
        total = sum(w for w, _ in items)
        g = []
        for i in range(5):
            vals = [rt["g"][i] for _, rt in items]
            g.append(None if any(v is None for v in vals) else sum(w * v for (w, _), v in zip(items, vals)) / total)
        s = round(sum(w * rt.get("s", 0) for w, rt in items) / total, 2)
        zs = [(w, rt.get("_z")) for w, rt in items if rt.get("_z") is not None]
        z = sum(w * v for w, v in zs) / sum(w for w, _ in zs) if zs else None
    rt = {"m": round(M, 1), "g": g, "s": s, "_z": z}
    if nm:
        rt["nm"] = True
    if ltd:
        rt["ltd"] = True
    return rt


MAX_RESPREAD = 2.5


def respread(rts, reference=None):
    """Averaging many stats that partly cancel out shrinks the result. Measure how much
    (the spread of the averaged 'how good vs peers' score across the peer group) and scale
    this level's adjustments back up so it moves as much as a single stat would.
    Changes rts in place; rounds the stored numbers."""
    ref = [rt["_z"] for rt in (reference if reference is not None else rts) if rt and rt.get("_z") is not None]
    k = 1.0
    if len(ref) >= 5:
        mu = sum(ref) / len(ref)
        sd = math.sqrt(sum((x - mu) ** 2 for x in ref) / len(ref))
        if sd:
            k = max(1.0, min(MAX_RESPREAD, 1 / sd))
    for rt in rts:
        if not rt:
            continue
        rt["g"] = [None if x is None else r1(x * k) for x in rt["g"]]
        if rt.get("_z") is not None:
            rt["_z"] = rt["_z"] * k
        if k > 1.01:
            rt["k"] = round(k, 2)


def clean(rt):
    """Drop working values before saving."""
    if rt:
        rt.pop("_z", None)
    return rt


def blend_default(rt):
    """Final rating with the default slider weights (used for reports and checks)."""
    if not rt:
        return None
    ws = [f["weight"] if f.get("available", True) else 0 for f in SETTINGS["context"]["factors"]]
    pairs = [(w, v) for w, v in zip(ws, rt["g"]) if v is not None and w > 0]
    adj = sum(w * v for w, v in pairs) / sum(w for w, _ in pairs) if pairs else 0
    return max(1, min(99, rt["m"] + adj + rt.get("res", 0)))


# --------------------------------------------------------------------------
# Team baselines (from players' Madden ratings) + team ratings
# --------------------------------------------------------------------------

def team_baselines(starters: dict, madden: dict, fallback: dict) -> dict:
    """{team: {"offense", "defense", "special", "overall"}} on Madden's team scale.
    starters: {team: [(id, side, weight)]} (weight 3 marks the QB). madden: {id: rating}.
    fallback: {id: estimated rating} for starters without a Madden rating."""
    cfg = MADDEN["teamBaseline"]
    raw = {}
    for team, players in starters.items():
        sums = {}
        for pid, side, weight in players:
            w = cfg["qbWeight"] if weight >= 3 else 1.0
            rating = madden.get(pid, fallback.get(pid))
            if rating is None:
                continue
            a = sums.setdefault(side, [0.0, 0.0])
            a[0] += w * rating
            a[1] += w
        raw[team] = {side: s / w for side, (s, w) in sums.items() if w}
    unit_w = weights_for("team", "units")
    for vals in raw.values():
        tot = sum(unit_w[u] for u in unit_w if u in vals)
        vals["overall"] = sum(unit_w[u] * vals[u] for u in unit_w if u in vals) / tot
    out = {t: {} for t in raw}
    for key in ("offense", "defense", "special", "overall"):
        xs = [v[key] for v in raw.values() if key in v]
        mu = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs)) or 1.0
        for t, v in raw.items():
            if key in v:
                out[t][key] = round(max(1, min(99, cfg["mean"] + cfg["sd"] * (v[key] - mu) / sd)), 1)
    return out


def recent_games(gp):
    return min(gp, RECENT_GAMES) if gp else 0


def rate_teams(model, season, all_units: dict, recent_units: dict, gp: dict, ctx: dict, baselines: dict):
    """Adds `rt` and roll-up weight `w` to every team stat and category.
    Returns {team: {"rt": overall, "units": {unit: {"rt", "w"}}}}."""
    half = MADDEN["teamHalfWeightGames"]
    unit_w = weights_for("team", "units")
    teams = list(all_units)
    sample = all_units[teams[0]]
    # Stats and categories.
    for unit, cats in sample.items():
        cat_w = weights_for("team", "categories", unit)
        for ci, cat0 in enumerate(cats):
            weights = model.weights.get((unit, cat0["id"]), {})
            for t in teams:
                share = gp[t] / (gp[t] + half) if gp[t] else 0.0
                cat = all_units[t][unit][ci]
                c = ctx[t][unit]
                for si, s in enumerate(cat["stats"]):
                    rv = recent_units[t][unit][ci]["stats"][si]["value"]
                    pv = per_game(s["value"], s["id"], s["fmt"], gp[t])
                    rpv = per_game(rv, s["id"], s["fmt"], recent_games(gp[t]))
                    s["rt"] = stat_rating(model, season, unit, cat["id"], s, pv, rpv, baselines[t][unit], share,
                                          c["opp_z"], c["inj_z"])
                    s["w"] = round(weights.get(s["id"], 0) * 100, 1)
                cat["rt"] = combine([(s["w"], s["rt"]) for s in cat["stats"]], baselines[t][unit])
                cat["w"] = cat_w.get(cat["id"], 0)
            respread([all_units[t][unit][ci]["rt"] for t in teams])
    # Units, then the whole team.
    out = {t: {"units": {}} for t in teams}
    for unit in sample:
        for t in teams:
            cats = all_units[t][unit]
            out[t]["units"][unit] = {"rt": combine([(c["w"], c["rt"]) for c in cats], baselines[t][unit]),
                                     "w": unit_w.get(unit, 0)}
        respread([out[t]["units"][unit]["rt"] for t in teams])
    for t in teams:
        out[t]["rt"] = combine([(v["w"], v["rt"]) for v in out[t]["units"].values()], baselines[t]["overall"])
    respread([out[t]["rt"] for t in teams])
    # Tidy up working values.
    for t in teams:
        clean(out[t]["rt"])
        for v in out[t]["units"].values():
            clean(v["rt"])
        for cats in all_units[t].values():
            for cat in cats:
                clean(cat["rt"])
                for s in cat["stats"]:
                    clean(s["rt"])
    return out


def strip_fmt(all_units: dict):
    for units in all_units.values():
        for cats in units.values():
            for cat in cats:
                for s in cat["stats"]:
                    s.pop("fmt", None)
