"""
Learning how stats connect to Madden ratings (step 3 of the ratings).

For every position group (QB, RB, ... and the three team units), and every stat category
(Passing, Rushing, ...), we compare players' per-game stats with their Madden ratings,
using 2025 full-season stats and 2026 stats so far:

  - Each stat is standardized against peers in the same season ("z-score": how many
    standard deviations better than the average qualified player at his position).
  - A ridge regression (line fitting that resists overfitting) predicts the Madden rating
    from the category's stats. Only "sensible direction" weights are allowed: more
    interceptions can never raise a QB's rating, for example.
  - Cross-validation (fit on 80% of players, test on the other 20%, five times) measures
    how well stats explain Madden at that position, honestly, on players the model
    didn't see.

Outputs, per (position, category): the learned stat weights, how strongly each stat
tracks Madden on its own (its correlation, R), and the cross-validated fit.
"""

from __future__ import annotations

import copy
import math

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_predict

from ratings import SETTINGS, per_game

LEARN = SETTINGS["madden"]["learning"]


def _stats_of(cat):
    return [s for s in cat["stats"] if s["better"]]


class Model:
    def __init__(self):
        self.pools = {}     # (season, group, cat, stat) -> (mean, sd) of per-game values among qualified peers
        self.mdist = {}     # group -> (mean, sd) of Madden ratings among qualified players
        self.stat_r = {}    # (group, cat, stat) -> correlation of the stat with Madden (0 if negative)
        self.weights = {}   # (group, cat) -> {stat: learned weight (sums to 1)}
        self.learned = {}   # (group, cat) -> True if learned, False if fallback weights were used
        self.cat_fit = {}   # (group, cat) -> {"r2": cross-validated R², "n": players}
        self.group_fit = {} # group -> {"r2", "n", "top": [(stat label, points per SD)]}
        self.trust = {}     # group -> how much stats are trusted to move ratings (0-1)

    # ---- standardizing ----
    def z(self, season, group, cat, stat, value):
        mu, sd = self.pools.get((season, group, cat, stat["id"]), (None, None))
        if value is None or mu is None or not sd:
            return None
        z = (value - mu) / sd * (1 if stat["better"] == "high" else -1)
        return max(-3.0, min(3.0, z))


def perf_value(stat, games, team_based=False):
    if team_based:
        return stat["value"]
    return per_game(stat["value"], stat["id"], stat.get("fmt", "d1"), games)


def fit(rows: list, fallback) -> Model:
    """rows: [{"id", "season", "group", "M", "games", "cats": {cat_id: cat}}] where each cat has
    "stats" (with id/value/fmt/better), "qualified" and optional "teamBased".
    fallback(group, cat_id) -> {stat_id: weight} from the settings file."""
    model = Model()

    # 1. Peer averages/spreads per season (qualified players only).
    model.pools = _pools(rows)

    # 2. Madden spread per group.
    ms = {}
    for r in rows:
        if r["M"] is not None and any(c["qualified"] for c in r["cats"].values()):
            ms.setdefault(r["group"], []).append(r["M"])
    for g, v in ms.items():
        a = np.array(v, dtype=float)
        model.mdist[g] = (float(a.mean()), float(a.std()) or 7.0)

    # 3. Per (group, category): learned weights + fit.
    keys = {(r["group"], cid) for r in rows for cid in r["cats"]}
    for group, cid in sorted(keys):
        train = [r for r in rows if r["M"] is not None and cid in r["cats"] and r["cats"][cid]["qualified"]]
        sample_cat = next(r["cats"][cid] for r in rows if cid in r["cats"])
        stats = _stats_of(sample_cat)
        X, y = _matrix(model, train, group, cid, stats)
        for j, s in enumerate(stats):
            model.stat_r[(group, cid, s["id"])] = _corr(X[:, j], y) if len(y) >= 5 else 0.0
        if len(y) >= LEARN["minPlayers"] and stats:
            reg = Ridge(alpha=LEARN["ridgeAlpha"], positive=True).fit(X, y)
            coef = np.clip(reg.coef_, 0, None)
            r2 = _cv_r2(X, y)
            if coef.sum() > 0:
                # Half learned, half football knowledge (see settings: learnedShare).
                share = LEARN["learnedShare"]
                fb = fallback(group, cid)
                fb_total = sum(fb.get(s["id"], 0) for s in stats)
                model.weights[(group, cid)] = {
                    s["id"]: share * float(c / coef.sum()) + (1 - share) * (fb.get(s["id"], 0) / fb_total if fb_total else 0)
                    for s, c in zip(stats, coef)}
                model.learned[(group, cid)] = True
            model.cat_fit[(group, cid)] = {"r2": r2, "n": len(y)}
        if (group, cid) not in model.weights:
            fb = fallback(group, cid)
            total = sum(fb.get(s["id"], 0) for s in stats) or 1
            model.weights[(group, cid)] = {s["id"]: fb.get(s["id"], 0) / total for s in stats}
            model.learned[(group, cid)] = False
            model.cat_fit.setdefault((group, cid), {"r2": None, "n": len(y)})
    return model


