"""
Fit the models once, offline, and save what serving needs.

    python -m src.recsys.train

The API must never fit a model at startup. This writes artifacts/model.npz with
the item-item similarity, the normalised day-to-day transition matrix and the
popularity vector, so a request is a few sparse lookups.

Blend weights are the measured optimum on tail discovery (see
docs/evaluation.md), not a guess: cf=1.0, seq=3.0, pop=0.0.
"""
from __future__ import annotations

import json
import os

import numpy as np
from scipy import sparse

from src.pipeline.build_dataset import ART, load
from src.recsys.hybrid import SequenceRec
from src.recsys.item_item import ItemItemCF

HEAD_N = 50          # "Popularno" size, and the head excluded from discovery rows
W_CF, W_SEQ, W_POP = 1.0, 3.0, 0.0


def train():
    d = load()
    X, T, R = d["X_train"], d["T"], d["X_recent"]
    print("fitting on", X.shape, format(X.nnz, ","), "interactions")

    cf = ItemItemCF().fit(X)
    seq = SequenceRec(T, R, alpha=0.0).fit(X)

    binar = X.copy()
    binar.data = np.ones_like(binar.data)
    pop = np.asarray(binar.sum(axis=0)).ravel().astype(np.float32)

    S = cf.sim_.tocsr()
    Tn = seq.T_.tocsr()
    os.makedirs(ART, exist_ok=True)
    np.savez_compressed(
        os.path.join(ART, "model.npz"),
        sim_data=S.data, sim_indices=S.indices, sim_indptr=S.indptr,
        sim_shape=np.array(S.shape),
        seq_data=Tn.data, seq_indices=Tn.indices, seq_indptr=Tn.indptr,
        seq_shape=np.array(Tn.shape),
        pop=pop,
        weights=np.array([W_CF, W_SEQ, W_POP], dtype=np.float32))

    meta = {
        "models": ["item_item", "sequence"],
        "blend": {"cf": W_CF, "sequence": W_SEQ, "popularity": W_POP},
        "cf": {"alpha": cf.alpha, "shrink": cf.shrink, "top_k": cf.top_k, "nnz": int(S.nnz)},
        "sequence": {"alpha": seq.alpha, "shrink": seq.shrink, "top_k": seq.top_k,
                     "nnz": int(Tn.nnz)},
        "players": int(X.shape[0]), "items": int(X.shape[1]),
        "interactions": int(X.nnz), "head_n": HEAD_N,
    }
    with open(os.path.join(ART, "model_report.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))
    print("wrote artifacts/model.npz")
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


if __name__ == "__main__":
    train()
