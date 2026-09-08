"""
Feature engineering for the supervised re-ranker.

Every feature here is computed from the **train window only**. The labels the
ranker learns from come from the validation window, and the test window is
never touched by either. That separation is the whole point of the three-way
split: an earlier version of this project tuned on test and reported from it.

Features fall into three groups, and the split matters when reading the learned
coefficients:

  candidate scores   what the two counting models already think
  player x game fit  provider and game-type affinity, recency of that provider
  game properties    popularity, age, momentum, jackpot, payout ratio

A model that leans entirely on the first group has learned nothing the
candidate generator did not already know. The second group is where a ranker
earns its place.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy import sparse

FEATURE_NAMES: List[str] = [
    "cf_score",             # item-item collaborative filtering score
    "seq_score",            # day-to-day sequence score
    "pop_log",              # log1p(distinct players who played the game)
    "provider_affinity",    # share of this player's plays on that provider
    "provider_recency",     # recency weight of their most recent play there
    "type_affinity",        # share of this player's plays on that game type
    "momentum",             # rising/falling stake over 12 months
    "age_months",           # months since the game first recorded stake
    "is_new",               # first seen in the last 3 months
    "has_jackpot",
    "payout_ratio",         # win/stake proxy; similarity only, never ranked on
    "player_n_games",       # log1p, how broad this player's history is
    "player_total_conf",    # log1p, how heavy their play is
    "game_stake_pct",       # game's lifetime stake percentile
]


class FeatureBuilder:
    """Builds the (n_pairs, n_features) matrix for candidate scoring."""

    def __init__(self, X, catalog: Dict[str, dict], items: List[str],
                 X_recent: sparse.csr_matrix):
        self.X = X.tocsr()
        self.R = X_recent.tocsr()
        self.items = items
        self.catalog = catalog

        binar = self.X.copy()
        binar.data = np.ones_like(binar.data)
        self.pop = np.asarray(binar.sum(axis=0)).ravel().astype(np.float32)
        self.pop_log = np.log1p(self.pop)

        n = len(items)
        # --- per-game static features, aligned to the item index ----------
        self.momentum = np.zeros(n, dtype=np.float32)
        self.age = np.zeros(n, dtype=np.float32)
        self.is_new = np.zeros(n, dtype=np.float32)
        self.jackpot = np.zeros(n, dtype=np.float32)
        self.payout = np.full(n, 0.94, dtype=np.float32)   # median, for unknowns
        stake = np.zeros(n, dtype=np.float32)

        prov_ids: Dict[str, int] = {}
        type_ids: Dict[str, int] = {}
        self.prov_of = np.full(n, -1, dtype=np.int32)
        self.type_of = np.full(n, -1, dtype=np.int32)

        for i, code in enumerate(items):
            g = catalog.get(code) or {}
            self.momentum[i] = float(g.get("momentum") or 0.0)
            self.age[i] = float(g.get("age_months") or 0.0)
            self.is_new[i] = 1.0 if g.get("is_new") else 0.0
            self.jackpot[i] = 1.0 if g.get("has_jackpot") else 0.0
            if g.get("payout_ratio") is not None:
                self.payout[i] = float(g["payout_ratio"])
            stake[i] = float(g.get("lifetime_stake") or 0.0)
            p, t = g.get("provider"), g.get("game_type")
            if p:
                self.prov_of[i] = prov_ids.setdefault(p, len(prov_ids))
            if t:
                self.type_of[i] = type_ids.setdefault(t, len(type_ids))

        order = np.argsort(np.argsort(stake))
        self.stake_pct = (order / max(n - 1, 1)).astype(np.float32)

        # One-hot maps so a player's provider/type affinity is one sparse matmul.
        self.prov_onehot = _onehot(self.prov_of, len(prov_ids))
        self.type_onehot = _onehot(self.type_of, len(type_ids))

    # -- per-player vectors ------------------------------------------------
    def player_context(self, urow: int):
        """Affinities and activity summary for one player, from train data only."""
        hist = self.X[urow]
        rec = self.R[urow]
        total = float(hist.sum()) or 1.0

        prov_aff = np.asarray((hist @ self.prov_onehot).todense()).ravel() / total
        type_aff = np.asarray((hist @ self.type_onehot).todense()).ravel() / total
        prov_rec = np.asarray((rec @ self.prov_onehot).todense()).ravel()
        if prov_rec.max() > 0:
            prov_rec = prov_rec / prov_rec.max()
        return {
            "prov_aff": prov_aff.astype(np.float32),
            "type_aff": type_aff.astype(np.float32),
            "prov_rec": prov_rec.astype(np.float32),
            "n_games": np.float32(np.log1p(hist.nnz)),
            "total_conf": np.float32(np.log1p(total)),
        }

    def build(self, urow: int, candidates: np.ndarray,
              cf_scores: np.ndarray, seq_scores: np.ndarray) -> np.ndarray:
        """Feature matrix for one player's candidate list."""
        ctx = self.player_context(urow)
        c = candidates
        pi = self.prov_of[c]
        ti = self.type_of[c]
        safe_p = np.clip(pi, 0, None)
        safe_t = np.clip(ti, 0, None)

        prov_aff = np.where(pi >= 0, ctx["prov_aff"][safe_p], 0.0)
        prov_rec = np.where(pi >= 0, ctx["prov_rec"][safe_p], 0.0)
        type_aff = np.where(ti >= 0, ctx["type_aff"][safe_t], 0.0)

        return np.column_stack([
            _unit(cf_scores[c]), _unit(seq_scores[c]), self.pop_log[c],
            prov_aff, prov_rec, type_aff,
            self.momentum[c], self.age[c], self.is_new[c], self.jackpot[c],
            self.payout[c],
            np.full(len(c), ctx["n_games"], dtype=np.float32),
            np.full(len(c), ctx["total_conf"], dtype=np.float32),
            self.stake_pct[c],
        ]).astype(np.float32)


def _onehot(ids: np.ndarray, k: int) -> sparse.csr_matrix:
    k = max(k, 1)
    rows = np.arange(len(ids))
    keep = ids >= 0
    return sparse.csr_matrix(
        (np.ones(keep.sum(), dtype=np.float32), (rows[keep], ids[keep])),
        shape=(len(ids), k), dtype=np.float32)


def _unit(v: np.ndarray) -> np.ndarray:
    mx = v.max() if v.size else 0.0
    return (v / mx) if mx > 0 else v
