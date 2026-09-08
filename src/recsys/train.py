"""
Fit the models once, offline, and save what serving needs.

    python -m src.recsys.train

The API must not fit a model at startup. This writes artifacts/model.npz with
the item-item similarity matrix, the popularity vector and the cold-item list,
so `serve.py` is a few sparse lookups per request.

The similarity matrix is trained on the FULL catalogue (all 3,202 games,
including the 2,625 opaque codes carrying 83% of stake) because their
co-occurrence is what makes neighbourhoods meaningful. Filtering to displayable
games happens at serving time, never here.
"""
from __future__ import annotations

import json
import os

import numpy as np
from scipy import sparse

from src.pipeline.build_dataset import ART, load
from src.recsys.item_item import ItemItemCF

HEAD_N = 50          # "trending" size, and the head excluded from tail rows


def train():
    d = load()
    X = d["X_train"]
    print("fitting item-item on", X.shape, X.nnz, "interactions")

    cf = ItemItemCF()
    cf.fit(X)

    binar = X.copy()
    binar.data = np.ones_like(binar.data)
    pop = np.asarray(binar.sum(axis=0)).ravel().astype(np.float32)

    # Cold items: no training history at all. No collaborative model can reach
    # them, so they get their own row rather than being silently unreachable.
    cold = np.where(pop == 0)[0].astype(np.int32)

    S = cf.sim_.tocsr()
    os.makedirs(ART, exist_ok=True)
    np.savez_compressed(
        os.path.join(ART, "model.npz"),
        sim_data=S.data, sim_indices=S.indices, sim_indptr=S.indptr,
        sim_shape=np.array(S.shape),
        pop=pop, cold=cold,
        alpha=np.array([cf.alpha]), shrink=np.array([cf.shrink]),
        top_k=np.array([cf.top_k]),
    )
    meta = {
        "model": "item_item",
        "alpha": cf.alpha, "shrink": cf.shrink, "top_k": cf.top_k,
        "items": int(X.shape[1]), "players": int(X.shape[0]),
        "interactions": int(X.nnz),
        "sim_nnz": int(S.nnz),
        "cold_items": int(len(cold)),
        "head_n": HEAD_N,
    }
    with open(os.path.join(ART, "model_report.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))
    print("wrote artifacts/model.npz")
    return meta


def load_model():
    z = np.load(os.path.join(ART, "model.npz"), allow_pickle=False)
    S = sparse.csr_matrix(
        (z["sim_data"], z["sim_indices"], z["sim_indptr"]),
        shape=tuple(z["sim_shape"]))
    return {"sim": S, "pop": z["pop"], "cold": z["cold"]}


if __name__ == "__main__":
    train()
