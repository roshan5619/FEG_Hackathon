"""
Fit every model once, offline, and save what serving needs.

    python -m src.recsys.train

Three things are produced:

  artifacts/model.npz     item-item similarity, sequence transitions, popularity
  artifacts/ranker.pkl    the TRAINED classifier (scikit-learn)
  artifacts/*_report.json what was fitted, and what the ranker learned

The API never fits anything at startup.

WHICH DATA EACH MODEL SEES
Everything - candidate models, ranker features, ranker labels - is fitted on
train features with validation labels. The test window is never touched, by
evaluation or by serving.

An earlier version of this file refitted the served models on train+validation
and trained the ranker on TEST labels, on the reasoning that "in production you
use every day you have". That is true in production, but here the test window
is our held-out evaluation: a served model that has seen it makes every number
we quote from the demo unverifiable, and produces a feature/scaler mismatch
against the evaluated model. A real deployment slides all three windows forward
instead; `--serve-on-all` reproduces that behaviour and is off by default and
clearly unsafe to evaluate from.

WHY LOGISTIC REGRESSION AND NOT GRADIENT BOOSTING
Chosen before reading the test set, on two grounds:
  1. It is interpretable. Contribution = coefficient x standardised feature,
     which is exactly what the "why this tile" panel shows and what the EU AI
     Act explainability expectation needs. A boosted ensemble has no such exact
     decomposition.
  2. Its training accuracy is 0.656 against the boosted model's 0.920 on an
     8.1%-positive problem - the boosted model is memorising.
Both are reported in docs/evaluation.md, including the finding that GBM scored
higher on a player-split validation and lower on the temporally separate test
set, which is what overfitting to a label window looks like.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from scipy import sparse

from src.pipeline.build_dataset import ART, load
from src.recsys.features import FeatureBuilder
from src.recsys.hybrid import SequenceRec
from src.recsys.item_item import ItemItemCF
from src.recsys.ranker import LearnedRanker

HEAD_N = 50                          # "Popularno" size; head excluded from discovery
W_CF, W_SEQ, W_POP = 1.0, 5.0, 0.0   # swept on VALIDATION (docs/evaluation.md)
RANKER_KIND = "logreg"


def train(serve_on_all: bool = False, ranker_kind: str = RANKER_KIND):
    d = load()
    if serve_on_all:
        # Production-shaped, and NOT safe to quote evaluation numbers from.
        X, T, R, labels = d["X_fit"], d["T_fit"], d["X_recent_fit"], d["X_test"]
        window = "train+validation (labels from test - EVALUATION INVALID)"
    else:
        X, T, R, labels = d["X_train"], d["T"], d["X_recent"], d["X_val"]
        window = "train (labels from validation)"
    print("fitting on %s: %s players, %s interactions"
          % (window, format(X.shape[0], ","), format(X.nnz, ",")))

    cf = ItemItemCF().fit(X)
    seq = SequenceRec(T, R, alpha=0.0).fit(X)

    binar = X.copy()
    binar.data = np.ones_like(binar.data)
    pop = np.asarray(binar.sum(axis=0)).ravel().astype(np.float32)

    S, Tn = cf.sim_.tocsr(), seq.T_.tocsr()
    os.makedirs(ART, exist_ok=True)
    np.savez_compressed(
        os.path.join(ART, "model.npz"),
        sim_data=S.data, sim_indices=S.indices, sim_indptr=S.indptr,
        sim_shape=np.array(S.shape),
        seq_data=Tn.data, seq_indices=Tn.indices, seq_indptr=Tn.indptr,
        seq_shape=np.array(Tn.shape),
        pop=pop, weights=np.array([W_CF, W_SEQ, W_POP], dtype=np.float32))

    # ---- the trained part ------------------------------------------------
    print("training the supervised ranker (%s) ..." % ranker_kind)
    fb = FeatureBuilder(X, d["catalog"], d["items"], R)
    ranker = LearnedRanker(cf, seq, fb, model_kind=ranker_kind)
    ranker.fit_supervised(X, labels)
    ranker.save(ART)
    top = ranker.report["features"][:5]
    print("  learned weights (top 5): "
          + ", ".join("%s %+0.3f" % (f["name"], f["weight"]) for f in top))

    meta = {
        "fitted_on": window,
        "candidate_models": ["item_item", "sequence"],
        "blend": {"cf": W_CF, "sequence": W_SEQ, "popularity": W_POP,
                  "tuned_on": "validation"},
        "ranker": {"kind": ranker_kind,
                   "train_accuracy": ranker.report["train_accuracy"],
                   "n_rows": ranker.report["n_rows"],
                   "n_positives": ranker.report["n_positives"]},
        "cf": {"alpha": cf.alpha, "shrink": cf.shrink, "top_k": cf.top_k,
               "nnz": int(S.nnz)},
        "sequence": {"alpha": seq.alpha, "shrink": seq.shrink,
                     "top_k": seq.top_k, "nnz": int(Tn.nnz)},
        "players": int(X.shape[0]), "items": int(X.shape[1]),
        "interactions": int(X.nnz), "head_n": HEAD_N,
    }
    with open(os.path.join(ART, "model_report.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))
    print("wrote artifacts/model.npz, ranker.pkl, ranker_report.json")
    return meta


def load_model():
    z = np.load(os.path.join(ART, "model.npz"), allow_pickle=False)
    S = sparse.csr_matrix((z["sim_data"], z["sim_indices"], z["sim_indptr"]),
                          shape=tuple(z["sim_shape"]))
    T = sparse.csr_matrix((z["seq_data"], z["seq_indices"], z["seq_indptr"]),
                          shape=tuple(z["seq_shape"]))
    w = z["weights"]
    return {"sim": S, "seq": T, "pop": z["pop"],
            "w_cf": float(w[0]), "w_seq": float(w[1]), "w_pop": float(w[2])}


def main():
    ap = argparse.ArgumentParser(description="Fit all models and save artifacts.")
    ap.add_argument("--serve-on-all", action="store_true",
                    help="fit on train+validation with test labels; production-shaped "
                         "but invalidates every evaluation number")
    ap.add_argument("--ranker", default=RANKER_KIND, choices=["logreg", "gbm"])
    args = ap.parse_args()
    train(serve_on_all=args.serve_on_all, ranker_kind=args.ranker)


if __name__ == "__main__":
    main()
