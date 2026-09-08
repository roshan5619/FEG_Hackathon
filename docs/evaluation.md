# Evaluation

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

> **Headline, stated up front because it is not the flattering version:
> collaborative filtering loses to "most played" on next-game prediction, and
> loses badly.** It wins decisively on the tail, which is where three quarters
> of discovery actually happens. That split is the entire product argument, and
> everything below is the evidence for it.

Reproduce with:

```bash
python -m src.pipeline.build_dataset --source path/to/CA_Player.csv
python -m src.recsys.evaluate
```

---

## 1. Protocol

**Data.** `CA_Player.csv` — 741,679 rows of daily per-player stake by game,
brand `hr`, 2026-08-01 → 2026-08-31.

**Split.** Temporal. Train 08-01→24, test 08-25→31. Never random: a random
split lets a player's future leak into their own training history and inflates
every metric.

**Index maps are built from training only**, so the test window cannot define
the item space. 8,960 test interactions belong to players unseen in training —
genuine cold-start users, correctly excluded from the cohort rather than
scored.

**Matrix.** 23,673 players × 3,202 games, 296,205 training interactions
(density 0.39%). Confidence is `log1p(stake)`: raw stake spans orders of
magnitude and one whale would otherwise dominate every similarity.

**One row was excluded from the item space entirely.** The export contains a
"game" called `NA - Deposit / Withdrawal / Corrections` (48 rows). Left in, it
co-occurs with everything and becomes the most similar item to every game on
the site. It is an accounting record, not gameplay.

### The task split, and why it exists

A median **78%** of a player's launches sit in their top-3 games. A model
scored on all test interactions can simply re-serve what someone already plays,
post an excellent precision@10, and be useless as a discovery widget. One
blended number would flatter every model here. So:

| Task | Ground truth | Candidate pool |
|---|---|---|
| **discovery** | test games the player has never played | everything except their history |
| **tail_discovery** | the same, minus the global top-50 | the same, minus the global top-50 |
| **repeat** | test games they have played before | their history only |

---

## 2. Results

k = 10. Coverage = distinct games ever recommended. Novelty = mean
unpopularity of what was recommended (higher = more obscure).

### 2.1 Discovery — popularity wins outright

| Model | Cohort | P@10 | R@10 | **NDCG@10** | Coverage | Novelty |
|---|---|---|---|---|---|---|
| **most_played** | 9,102 | 0.0841 | 0.3908 | **0.3050** | 41 | 0.002 |
| provider_popular | 9,102 | 0.0605 | 0.2380 | 0.1737 | 288 | 0.010 |
| most_staked | 9,102 | 0.0387 | 0.1201 | 0.0694 | 45 | 0.002 |
| item_item CF | 9,102 | 0.0263 | 0.0674 | 0.0565 | 726 | 0.019 |
| random | 9,102 | 0.0016 | 0.0031 | 0.0025 | 3,202 | 0.503 |
| user_top | 9,102 | 0.0016 | 0.0024 | 0.0022 | 118 | 0.464 |

**Popularity beats collaborative filtering 5.4×.** This is not a tuning
failure — it was tested:

- popularity correction α swept over {+0.5, 0, −0.3, −0.6, −1.0, −1.5}: NDCG
  rose monotonically as α went negative (0.0565 → 0.1775) but only by
  converging on the popularity baseline, with coverage collapsing 726 → 87.
- shrinkage swept over {0, 20}, `top_k` over {200, 300}.
- a principled hybrid `norm(CF) + w·norm(popularity)` swept over
  w ∈ {0, 0.05, 0.15, 0.3, 0.6, 1, 2, 5}: best NDCG **0.2453** at w=5, still
  below plain popularity, and by then it *is* popularity.

**Why**, and this is a real finding about PSK rather than an artefact:
next-game choice is overwhelmingly driven by what is already popular. Spearman
correlation between training popularity and next-week discovery count is
**0.79**. The top 10 games take **24.9%** of all discovery plays; one title,
*Goal Goal Goal: Cash Collect*, takes **13% on its own**.

### 2.2 Tail discovery — collaborative filtering wins

Global top-50 removed from both candidates and ground truth. **76.5% of all
discovery plays live here.**

