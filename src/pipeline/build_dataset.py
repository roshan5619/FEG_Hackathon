"""
Offline pipeline: raw FEG exports -> everything the recommender serves from.

    python -m src.pipeline.build_dataset --data-dir path/to/FEG_Hackathon

Reads (none are committed - all are gitignored FEG property):
    CA_Player.csv                    player x game x day stake  (the interactions)
    CA_MOM.csv                       game x month, 12 months    (content features)
    top_casino_users_event_logs.csv  session events, real titles
    top_sport_users_event_logs.csv   ditto, plus sport crossover
    SB_Player.csv                    sportsbook bets            (cross-domain, optional)

Writes to artifacts/ (committed, so the API runs without the source data):
    catalog.json          every game: family, title, provider, content features
    interactions.npz      train/test matrices, recency profiles, index maps
    sequence.npz          day-to-day game transition matrix
    dataset_report.json   what the build contains

Three decisions worth knowing:

* **Temporal split, never random.** Train 2026-08-01..24, test 08-25..31. Index
  maps are built from training only, so the test window cannot define the item
  space.
* **Two user representations.** Item-item similarity uses flat co-occurrence
  (stable). The *profile* used at serving time is recency-decayed, because a
  game played yesterday predicts better than one played three weeks ago -
  measured at 38.2% vs 32.3% replay probability.
* **Train wide, serve narrow.** All trainable games enter the matrix; only
  nameable ones can ever be recommended. That filter belongs at serving time.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os

import numpy as np
from scipy import sparse

from src.pipeline import game_features, name_bridge
from src.recsys import catalog as cat

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ART = os.path.join(REPO, "artifacts")

SPLIT_DATE = "2026-08-25"
RECENCY_HALFLIFE_DAYS = 10.0     # profile weight halves every N days


def _conf(stake):
    """Implicit-feedback confidence. log1p damps whales without discarding them."""
    return float(np.log1p(max(stake, 0.0)))


def build(data_dir, split_date=SPLIT_DATE, use_sb=True):
    ca_path = os.path.join(data_dir, "CA_Player.csv")
    mom_path = os.path.join(data_dir, "CA_MOM.csv")
    ev_paths = [os.path.join(data_dir, f) for f in
                ("top_casino_users_event_logs.csv", "top_sport_users_event_logs.csv")]
    ev_paths = [p for p in ev_paths if os.path.exists(p)]

    print("reading", ca_path)
    rows = []
    with open(ca_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    print("  rows %s" % format(len(rows), ","))

    # ---- catalogue: code families + parsed titles ------------------------
    games = cat.build(rows)
    families = cat.summarise(games)

    # ---- name bridge: recover titles for opaque codes --------------------
    bridged = {}
    if ev_paths:
        print("resolving opaque codes against event logs ...")
        bridged = name_bridge.resolve(rows, ev_paths)
        gained = 0
        for code, info in bridged.items():
            g = games.get(code)
            if g is None or g.title:
                continue
            g.title = info["title"]
            g.family = cat.NAMED
            g.studio = g.studio or info.get("provider")
            gained += 1
        print("  resolved %d codes, %d newly nameable" % (len(bridged), gained))

    # ---- content features from 12 months of CA_MOM -----------------------
    feats = {"months": [], "games": {}}
    if os.path.exists(mom_path):
        print("reading", mom_path)
        feats = game_features.build(mom_path)
        print("  %d games, %d months" % (len(feats["games"]), len(feats["months"])))

    # ---- aggregate interactions -----------------------------------------
    agg = {"train": collections.defaultdict(float), "test": collections.defaultdict(float)}
    per_day = collections.defaultdict(lambda: collections.defaultdict(set))
    dates = set()
    dropped = collections.Counter()

    for r in rows:
        code = (r.get("reporting_bet_type") or "").strip()
        g = games.get(code)
        if g is None or g.family == cat.NON_GAME:
            dropped["non_game"] += 1
            continue
        try:
            stake = float(r.get("total_stake_amt") or 0.0)
        except (TypeError, ValueError):
            dropped["unparseable"] += 1
            continue
        if stake < 0:
            dropped["negative_stake"] += 1      # refunds / corrections
            continue
        if stake == 0:
            dropped["zero_stake"] += 1
            continue
        d = r["local_transaction_date"]
        dates.add(d)
        half = "train" if d < split_date else "test"
        agg[half][(r["PlayerID"], code)] += stake
        if half == "train":
            per_day[r["PlayerID"]][d].add(code)

    train_days = sorted(d for d in dates if d < split_date)
    idx_of_day = {d: i for i, d in enumerate(train_days)}
    last_day = len(train_days) - 1

    # Recency-decayed profile: each active day contributes 0.5 ** (age/halflife).
    recency = collections.defaultdict(float)
    for p, by_day in per_day.items():
        for d, codes in by_day.items():
            w = math.pow(0.5, (last_day - idx_of_day[d]) / RECENCY_HALFLIFE_DAYS)
            for code in codes:
                recency[(p, code)] += w

    print("dropped rows:", dict(dropped))

    # ---- index maps: TRAIN ONLY -----------------------------------------
    players = sorted({p for p, _ in agg["train"]})
    items = sorted({c for _, c in agg["train"]} | {c for _, c in agg["test"]})
    uidx = {p: i for i, p in enumerate(players)}
    iidx = {c: i for i, c in enumerate(items)}
    shape = (len(uidx), len(iidx))

    def matrix(pairs, transform):
        r_, c_, v_ = [], [], []
        for (p, code), val in pairs.items():
            if p in uidx and code in iidx:
                r_.append(uidx[p])
                c_.append(iidx[code])
                v_.append(transform(val))
        return sparse.csr_matrix((v_, (r_, c_)), shape=shape, dtype=np.float32)

    X_train = matrix(agg["train"], _conf)
    X_test = matrix(agg["test"], _conf)
    X_recent = matrix(recency, float)
    print("train %s nnz | test %s nnz | recency %s nnz"
          % (format(X_train.nnz, ","), format(X_test.nnz, ","), format(X_recent.nnz, ",")))

    # ---- day-to-day sequence transitions ---------------------------------
    # T[i,j] = played i on one active day, j on the NEXT active day.
    # CA_Player is daily-aggregated so within-day order is lost; day-level order
    # is what the data supports, and it covers 76% of players. Session-level
    # sequence was considered and rejected: only 91 players have event logs.
    tr, tc, tv = [], [], []
    trans_count = 0
    for p, by_day in per_day.items():
        ds = sorted(by_day)
        for a, b in zip(ds, ds[1:]):
            trans_count += 1
            for x in by_day[a]:
                if x not in iidx:
                    continue
                xi = iidx[x]
                for y in by_day[b]:
                    if y != x and y in iidx:
                        tr.append(xi)
                        tc.append(iidx[y])
                        tv.append(1.0)
    T = sparse.csr_matrix((tv, (tr, tc)), shape=(len(iidx), len(iidx)), dtype=np.float32)
    T.sum_duplicates()
    print("sequence: %s transitions, %s distinct pairs"
          % (format(trans_count, ","), format(T.nnz, ",")))

    # ---- sportsbook cross-signal (optional) ------------------------------
    sb_players = {}
    sb_path = os.path.join(data_dir, "SB_Player.csv")
    if use_sb and os.path.exists(sb_path):
        print("reading", sb_path)
        sport = collections.defaultdict(collections.Counter)
        with open(sb_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                p = r.get("PlayerID")
                if p in uidx:
                    sport[p][r.get("Sport_name_english") or "?"] += 1
        for p, c in sport.items():
            top, _ = c.most_common(1)[0]
            sb_players[p] = {"top_sport": top, "bets": int(sum(c.values()))}
        print("  %s casino players also bet sport (%.1f%%)"
              % (format(len(sb_players), ","), 100 * len(sb_players) / max(len(uidx), 1)))

    # ---- assemble catalogue ---------------------------------------------
    catalog = {}
    fg = feats.get("games", {})
    keep = ("first_month", "months_active", "age_months", "is_new", "momentum",
            "payout_ratio", "has_jackpot", "jackpot_share", "bonus_share",
            "lifetime_stake")
    for code, g in games.items():
        d = g.as_dict()
        f = fg.get(code)
        if f:
            d.update({k: f[k] for k in keep})
        if code in bridged:
            d["title_source"] = "event_log_bridge"
            d["title_votes"] = bridged[code]["votes"]
        catalog[code] = d

    disp = sorted(iidx[c] for c, d in catalog.items() if d.get("displayable") and c in iidx)
    new_items = sorted(iidx[c] for c, d in catalog.items()
                       if c in iidx and d.get("displayable") and d.get("is_new"))
    jack_items = sorted(iidx[c] for c, d in catalog.items()
                        if c in iidx and d.get("displayable") and d.get("has_jackpot"))

    os.makedirs(ART, exist_ok=True)
    with open(os.path.join(ART, "catalog.json"), "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, indent=1, ensure_ascii=False)
    np.savez_compressed(
        os.path.join(ART, "interactions.npz"),
        train_data=X_train.data, train_indices=X_train.indices, train_indptr=X_train.indptr,
        test_data=X_test.data, test_indices=X_test.indices, test_indptr=X_test.indptr,
        rec_data=X_recent.data, rec_indices=X_recent.indices, rec_indptr=X_recent.indptr,
        shape=np.array(shape),
        players=np.array(players, dtype=object), items=np.array(items, dtype=object),
        displayable=np.array(disp, dtype=np.int32),
        new_items=np.array(new_items, dtype=np.int32),
        jackpot_items=np.array(jack_items, dtype=np.int32))
    np.savez_compressed(
        os.path.join(ART, "sequence.npz"),
        data=T.data, indices=T.indices, indptr=T.indptr, shape=np.array(T.shape))
    with open(os.path.join(ART, "sb_players.json"), "w", encoding="utf-8") as fh:
        json.dump(sb_players, fh)

    report = {
        "sources": {"stake": os.path.basename(ca_path),
                    "monthly": os.path.basename(mom_path) if os.path.exists(mom_path) else None,
                    "event_logs": [os.path.basename(p) for p in ev_paths]},
        "rows": len(rows), "dropped": dict(dropped),
        "date_range": [min(dates), max(dates)], "split_date": split_date,
        "months_of_history": len(feats.get("months", [])),
        "players": shape[0], "games_trainable": shape[1],
        "games_displayable": len(disp),
        "games_named_by_bridge": sum(1 for d in catalog.values()
                                     if d.get("title_source") == "event_log_bridge"),
        "new_games": len(new_items), "jackpot_games": len(jack_items),
        "interactions_train": int(X_train.nnz), "interactions_test": int(X_test.nnz),
        "sequence_transitions": trans_count, "sequence_pairs": int(T.nnz),
        "sb_crossover_players": len(sb_players),
        "recency_halflife_days": RECENCY_HALFLIFE_DAYS,
        "families": families,
    }
    with open(os.path.join(ART, "dataset_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, ensure_ascii=False)
    print()
    print(json.dumps({k: v for k, v in report.items() if k != "families"}, indent=1))
    return report


def load():
    """Load everything serving and evaluation need."""
    z = np.load(os.path.join(ART, "interactions.npz"), allow_pickle=True)
    shape = tuple(z["shape"])

    def mk(a, b, c):
        return sparse.csr_matrix((z[a], z[b], z[c]), shape=shape)

    out = {
        "X_train": mk("train_data", "train_indices", "train_indptr"),
        "X_test": mk("test_data", "test_indices", "test_indptr"),
        "X_recent": mk("rec_data", "rec_indices", "rec_indptr"),
        "players": list(z["players"]), "items": list(z["items"]),
        "displayable": z["displayable"].tolist(),
        "new_items": z["new_items"].tolist(),
        "jackpot_items": z["jackpot_items"].tolist(),
    }
    with open(os.path.join(ART, "catalog.json"), encoding="utf-8") as fh:
        out["catalog"] = json.load(fh)
    seq = os.path.join(ART, "sequence.npz")
    if os.path.exists(seq):
        s = np.load(seq, allow_pickle=False)
        out["T"] = sparse.csr_matrix((s["data"], s["indices"], s["indptr"]),
                                     shape=tuple(s["shape"]))
    sb = os.path.join(ART, "sb_players.json")
    if os.path.exists(sb):
        with open(sb, encoding="utf-8") as fh:
            out["sb"] = json.load(fh)
    else:
        out["sb"] = {}
    return out


def main():
    ap = argparse.ArgumentParser(description="Build recommender artifacts from FEG exports.")
    ap.add_argument("--data-dir", required=True, help="folder holding the FEG CSVs")
    ap.add_argument("--split-date", default=SPLIT_DATE)
    ap.add_argument("--no-sb", action="store_true", help="skip the SB_Player cross-signal")
    args = ap.parse_args()
    build(args.data_dir, args.split_date, use_sb=not args.no_sb)


if __name__ == "__main__":
    main()
