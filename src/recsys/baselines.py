"""
Baselines. These exist to be beaten, and one of them is hard to beat.

`most_played` is not a straw man - it is what psk.hr ships today. The lobby's
biggest row is "Najigranije" (most played), identical for every player. A
personalised model that cannot beat it has no business replacing it.

`user_top` is the honest hard baseline for the repeat task: a median 78% of a
player's launches sit in their top-3 games, so "show them what they already
play" scores very well on repeat and tells you nothing about discovery.

Every scorer returns a dense score array of shape (n_users, n_items). Ranking,
candidate masking and metric computation all live in evaluate.py so that every
model is scored by exactly the same code path.
"""
from __future__ import annotations

import numpy as np
from scipy import sparse


class Recommender:
    name = "base"

    def fit(self, X: sparse.csr_matrix) -> "Recommender":
        return self

    def scores(self, X: sparse.csr_matrix, rows: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class MostPlayed(Recommender):
    """Global popularity by number of distinct players. PSK's production row."""

    name = "most_played"

    def fit(self, X):
        binar = X.copy()
        binar.data = np.ones_like(binar.data)
        self.pop_ = np.asarray(binar.sum(axis=0)).ravel()
        return self

    def scores(self, X, rows):
        return np.tile(self.pop_, (len(rows), 1))


class MostStaked(Recommender):
    """Popularity by total confidence rather than headcount."""

    name = "most_staked"

    def fit(self, X):
        self.pop_ = np.asarray(X.sum(axis=0)).ravel()
        return self

    def scores(self, X, rows):
        return np.tile(self.pop_, (len(rows), 1))


class UserTop(Recommender):
    """The player's own history, ranked by their confidence. Repeat baseline."""

    name = "user_top"

    def scores(self, X, rows):
        return np.asarray(X[rows].todense(), dtype=np.float32)


class ProviderPopular(Recommender):
    """
    Popularity restricted to the player's dominant provider.

    A median 65% of a player's launches come from one provider, so this is a
    genuinely competitive non-personalised-model heuristic, not a formality.
    """

    name = "provider_popular"

    def __init__(self, item_provider: np.ndarray):
        self.item_provider = item_provider  # int code per item, -1 if unknown

    def fit(self, X):
        binar = X.copy()
        binar.data = np.ones_like(binar.data)
        self.pop_ = np.asarray(binar.sum(axis=0)).ravel()
        n_prov = int(self.item_provider.max()) + 1 if len(self.item_provider) else 0
        # provider affinity per user = summed confidence over that provider's items
        self.prov_onehot_ = sparse.csr_matrix(
            (np.ones(len(self.item_provider), dtype=np.float32),
             (np.arange(len(self.item_provider)),
              np.clip(self.item_provider, 0, None))),
            shape=(len(self.item_provider), max(n_prov, 1)), dtype=np.float32)
        return self

    def scores(self, X, rows):
        aff = X[rows] @ self.prov_onehot_               # (u, providers)
        aff = np.asarray(aff.todense(), dtype=np.float32)
        # broadcast each user's provider affinity back onto items, times popularity
        item_aff = aff[:, np.clip(self.item_provider, 0, None)]
        item_aff[:, self.item_provider < 0] = 0.0
        return item_aff * self.pop_[None, :]


class RandomRec(Recommender):
    """Floor. Seeded so the reported number is reproducible."""

    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def fit(self, X):
        self.n_items_ = X.shape[1]
        return self

    def scores(self, X, rows):
        return self.rng.random((len(rows), self.n_items_), dtype=np.float32)