| Model | Cohort | P@10 | R@10 | **NDCG@10** | Coverage | Novelty |
|---|---|---|---|---|---|---|
| **item_item CF** | 6,323 | 0.0228 | 0.0581 | **0.0462** | **680** | 0.033 |
| provider_popular | 6,323 | 0.0209 | 0.0460 | 0.0359 | 292 | 0.028 |
| most_staked | 6,323 | 0.0135 | 0.0303 | 0.0220 | 31 | 0.019 |
| most_played | 6,323 | 0.0135 | 0.0280 | 0.0205 | 37 | 0.017 |
| random | 6,323 | 0.0020 | 0.0029 | 0.0026 | 3,152 | 0.510 |
| user_top | 6,323 | 0.0012 | 0.0018 | 0.0017 | 118 | 0.517 |

**CF beats popularity 2.25× on NDCG@10 with 18× the catalogue coverage** (680
games against 37). Excluding the top-20 or top-100 instead of the top-50 gives
1.45× and 2.15× — the result is not an artefact of where the line is drawn.

Popularity cannot serve the tail. It only knows 37 games.

### 2.3 Repeat — the player's own history wins, as it should

| Model | Cohort | P@10 | R@10 | **NDCG@10** |
|---|---|---|---|---|
| **user_top** | 9,257 | 0.2861 | 0.8264 | **0.7289** |
| provider_popular | 9,257 | 0.2403 | 0.7584 | 0.5876 |
| most_played | 9,257 | 0.2318 | 0.7457 | 0.5727 |
| random | 9,257 | 0.2143 | 0.7108 | 0.5056 |
| item_item CF | 9,257 | 0.2135 | 0.6977 | 0.4858 |

Note `random` scores 0.5056 here. That is not a bug: the repeat task ranks only
within a player's own history, and a median player has few games, so any
ordering does well. **The repeat task is easy and we label it as such.** It
justifies a "Continue playing" row; it justifies nothing else.

---

## 3. What no model can reach

**92 games have zero training interactions** — titles launched or first played
during the test week (*Pandora's Treasure*, *Asian Palace v1*, *Wild Fortune*).
They account for **11.2% of all discovery plays** and **12.1% of the evaluation
cohort's ground truth**.

No collaborative model can retrieve an item with no history. The **recall
ceiling for any CF model here is 87.9%**, and the only honest answer is a
separate "New releases" row — which is why the lobby has one.

---

## 4. What this means for the product

| Row | Model | Justified by |
|---|---|---|
| Trending now | `most_played` | §2.1 — popularity wins the head outright |
| Continue playing | `user_top` | §2.3 — 0.73 NDCG, and honestly labelled as easy |
| Picked for you | item-item CF | §2.2 |
| Discover something new | item-item CF, top-50 removed | §2.2 — 2.25× and 18× coverage |
| New releases | cold items | §3 — 12.1% of discovery, unreachable otherwise |

**We did not replace the row PSK already ships.** `most_played` is
*Najigranije*, live today, and it wins its job. The recommender is additive: it
reaches 680 games where popularity reaches 37.

---

## 5. Limits, stated plainly

1. **One month.** No seasonality, no tournament effects, no long-horizon
   validation. The test window is 7 days.
2. **Offline metrics are not engagement.** Every number here measures
   next-week game selection. The stated goal — longer sessions — is a
   *different* quantity that only an online A/B test can measure. Catalogue
   coverage is our proxy and a proxy is what it remains.
3. **Position and exposure bias.** Players choose from what PSK already shows
   them, and today that is a popularity row. Popularity therefore partly
   predicts its own success. This biases §2.1 *in favour of* `most_played` and
   is a further reason not to read that table as the whole story.
4. **83% of stake is on unnameable games.** They train the model but can never
   be displayed, so the servable catalogue is 351 of 3,202 games. A game
   catalogue from FEG would remove this limit entirely.
5. **No confidence intervals.** Differences of the size in §2.2 (2.25×) are
   unlikely to be noise at n=6,323, but we have not bootstrapped them.
6. **ALS is implemented and not reported.** It is in `src/recsys/item_item.py`
   and runs via `--all`. We did not include it in the headline tables because
   we have not tuned it, and reporting an untuned model beside tuned ones
   would be misleading in either direction.

---

## 6. Reproducibility

Every table above regenerates from `artifacts/eval_full.json`, written by
`python -m src.recsys.evaluate`. The two bugs found during this work are both
covered by regression tests in `tests/test_recsys.py`:

- `test_accounting_row_is_not_a_game` — the deposit/withdrawal row
- `test_popularity_correction_actually_has_an_effect` — the α parameter was
  silently a no-op, because the code damped item columns and then L2-normalised
  them, and cosine is scale-invariant per column
- `test_item_item_beats_popularity_on_tail_discovery` — the headline claim,
  asserted against the real artifacts
