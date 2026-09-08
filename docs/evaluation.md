# Evaluation

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

> **Headline, stated up front because it is not the flattering version:
> collaborative filtering loses to "most played" on next-game prediction, and
> loses badly.** Personalisation wins decisively on the *tail*, which is where
> three quarters of discovery actually happens. That split is the entire product
> argument.
>
> **This document was rewritten after two leaks were found and fixed.** An
> earlier version had only train/test splits and swept blend weights on the test
> set; a later one trained the served ranker on test labels. Both are described
> in §7. Every number below comes from a three-way split with the test window
> read once.

Reproduce with:

```bash
python -m src.pipeline.build_dataset --source path/to/CA_Player.csv
python -m src.recsys.evaluate
```

---

## 1. Protocol

**Data.** `CA_Player.csv` — 741,679 rows of daily per-player stake by game,
brand `hr`, 2026-08-01 → 2026-08-31.

**Split.** Temporal, three ways. **Train 08-01→17** (features, item-item
similarity, sequence matrix), **validation 08-18→24** (ranker labels, blend
weights, model selection), **test 08-25→31** (read once). Never random: a random
split lets a player's future leak into their own training history.

**Index maps are built from training only**, so the test window cannot define
the item space. 8,960 test interactions belong to players unseen in training —
genuine cold-start users, correctly excluded from the cohort rather than
scored.

**Matrix.** 23,673 players × 3,202 games. 223,531 train / 115,086 validation /
99,930 test interactions. Confidence is `log1p(stake)`: raw stake spans orders of
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

k = 10. Coverage = distinct games ever recommended. "vs popularity" is the
multiple over `most_played`, the row psk.hr ships today. Every figure is
regenerated from `artifacts/eval_full.json` — none is typed by hand.

### 2.1 Discovery — popularity wins outright

| Model | Cohort | P@10 | R@10 | **NDCG@10** | Coverage | vs popularity |
|---|---|---|---|---|---|---|
| `most_played` | 8,304 | 0.0907 | 0.3838 | **0.2110** | 32 | 1.00x |
| provider_popular | 8,304 | 0.0586 | 0.2057 | **0.1350** | 275 | 0.64x |
| **Trained ranker** | 8,304 | 0.0378 | 0.0823 | **0.0677** | 720 | 0.32x |
| Blend (sequence + CF) | 8,304 | 0.0363 | 0.0732 | **0.0650** | 583 | 0.31x |
| Sequence | 8,304 | 0.0356 | 0.0708 | **0.0632** | 645 | 0.30x |
| most_staked | 8,304 | 0.0265 | 0.0624 | **0.0489** | 37 | 0.23x |
| Item-item CF | 8,304 | 0.0254 | 0.0568 | **0.0489** | 740 | 0.23x |
| random | 8,304 | 0.0018 | 0.0029 | **0.0026** | 3202 | 0.01x |
| user_top | 8,304 | 0.0019 | 0.0023 | **0.0025** | 104 | 0.01x |

**Popularity beats every personalised model on raw next-game prediction.** Not a
tuning failure; it was swept extensively. Next-game choice at PSK is
overwhelmingly driven by what is already popular — Spearman **0.79** between
training popularity and next-week discovery, and one title,
*Goal Goal Goal: Cash Collect*, takes **13%** of all discovery plays alone.

That is why the *Popularno* row is kept unchanged.

### 2.2 Tail discovery — where personalisation wins

Global top-50 removed from both candidates and ground truth. **76.5% of all
discovery plays live here**, and popularity can only ever reach ~29 games.