def set_trust(model: Model, minimum: float):
    """Trust in stats per group = cross-validated correlation with Madden, never below `minimum`."""
    for group, fit in model.group_fit.items():
        r2 = fit.get("r2") or 0.0
        model.trust[group] = round(max(minimum, math.sqrt(r2)), 2)


def _pools(rows: list) -> dict:
    """(season, group, category, stat) -> (mean, sd) of per-game values among qualified peers."""
    vals = {}
    for r in rows:
        for cid, cat in r["cats"].items():
            if not cat["qualified"]:
                continue
            for s in _stats_of(cat):
                v = perf_value(s, r["games"], cat.get("teamBased"))
                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                    vals.setdefault((r["season"], r["group"], cid, s["id"]), []).append(v)
    out = {}
    for k, v in vals.items():
        a = np.array(v, dtype=float)
        out[k] = (float(a.mean()), float(a.std()))
    return out


def repool(model: Model, rows: list) -> Model:
    """The same learned model, but comparing against peers as they stood at an earlier point
    in the season (used to rebuild ratings 'as of' a past week without peeking ahead)."""
    m = copy.copy(model)
    m.pools = _pools(rows)
    return m


def fit_groups(model: Model, rows: list, core: dict, labels: dict):
    """Overall 'how well do stats explain Madden' per group, using all core-category stats together."""
    for group, cats in core.items():
        train = [r for r in rows if r["group"] == group and r["M"] is not None
                 and any(r["cats"].get(c, {}).get("qualified") for c in cats)]
        cols, Xs = [], []
        for cid in cats:
            sample = next((r["cats"][cid] for r in rows if r["group"] == group and cid in r["cats"]), None)
            if not sample:
                continue
            stats = _stats_of(sample)
            X, _ = _matrix(model, train, group, cid, stats, require_qualified=False)
            Xs.append(X)
            cols += [f"{labels.get(cid, cid)}: {s['label']}" for s in stats]
        if not Xs or len(train) < LEARN["minPlayers"]:
            model.group_fit[group] = {"r2": None, "n": len(train), "top": []}
            continue
        X = np.hstack(Xs)
        y = np.array([r["M"] for r in train], dtype=float)
        reg = Ridge(alpha=LEARN["ridgeAlpha"], positive=True).fit(X, y)
        order = np.argsort(-reg.coef_)[:4]
        model.group_fit[group] = {
            "r2": _cv_r2(X, y), "n": len(y),
            "top": [(cols[i], round(float(reg.coef_[i]), 2)) for i in order if reg.coef_[i] > 0.05],
        }


def _matrix(model, rows, group, cid, stats, require_qualified=True):
    X = np.zeros((len(rows), len(stats)))
    y = np.zeros(len(rows))
    for i, r in enumerate(rows):
        y[i] = r["M"]
        cat = r["cats"].get(cid)
        if cat is None or (require_qualified and not cat["qualified"]):
            continue  # not enough playing time here: counts as an average player (all zeros)
        lookup = {s["id"]: s for s in cat["stats"]}
        for j, s in enumerate(stats):
            st = lookup.get(s["id"])
            if st is None:
                continue
            z = model.z(r["season"], group, cid, st, perf_value(st, r["games"], cat.get("teamBased")))
            X[i, j] = 0.0 if z is None else z
    return X, y


def _corr(x, y):
    if x.std() == 0 or y.std() == 0:
        return 0.0
    return max(0.0, float(np.corrcoef(x, y)[0, 1]))


def _cv_r2(X, y):
    if len(y) < 10:
        return None
    folds = KFold(n_splits=5, shuffle=True, random_state=0)
    pred = cross_val_predict(Ridge(alpha=LEARN["ridgeAlpha"], positive=True), X, y, cv=folds)
    sst = float(((y - y.mean()) ** 2).sum())
    return max(0.0, 1 - float(((y - pred) ** 2).sum()) / sst) if sst else None
