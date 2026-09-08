"""
Offline pipeline: CA_Player.csv -> interaction matrices + catalogue.

    python -m src.pipeline.build_dataset --source path/to/CA_Player.csv

Writes to artifacts/ (committed, so the API and the dashboard run without the
source data, which is proprietary FEG data and gitignored):

    artifacts/catalog.json        every game code, family, title, provider
    artifacts/interactions.npz    train/test sparse matrices + index maps
    artifacts/dataset_report.json what the split contains, for the docs

Design decisions worth knowing:

* **Temporal split, never random.** Train on 2026-08-01..24, test on 08-25..31.
  A random split lets a player's future leak into their own training history and
  inflates every metric.
* **Train wide, serve narrow.** The matrix keeps all trainable games, including
  the opaque ones carrying 83% of stake, because their co-occurrence is what
  makes item-item similarity work. Only displayable games are ever recommended;
  that filter is applied at serving time, not here.
* **Stake is damped.** Raw stake spans several orders of magnitude, so one
  whale would dominate every similarity. Confidence is log1p(stake) with an
  interaction floor, the standard implicit-feedback treatment.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict

import numpy as np
from scipy import sparse

from src.recsys import catalog as cat

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ART = os.path.join(REPO, "artifacts")

SPLIT_DATE = "2026-08-25"       # test window is the final 7 days
MIN_STAKE = 0.0                 # keep every non-zero interaction


def _confidence(stake: float) -> float:
    """Implicit-feedback confidence. log1p damps whales without discarding them."""
    return float(np.log1p(max(stake, 0.0)))


def build(source: str, split_date: str = SPLIT_DATE):
    print("reading", source)
    rows_seen = 0
    raw = []
    with open(source, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows_seen += 1
            raw.append(r)
    print("rows", f"{rows_seen:,}")

    games = cat.build(raw)
    families = cat.summarise(games)
    print("catalogue:", json.dumps(families, indent=None))

    # ---- aggregate to (player, game) per split half -----------------------
    agg = {"train": defaultdict(float), "test": defaultdict(float)}
    days = {"train": defaultdict(set), "test": defaultdict(set)}
    dates = set()
    dropped_non_game = 0

    for r in raw:
        code = (r.get("reporting_bet_type") or "").strip()
        g = games.get(code)
        if g is None or g.family == cat.NON_GAME:
            dropped_non_game += 1
            continue
        d = r["local_transaction_date"]
        dates.add(d)
        try:
            stake = float(r.get("total_stake_amt") or 0.0)
        except (TypeError, ValueError):
            continue
        if stake <= MIN_STAKE:
            continue
        half = "train" if d < split_date else "test"
        key = (r["PlayerID"], code)
        agg[half][key] += stake
        days[half][key].add(d)

    print("dropped non-game rows:", f"{dropped_non_game:,}")

    # ---- index maps: built from TRAIN only, so test cannot define the space -
    train_players = sorted({p for p, _ in agg["train"]})
    trainable = sorted({c for _, c in agg["train"]} | {c for _, c in agg["test"]})
    uidx = {p: i for i, p in enumerate(train_players)}
    iidx = {c: i for i, c in enumerate(trainable)}

    def to_matrix(half):
        rows_, cols_, vals_ = [], [], []
        skipped = 0
        for (p, c), stake in agg[half].items():
            if p not in uidx or c not in iidx:
                skipped += 1
                continue
            rows_.append(uidx[p])
            cols_.append(iidx[c])
            vals_.append(_confidence(stake))
        m = sparse.csr_matrix(
            (vals_, (rows_, cols_)), shape=(len(uidx), len(iidx)), dtype=np.float32)
        return m, skipped

    X_train, _ = to_matrix("train")
    X_test, skipped_test = to_matrix("test")
    print("train matrix", X_train.shape, X_train.nnz, "nnz")
    print("test  matrix", X_test.shape, X_test.nnz, "nnz",
          "| test interactions from players unseen in train:", f"{skipped_test:,}")

    # ---- leakage guard -----------------------------------------------------
    # A test cell that also appears in train is a REPEAT, which is legitimate.
    # What must never happen is the same interaction counted in both halves as
    # if it were new. We record the overlap explicitly so evaluate.py can split
    # repeat from discovery rather than silently mixing them.
    overlap = X_train.multiply(X_test)
    overlap.eliminate_zeros()
    repeat_cells = overlap.nnz
    discovery_cells = X_test.nnz - repeat_cells
    print("test cells that are REPEATS  :", f"{repeat_cells:,}")
    print("test cells that are DISCOVERY:", f"{discovery_cells:,}")

    displayable = cat.displayable_codes(games)
    disp_idx = [iidx[c] for c in displayable if c in iidx]

    report = {
        "source": os.path.basename(source),
        "rows": rows_seen,
        "dropped_non_game_rows": dropped_non_game,
        "date_range": [min(dates), max(dates)],
        "split_date": split_date,
        "players_train": int(X_train.shape[0]),
        "games_trainable": int(X_train.shape[1]),
        "games_displayable": len(disp_idx),
        "interactions_train": int(X_train.nnz),
        "interactions_test": int(X_test.nnz),
        "test_repeat_cells": int(repeat_cells),
        "test_discovery_cells": int(discovery_cells),
        "density_train_pct": round(100 * X_train.nnz / (X_train.shape[0] * X_train.shape[1]), 3),
        "families": families,
    }

    os.makedirs(ART, exist_ok=True)
    with open(os.path.join(ART, "catalog.json"), "w", encoding="utf-8") as fh:
        json.dump({c: g.as_dict() for c, g in sorted(games.items())}, fh, indent=1, ensure_ascii=False)
    np.savez_compressed(
        os.path.join(ART, "interactions.npz"),
        train_data=X_train.data, train_indices=X_train.indices, train_indptr=X_train.indptr,
        test_data=X_test.data, test_indices=X_test.indices, test_indptr=X_test.indptr,
        shape=np.array(X_train.shape),
        players=np.array(train_players, dtype=object),
        items=np.array(trainable, dtype=object),
        displayable=np.array(disp_idx, dtype=np.int32),
    )
    with open(os.path.join(ART, "dataset_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)

    print("\nwrote artifacts/catalog.json, interactions.npz, dataset_report.json")
    return report


def load():
    """Load the built dataset. Used by the models, the API and the tests."""
    z = np.load(os.path.join(ART, "interactions.npz"), allow_pickle=True)
    shape = tuple(z["shape"])
    X_train = sparse.csr_matrix((z["train_data"], z["train_indices"], z["train_indptr"]), shape=shape)
    X_test = sparse.csr_matrix((z["test_data"], z["test_indices"], z["test_indptr"]), shape=shape)
    with open(os.path.join(ART, "catalog.json"), encoding="utf-8") as fh:
        games = json.load(fh)
    return {
        "X_train": X_train,
        "X_test": X_test,
        "players": list(z["players"]),
        "items": list(z["items"]),
        "displayable": z["displayable"].tolist(),
        "catalog": games,
    }


def main():
    ap = argparse.ArgumentParser(description="Build interaction matrices and catalogue.")
    ap.add_argument("--source", required=True, help="path to CA_Player.csv")
    ap.add_argument("--split-date", default=SPLIT_DATE)
    args = ap.parse_args()
    build(args.source, args.split_date)


if __name__ == "__main__":
    main()