| Model | Cohort | P@10 | R@10 | **NDCG@10** | Coverage | vs popularity |
|---|---|---|---|---|---|---|
| **Trained ranker** | 5,921 | 0.0369 | 0.0831 | **0.0708** | 732 | 4.28x |
| Blend (sequence + CF) | 5,921 | 0.0321 | 0.0788 | **0.0655** | 773 | 3.96x |
| Sequence | 5,921 | 0.0324 | 0.0785 | **0.0649** | 887 | 3.92x |
| Item-item CF | 5,921 | 0.0231 | 0.0626 | **0.0490** | 731 | 2.96x |
| provider_popular | 5,921 | 0.0238 | 0.0519 | **0.0414** | 253 | 2.51x |
| most_staked | 5,921 | 0.0155 | 0.0327 | **0.0258** | 26 | 1.56x |
| `most_played` | 5,921 | 0.0103 | 0.0234 | **0.0165** | 29 | 1.00x |
| random | 5,921 | 0.0023 | 0.0042 | **0.0034** | 3152 | 0.21x |
| user_top | 5,921 | 0.0015 | 0.0020 | **0.0018** | 108 | 0.11x |

The **trained ranker** — a scikit-learn logistic regression over 14 features,
fitted on 199,792 labelled rows (8.1% positive) — is the best model, and it
beats the untrained blend whose candidates it re-ranks. Excluding the top-20 or
top-100 instead of the top-50 preserves the ordering, so the result is not an
artefact of where the line is drawn.

### 2.3 Repeat — the player's own history wins, as it should

| Model | Cohort | P@10 | R@10 | **NDCG@10** | Coverage | vs popularity |
|---|---|---|---|---|---|---|
| user_top | 7,781 | 0.2856 | 0.8444 | **0.7417** | 2401 | 1.26x |
| Sequence | 7,781 | 0.2616 | 0.7992 | **0.6124** | 1924 | 1.04x |
| provider_popular | 7,781 | 0.2490 | 0.7844 | **0.6099** | 1812 | 1.04x |
| Blend (sequence + CF) | 7,781 | 0.2558 | 0.7866 | **0.5978** | 1906 | 1.02x |
| `most_played` | 7,781 | 0.2387 | 0.7706 | **0.5870** | 1778 | 1.00x |
| most_staked | 7,781 | 0.2404 | 0.7722 | **0.5816** | 1782 | 0.99x |
| random | 7,781 | 0.2260 | 0.7460 | **0.5410** | 2548 | 0.92x |
| Item-item CF | 7,781 | 0.2234 | 0.7283 | **0.5101** | 1889 | 0.87x |
| **Trained ranker** | 7,781 | 0.0017 | 0.0042 | **0.0032** | 10 | 0.01x |

`random` scores well here because the repeat task ranks only within a player's
own history, and a median player has few games. **The repeat task is easy and we
label it as such.** It justifies a *Nastavi igrati* row and nothing else.

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
| **Popularno** | `most_played` | §2.1 — popularity wins the head outright |
| **Nastavi igrati** | recency-weighted history | §2.3 — easy task, honestly labelled |
| **Preporučeno za tebe** | trained ranker | §2.2 |
| **Otkrij nešto novo** | trained ranker, top-50 removed | §2.2 — 4.28x and 25x coverage |
| **Jackpoti** | jackpot games, ranker-ordered | 136 titles, from 12 months of CA_MOM |
| **Nove igre** | real release age | 275 titles first seen in the last 3 months |

**We did not replace the row PSK already ships.** `most_played` is
*Najigranije*, live today, and it wins its job. The recommender is additive: it
reaches **732 games where popularity reaches 29**.

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
   be *recommended*, so the recommendable catalogue is 479 of 3,202 (the name bridge recovered 128). The same
   gap means **54% of players have no nameable game in their own history** —
   "Continue playing" therefore labels those by provider and kind
   ("Amusnet slot"), marked `named: false` and visibly dimmed, which lifts that
   row from 46.5% to 100% of players. A game catalogue from FEG would remove
   the limit entirely.
5. **No confidence intervals.** Differences of the size in §2.2 (4.28x) are
   unlikely to be noise at n=6,323, but we have not bootstrapped them.
6. **Only one model family was taken to completion.** An implicit-feedback
   ALS implementation was written and then removed rather than shipped
   untuned: reporting an untuned latent-factor model beside a tuned
   neighbourhood one would have been misleading in either direction, and
   leaving unused code in the repository is worse. Matrix factorisation
   remains the obvious next comparison.

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
