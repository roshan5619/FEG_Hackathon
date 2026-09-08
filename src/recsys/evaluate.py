"""
Evaluation harness.

    python -m src.recsys.evaluate --all

The whole point of this module is the task split. In this dataset a median 78%
of a player's launches sit in their top-3 games, so a model that simply
re-serves what someone already plays posts a superb precision@10 and is useless
as a discovery widget. Reporting one blended number would flatter every model
and mislead the reader.

So two tasks, scored separately, never averaged together:

  DISCOVERY  ground truth = test games the player has NEVER played
             candidates  = everything EXCEPT their training history
             -> global popularity wins this outright; see docs/evaluation.md

  TAIL       the same, with the global top-N most popular games removed from
  DISCOVERY  both the candidate pool and the ground truth
             -> 76.5% of all discovery plays live here, popularity cannot
                reach them, and this is where personalisation earns its place

  REPEAT     ground truth = test games the player HAS played before
             candidates  = their training history only
             -> feeds "Continue playing"; easy, and honest to label as such

Both run over the same ranking code so no model gets a different code path.
Alongside accuracy we report **coverage** (how much of the catalogue ever gets
recommended) and **novelty** (mean unpopularity of what is recommended). A model
can win NDCG by parroting the head; those two columns expose it when it does.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from scipy import sparse

from src.pipeline.build_dataset import ART, load
from src.recsys import baselines as B
from src.recsys.item_item import ALS, ItemItemCF

KS = (5, 10, 20)
MIN_TRAIN_ITEMS = 3          # a player needs some history to personalise from
HEAD_N = 50                  # games excluded from the tail-discovery task
NEG_INF = np.float32(-1e30)


# --------------------------------------------------------------------- metrics
def _dcg(hits: np.ndarray) -> np.ndarray:
    disc = 1.0 / np.log2(np.arange(2, hits.shape[1] + 2))
    return (hits * disc).sum(axis=1)


def _metrics(ranked: np.ndarray, truth_sets, k: int, pop_rank: np.ndarray):
    """ranked: (users, >=k) item indices, best first. truth_sets: list of sets."""
    topk = ranked[:, :k]
    hits = np.zeros(topk.shape, dtype=np.float32)
    n_truth = np.zeros(len(truth_sets), dtype=np.float32)
    for u, truth in enumerate(truth_sets):
        n_truth[u] = len(truth)
        if truth:
            hits[u] = np.fromiter((1.0 if i in truth else 0.0 for i in topk[u]),
                                  dtype=np.float32, count=k)
    n_hit = hits.sum(axis=1)

    ideal = np.zeros(len(truth_sets), dtype=np.float32)
    disc = 1.0 / np.log2(np.arange(2, k + 2))
    for u, t in enumerate(truth_sets):
        ideal[u] = disc[:min(len(t), k)].sum()
    ndcg = np.divide(_dcg(hits), ideal, out=np.zeros_like(ideal), where=ideal > 0)

    return {
        "precision@%d" % k: float(np.mean(n_hit / k)),
        "recall@%d" % k: float(np.mean(np.divide(n_hit, n_truth,
                                                 out=np.zeros_like(n_truth),
                                                 where=n_truth > 0))),
        "ndcg@%d" % k: float(np.mean(ndcg)),
        "coverage@%d" % k: float(len(np.unique(topk)) ),
        "novelty@%d" % k: float(np.mean(pop_rank[topk])),
    }


# ------------------------------------------------------------------ evaluation
def evaluate(model, X_train, X_test, task: str, candidate_mask: np.ndarray,
             ks=KS, min_train=MIN_TRAIN_ITEMS, batch=512, head_n=HEAD_N):
    """
    Score one model on one task.

    task is "discovery", "tail_discovery" or "repeat". For tail_discovery the
    global top-`head_n` games are struck from both the candidate pool and the
    ground truth, so the question becomes "can you find what this player will
    try, once the blockbusters everyone sees anyway are off the table".
    """
    n_items = X_train.shape[1]
    train_bin = X_train.copy(); train_bin.data = np.ones_like(train_bin.data)
    test_bin = X_test.copy(); test_bin.data = np.ones_like(test_bin.data)

    # popularity rank in [0,1]; 1 = most obscure. Used for the novelty column.
    pop = np.asarray(train_bin.sum(axis=0)).ravel()
    order = np.argsort(np.argsort(pop))
    pop_rank = 1.0 - (order / max(len(order) - 1, 1))

    candidate_mask = candidate_mask.copy()
    if task == "tail_discovery":
        candidate_mask[np.argsort(-pop)[:head_n]] = False

    # --- build the cohort and the ground truth for this task ---------------
    rows, truths = [], []
    for u in range(X_train.shape[0]):
        tr = set(train_bin[u].indices.tolist())
        te = set(test_bin[u].indices.tolist())
        if len(tr) < min_train or not te:
            continue
        truth = (te & tr) if task == "repeat" else (te - tr)
        truth = {i for i in truth if candidate_mask[i]}
        if not truth:
            continue
        rows.append(u)
        truths.append(truth)

    if not rows:
        return {"cohort": 0, "truth_total": 0}

    rows = np.asarray(rows, dtype=np.int64)
    max_k = max(ks)
    ranked = np.zeros((len(rows), max_k), dtype=np.int32)

    for start in range(0, len(rows), batch):
        chunk = rows[start:start + batch]
        s = model.scores(X_train, chunk).astype(np.float32, copy=True)
        s[:, ~candidate_mask] = NEG_INF
        for j, u in enumerate(chunk):
            played = train_bin[u].indices
            if task != "repeat":
                # never recommend what they already play - that is the repeat widget
                s[j, played] = NEG_INF
            else:
                # repeat task ranks only within their own history
                m = np.ones(n_items, dtype=bool)
                m[played] = False
                s[j, m] = NEG_INF
        part = np.argpartition(-s, max_k - 1, axis=1)[:, :max_k]
        part_scores = np.take_along_axis(s, part, axis=1)
        order2 = np.argsort(-part_scores, axis=1)
        ranked[start:start + len(chunk)] = np.take_along_axis(part, order2, axis=1)

    out = {"cohort": int(len(rows)), "truth_total": int(sum(len(t) for t in truths))}
    for k in ks:
        out.update(_metrics(ranked, truths, k, pop_rank))
    return out


def run(all_models: bool = True, displayable_only: bool = False):
    d = load()
    X_train, X_test = d["X_train"], d["X_test"]
    n_items = X_train.shape[1]

    mask = np.zeros(n_items, dtype=bool)
    if displayable_only:
        mask[np.asarray(d["displayable"], dtype=np.int64)] = True
    else:
        mask[:] = True

    # provider code per item, for the ProviderPopular baseline
    provs = {}
    item_prov = np.full(n_items, -1, dtype=np.int32)
    for i, code in enumerate(d["items"]):
        p = (d["catalog"].get(code) or {}).get("provider")
        if p:
            item_prov[i] = provs.setdefault(p, len(provs))

    models = [
        B.RandomRec(), B.MostPlayed(), B.MostStaked(),
        B.UserTop(), B.ProviderPopular(item_prov),
        ItemItemCF(),
    ]
    if all_models:
        models.append(ALS())

    results = {}
    for m in models:
        m.fit(X_train)
        results[m.name] = {
            task: evaluate(m, X_train, X_test, task, mask)
            for task in ("discovery", "tail_discovery", "repeat")
        }
        print("  scored", m.name)
    return results, mask.sum()


def _table(results, task, ks=(10,)):
    k = ks[0]
    head = "%-18s %7s %10s %10s %10s %9s %9s" % (
        "model", "cohort", "P@%d" % k, "R@%d" % k, "NDCG@%d" % k, "cover", "novelty")
    lines = [head, "-" * len(head)]
    ordered = sorted(results.items(), key=lambda kv: -kv[1][task].get("ndcg@%d" % k, 0))
    for name, r in ordered:
        t = r[task]
        if not t.get("cohort"):
            continue
        lines.append("%-18s %7d %10.4f %10.4f %10.4f %9d %9.3f" % (
            name, t["cohort"], t["precision@%d" % k], t["recall@%d" % k],
            t["ndcg@%d" % k], t["coverage@%d" % k], t["novelty@%d" % k]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Evaluate recommenders.")
    ap.add_argument("--all", action="store_true", help="include ALS (slower)")
    ap.add_argument("--displayable-only", action="store_true",
                    help="restrict candidates and ground truth to nameable games")
    args = ap.parse_args()

    results, n_cand = run(all_models=args.all, displayable_only=args.displayable_only)

    print("\ncandidate pool: %d games%s" % (
        n_cand, " (displayable only)" if args.displayable_only else " (full catalogue)"))
    for task in ("discovery", "tail_discovery", "repeat"):
        print("\n=== %s ===" % task.upper())
        print(_table(results, task))

    os.makedirs(ART, exist_ok=True)
    name = "eval_displayable.json" if args.displayable_only else "eval_full.json"
    with open(os.path.join(ART, name), "w", encoding="utf-8") as fh:
        json.dump({"candidate_pool": int(n_cand), "results": results}, fh, indent=1)
    print("\nwrote artifacts/%s" % name)


if __name__ == "__main__":
    main()
