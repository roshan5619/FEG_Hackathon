"""
Item-item collaborative filtering.

Chosen as the primary model for three reasons, in order of importance:

1. **It is explainable.** Every score decomposes into "you played X, and people
   who play X also play Y". The widgets need that sentence - a tile that says
   *Because you played Book of Ra* is a better product than an unexplained one,
   and under the EU AI Act an unexplainable recommender on a gambling platform
   is a liability.
2. **It suits this density.** 0.42% with ~3,200 items is squarely where
   neighbourhood methods do well; matrix factorisation's advantage shows up on
   much sparser, much larger catalogues.
3. **It has no training loop to get wrong.** One sparse matrix product.

Two corrections applied to plain cosine:

* **Popularity correction** (`alpha`), applied to the similarity matrix. The
  default is 0.0 and that is a measured choice, not laziness. Positive alpha
  damps popular items; on this dataset it makes discovery strictly worse,
  because what players try next is overwhelmingly what is already popular
  (Spearman 0.79 between training popularity and next-week discovery plays).
  Negative alpha boosts popularity and improves headline discovery, but only by
  converging on the popularity baseline - at alpha=-1.5 catalogue coverage
  collapses from 726 games to 87. Since this model's job is the *tail*, where
  the popularity row cannot reach, 0.0 is correct. See docs/evaluation.md.
* **Shrinkage** (`shrink`). Two items co-played by three people should not look
  as similar as two co-played by three hundred. Shrinkage pulls low-support
  pairs toward zero.
"""
from __future__ import annotations

import numpy as np
from scipy import sparse

from .baselines import Recommender


class ItemItemCF(Recommender):
    name = "item_item"

    def __init__(self, top_k: int = 300, alpha: float = 0.0, shrink: float = 20.0):
        self.top_k = top_k
        self.alpha = alpha
        self.shrink = shrink

    def fit(self, X: sparse.csr_matrix) -> "ItemItemCF":
        Xc = X.tocsc().astype(np.float32)

        binar = Xc.copy()
        binar.data = np.ones_like(binar.data)
        pop = np.asarray(binar.sum(axis=0)).ravel().astype(np.float32)

        # Cosine similarity.
        norms = np.sqrt(np.asarray(Xc.multiply(Xc).sum(axis=0)).ravel())
        inv = 1.0 / np.maximum(norms, 1e-8)
        Xn = (Xc @ sparse.diags(inv.astype(np.float32))).tocsc()

        S = (Xn.T @ Xn).tocsr().astype(np.float32)      # (items, items)

        # Popularity correction, applied to the SIMILARITY - not to the columns
        # before cosine, which does nothing at all: cosine is scale-invariant
        # per column, so a column-wise rescale cancels exactly in the
        # normalisation. Positive alpha damps popular items (long-tail
        # discovery); negative alpha boosts them, which is what this dataset
        # wants, because cosine's own normalisation already penalises
        # blockbusters and blockbusters are what players actually try next.
        if self.alpha:
            corr = np.power(np.maximum(pop, 1.0), -self.alpha).astype(np.float32)
            S = (S @ sparse.diags(corr)).tocsr()

        # Shrinkage by co-occurrence support. Applied on the data array: a
        # scalar cannot be added to a sparse matrix, and it would be wrong to
        # anyway - cells with zero co-occurrence must stay zero, not become
        # 0/(0+shrink) inside a densified matrix.
        co = (binar.T @ binar).tocsr().astype(np.float32)
        co.data = co.data / (co.data + self.shrink)
        S = sparse.csr_matrix(S.multiply(co))
        S.setdiag(0.0)
        S.eliminate_zeros()

        self.sim_ = _keep_top_k(S, self.top_k)
        self.pop_ = pop
        return self

    def scores(self, X: sparse.csr_matrix, rows: np.ndarray) -> np.ndarray:
        return np.asarray((X[rows] @ self.sim_).todense(), dtype=np.float32)

    # -- explanation -------------------------------------------------------
    def why(self, X: sparse.csr_matrix, user_row: int, item_col: int, top_n: int = 1):
        """
        Which of the player's own games drove this recommendation.

        Returns [(item_index, contribution)], largest first - the literal
        decomposition of the score, not a post-hoc story.
        """
        played = X[user_row].indices
        if len(played) == 0:
            return []
        contrib = np.asarray(
            X[user_row, played].todense()).ravel() * np.asarray(
            self.sim_[played, item_col].todense()).ravel()
        order = np.argsort(-contrib)[:top_n]
        return [(int(played[i]), float(contrib[i])) for i in order if contrib[i] > 0]


def _keep_top_k(S: sparse.csr_matrix, k: int) -> sparse.csr_matrix:
    """Keep the k strongest neighbours per row. Bounds memory and denoises."""
    S = S.tocsr()
    rows, cols, vals = [], [], []
    for i in range(S.shape[0]):
        lo, hi = S.indptr[i], S.indptr[i + 1]
        if hi <= lo:
            continue
        d = S.data[lo:hi]
        idx = S.indices[lo:hi]
        if len(d) > k:
            sel = np.argpartition(-d, k)[:k]
            d, idx = d[sel], idx[sel]
        rows.append(np.full(len(idx), i, dtype=np.int32))
        cols.append(idx.astype(np.int32))
        vals.append(d.astype(np.float32))
    if not rows:
        return sparse.csr_matrix(S.shape, dtype=np.float32)
    return sparse.csr_matrix(
        (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
        shape=S.shape, dtype=np.float32)


class ALS(Recommender):
    """
    Implicit-feedback matrix factorisation (Hu, Koren & Volinsky 2008).

    Hand-written rather than pulled from the `implicit` package: it is ~30 lines,
    it avoids a compiled dependency for one comparison model, and the point here
    is to check whether latent factors beat neighbourhoods on this data - not to
    win a leaderboard.
    """

    name = "als"

    def __init__(self, factors: int = 64, reg: float = 0.05, iters: int = 12,
                 alpha: float = 40.0, seed: int = 0):
        self.factors, self.reg, self.iters, self.alpha, self.seed = factors, reg, iters, alpha, seed

    def fit(self, X: sparse.csr_matrix) -> "ALS":
        rng = np.random.default_rng(self.seed)
        C = X.copy().astype(np.float32)
        C.data = 1.0 + self.alpha * C.data          # confidence
        n_u, n_i = C.shape
        U = rng.normal(0, 0.01, (n_u, self.factors)).astype(np.float32)
        V = rng.normal(0, 0.01, (n_i, self.factors)).astype(np.float32)
        Ct = C.T.tocsr()
        eye = np.eye(self.factors, dtype=np.float32) * self.reg

        for _ in range(self.iters):
            U = _als_side(C, V, eye)
            V = _als_side(Ct, U, eye)
        self.U_, self.V_ = U, V
        return self

    def scores(self, X, rows):
        return (self.U_[rows] @ self.V_.T).astype(np.float32)


def _als_side(C: sparse.csr_matrix, Y: np.ndarray, eye: np.ndarray) -> np.ndarray:
    """One ALS half-step: solve for every row of C given fixed factors Y."""
    YtY = Y.T @ Y
    out = np.zeros((C.shape[0], Y.shape[1]), dtype=np.float32)
    for r in range(C.shape[0]):
        lo, hi = C.indptr[r], C.indptr[r + 1]
        if hi == lo:
            continue
        idx, conf = C.indices[lo:hi], C.data[lo:hi]
        Yi = Y[idx]
        A = YtY + (Yi.T * (conf - 1.0)) @ Yi + eye
        b = (conf @ Yi)
        out[r] = np.linalg.solve(A, b)
    return out
