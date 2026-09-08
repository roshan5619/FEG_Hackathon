"""
The supervised re-ranker - the part of this system that is genuinely trained.

Everything else in `src/recsys` is closed-form counting: item-item CF is one
matrix multiply, the sequence model is normalised transition counts. Both are
legitimate recommender algorithms, but neither has a loss function and calling
them "trained" would be overselling. This module does have one.

Two stages, the way large recommenders are actually built:

  1. CANDIDATE GENERATION - the counting models propose ~200 games per player.
     Cheap, high recall, no judgement about ordering.
  2. RE-RANKING - a scikit-learn classifier, fitted with a loss function on
     labelled examples, scores those candidates and reorders them.

Labels come from the VALIDATION window: 1 if the player actually played that
game in 2026-08-18..24, else 0. Features come from the TRAIN window only. The
test window is never seen during training or model selection.

Negatives are sampled from the generated candidates, never from the whole
catalogue. Sampling 3,000 random games as negatives would make the task
trivially separable and produce a model that looks excellent and ranks badly.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import numpy as np

from src.recsys.baselines import Recommender
from src.recsys.features import FEATURE_NAMES, FeatureBuilder

N_CANDIDATES = 200
MAX_TRAIN_PLAYERS = 6000      # enough for a stable fit, keeps training ~1 min
NEG_PER_POS = 12
SEED = 0


class LearnedRanker(Recommender):
    """Two-stage recommender: candidate generation, then a trained classifier."""

    name = "ranker"

    def __init__(self, cf, seq, fb: FeatureBuilder, model_kind: str = "gbm",
                 n_candidates: int = N_CANDIDATES):
        self.cf = cf
        self.seq = seq
        self.fb = fb
        self.model_kind = model_kind
        self.n_candidates = n_candidates
        self.model = None
        self.report: Dict = {}

    # -- stage 1 -----------------------------------------------------------
    def candidates(self, X, urow: int, exclude_played: bool = True):
        """Union of what the two counting models rank highest for this player."""
        cf_s = np.asarray((X[urow] @ self.cf.sim_).todense(), dtype=np.float32).ravel()
        seq_s = np.asarray((self.fb.R[urow] @ self.seq.T_).todense(),
                           dtype=np.float32).ravel()
        blend = _unit(cf_s) + 3.0 * _unit(seq_s)
        if exclude_played:
            blend[X[urow].indices] = -np.inf
        k = min(self.n_candidates, blend.size)
        cand = np.argpartition(-blend, k - 1)[:k]
        cand = cand[np.isfinite(blend[cand])]
        return cand, cf_s, seq_s

    # -- stage 2: training -------------------------------------------------
    def fit_supervised(self, X, X_labels, rows: Optional[np.ndarray] = None):
        """
        Train on (features from X) -> (did the player play it in X_labels).

        X        train-window interactions; every feature is derived from it
        X_labels validation-window interactions; the target only
        """
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        rng = np.random.default_rng(SEED)
        lab = X_labels.tocsr()
        if rows is None:
            eligible = [u for u in range(X.shape[0])
                        if lab[u].nnz > 0 and X[u].nnz >= 3]
            rng.shuffle(eligible)
            rows = np.asarray(eligible[:MAX_TRAIN_PLAYERS], dtype=np.int64)

        feats, labels, groups = [], [], []
        for u in rows:
            cand, cf_s, seq_s = self.candidates(X, int(u))
            if cand.size == 0:
                continue
            truth = set(lab[int(u)].indices.tolist())
            y = np.fromiter((1 if c in truth else 0 for c in cand),
                            dtype=np.int8, count=len(cand))
            pos = np.flatnonzero(y == 1)
            if pos.size == 0:
                continue                      # nothing to learn from this player
            neg = np.flatnonzero(y == 0)
            take = min(neg.size, pos.size * NEG_PER_POS)
            neg = rng.choice(neg, size=take, replace=False) if take else neg
            sel = np.concatenate([pos, neg])
            feats.append(self.fb.build(int(u), cand[sel], cf_s, seq_s))
            labels.append(y[sel])
            groups.append(np.full(sel.size, u))

        Xf = np.vstack(feats).astype(np.float32)
        yf = np.concatenate(labels).astype(np.int8)
        print("  training rows %s | positives %s (%.1f%%) | players %d"
              % (format(len(yf), ","), format(int(yf.sum()), ","),
                 100 * yf.mean(), len(feats)))

        self.scaler = StandardScaler().fit(Xf)
        Xs = self.scaler.transform(Xf)

        if self.model_kind == "logreg":
            model = LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced")
        else:
            model = GradientBoostingClassifier(
                n_estimators=150, max_depth=3, learning_rate=0.1,
                subsample=0.8, random_state=SEED)
        model.fit(Xs, yf)
        self.model = model

        if hasattr(model, "coef_"):
            weights = model.coef_.ravel()
        else:
            weights = model.feature_importances_
        self.report = {
            "model": self.model_kind,
            "n_rows": int(len(yf)), "n_positives": int(yf.sum()),
            "positive_rate": round(float(yf.mean()), 4),
            "n_players": len(feats), "n_candidates": self.n_candidates,
            "negatives_per_positive": NEG_PER_POS,
            "train_accuracy": round(float(model.score(Xs, yf)), 4),
            "features": [
                {"name": n, "weight": round(float(w), 4)}
                for n, w in sorted(zip(FEATURE_NAMES, weights),
                                   key=lambda kv: -abs(kv[1]))
            ],
        }
        return self

    # -- Recommender interface --------------------------------------------
    def fit(self, X):
        return self          # supervised fitting is explicit, via fit_supervised

    def scores(self, X, rows: np.ndarray) -> np.ndarray:
        """Dense score row per player: candidates get the model's probability."""
        out = np.full((len(rows), X.shape[1]), -1e30, dtype=np.float32)
        for j, u in enumerate(rows):
            cand, cf_s, seq_s = self.candidates(X, int(u))
            if cand.size == 0:
                continue
            F = self.scaler.transform(self.fb.build(int(u), cand, cf_s, seq_s))
            out[j, cand] = self.model.predict_proba(F)[:, 1].astype(np.float32)
        return out

    # -- explanation -------------------------------------------------------
    def explain(self, X, urow: int, item: int) -> Dict:
        """
        Per-feature contribution for one (player, game) decision.

        For logistic regression this is exact: contribution = coefficient x
        standardised feature value, and they sum to the logit. For the boosted
        model the same product is reported as an indicative attribution and
        labelled as such, because tree ensembles have no linear decomposition.
        """
        cand, cf_s, seq_s = self.candidates(X, urow, exclude_played=False)
        if item not in set(cand.tolist()):
            cand = np.append(cand, item)
        F = self.fb.build(urow, cand, cf_s, seq_s)
        idx = int(np.flatnonzero(cand == item)[0])
        Fs = self.scaler.transform(F)
        w = (self.model.coef_.ravel() if hasattr(self.model, "coef_")
             else self.model.feature_importances_)
        contrib = Fs[idx] * w
        return {
            "probability": float(self.model.predict_proba(Fs[idx:idx + 1])[0, 1]),
            "exact": hasattr(self.model, "coef_"),
            "features": [
                {"name": n, "value": round(float(v), 4),
                 "standardised": round(float(s), 3),
                 "contribution": round(float(c), 4)}
                for n, v, s, c in sorted(
                    zip(FEATURE_NAMES, F[idx], Fs[idx], contrib),
                    key=lambda t: -abs(t[3]))
            ],
        }

    # -- persistence -------------------------------------------------------
    def save(self, art_dir: str):
        import pickle
        with open(os.path.join(art_dir, "ranker.pkl"), "wb") as fh:
            pickle.dump({"model": self.model, "scaler": self.scaler,
                         "kind": self.model_kind}, fh)
        with open(os.path.join(art_dir, "ranker_report.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(self.report, fh, indent=1)

    def load(self, art_dir: str):
        import pickle
        with open(os.path.join(art_dir, "ranker.pkl"), "rb") as fh:
            blob = pickle.load(fh)
        self.model, self.scaler, self.model_kind = blob["model"], blob["scaler"], blob["kind"]
        path = os.path.join(art_dir, "ranker_report.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.report = json.load(fh)
        return self


def _unit(v: np.ndarray) -> np.ndarray:
    mx = v.max() if v.size else 0.0
    return (v / mx) if mx > 0 else v
