# How it works

**PSK Game Recommender** · Team Q'Makers

Plain walkthrough of what happens between a player id and a row of games. Every
formula below is the code, not a simplification of it.

Run it while you read:

```bash
python -m src.cli status          # what is built
python -m src.cli explain <id>    # one player, with the model's reasoning
python -m src.cli demo            # server + browser
```

---

## 1. The shape of the problem

23,673 players × 3,202 games. Each cell is how much a player staked on a game
in a day. Density 0.31% — almost everything is empty, which is normal for
recommenders and is why we cannot simply "predict the number".

The target is not a rating. It is: **which games will this player open next
week that they have never opened before?**

---

## 2. Three windows, and why

```
Aug 01 ────────── 17 │ 18 ──── 24 │ 25 ──── 31
      TRAIN          │ VALIDATION │    TEST
   features, CF,     │  labels,   │  read once,
   sequence matrix   │  tuning    │  never fitted
```

**This was wrong until late in the project.** An earlier version had only
train/test. The blend weights were swept **on the test set** and test numbers
reported from it — hyperparameter leakage, which quietly inflates every result.
The validation window exists so tuning and reporting use different data.

The correction moved the headline from 3.06× to **3.96×** for the blend. It went
*up*: with a shorter training window the popularity baseline degrades faster
than the personalised models do.

---

## 3. Stage 1 — candidate generation (not trained)

Two models propose ~200 games per player. Both are **closed-form counting**:
there is no loss function and no gradient descent, and calling them "trained"
would be overselling. They are standard algorithms — item-kNN and Markov
chains — and they are fast and stable.

### 3a. Item-item collaborative filtering

*"People who play this also play that."*

```python
Xn = X / ||each game's column||          # L2-normalise per game
S  = Xnᵀ · Xn                            # cosine similarity, every game pair
S  = S ⊙ (co / (co + 20))                # shrink low-co-occurrence pairs
score(u) = X[u] · S                      # your history, propagated
```

`src/recsys/item_item.py`. The shrinkage matters: two games co-played by three
people should not look as similar as two co-played by three hundred.

**A bug worth recording.** The popularity-correction parameter originally damped
item *columns* and then L2-normalised them. Cosine is scale-invariant per
column, so the damping cancelled exactly and every value of `alpha` produced
byte-identical output. It now applies to the similarity matrix.
Regression test: `test_popularity_correction_actually_has_an_effect`.

### 3b. Day-to-day sequence

*"After playing this, people often play that next."*

```python
T[i,j] = times a player played i one active day and j the next
T      = T / (row_sum + 5)               # → P(play j next | played i)
score(u) = recency_weighted_history[u] · T
```

`src/recsys/hybrid.py`. The profile is **recency-decayed** — each active day
counts `0.5 ** (age / 10 days)` — so yesterday steers more than three weeks ago.

**Why day-level and not session-level.** The brief asked for a session-sequence
model. Only **91 of 26,904 players** have event-log data (0.3%), so a session
model would serve almost nobody. `CA_Player` is daily-aggregated: within-day
order is lost, but day-to-day order survives and covers **76% of players** with
114,898 transitions.

Recency was measured *before* building: P(replay a game) is **38.2%** the next
day against **32.3%** at 8–14 days. Real, but a 1.18× ratio — so sequence is a
strong signal, not a magic one.

---

## 4. Stage 2 — the trained ranker

**This is the part that is genuinely trained.** `src/recsys/ranker.py`.

- **Model:** `sklearn.linear_model.LogisticRegression`, fitted with a loss
  function on labelled examples.
- **Labels:** for each (player, candidate), `1` if the player played it in the
  validation week, else `0`. ~200,000 rows, 8.1% positive.
- **Negatives** are sampled from the generated candidates, never from the whole
  catalogue — random negatives would make the task trivially separable and
  produce a model that scores beautifully and ranks badly.
- **Features** (`src/recsys/features.py`), all from the train window:

| Group | Features |
|---|---|
| Candidate scores | `cf_score`, `seq_score` |
| Player × game fit | `provider_affinity`, `provider_recency`, `type_affinity` |
| Game properties | `pop_log`, `momentum`, `age_months`, `is_new`, `has_jackpot`, `payout_ratio`, `game_stake_pct` |
| Player state | `player_n_games`, `player_total_conf` |

A model leaning entirely on the first group has learned nothing the candidate
generator did not already know. The second group is where a ranker earns its
keep — and `provider_affinity` does carry weight.

### Why logistic regression, not gradient boosting

Chosen **before** reading the test set, on two stated grounds:

1. **It is interpretable.** Contribution = coefficient × standardised value,
   and those sum to the logit. That is exactly what the "why this tile" panel
   shows and what EU AI Act explainability expects. A boosted ensemble has no
   such exact decomposition.
2. **The boosted model was memorising** — training accuracy 0.920 against
   logistic regression's 0.656, on an 8.1%-positive problem.

That call was later vindicated, and the way it happened is worth knowing:
**GBM scored higher on a player-split validation (0.173 vs 0.105) and lower on
the temporally separate test set (0.059 vs 0.071).** A player split shares the
same week as the labels, so memorised week-specific patterns transfer there but
not to a different week. If you only ever split by user, this is invisible.

---

## 5. From scores to rows

`src/recsys/serve.py`. Six rows, named as the live psk.hr lobby names them.

| Row | Source | Personalised |
|---|---|---|
| **Nastavi igrati** | recency-weighted history | yes |
| **Preporučeno za tebe** | trained ranker | yes |
| **Otkrij nešto novo** | trained ranker, global top-50 removed | yes |
| **Jackpoti** | jackpot games, ranker-ordered | yes |
| **Popularno** | global most-played — the row PSK ships today | no |
| **Nove igre** | first released in the last 3 months | no |

Rules applied to every row: only nameable games can be *recommended*; at most 3
games per provider (lifted for a player's own history); no game appears twice.

**Responsible play runs before scoring, not after.** A self-excluded account is
never scored at all — the API returns zero rows, not a filtered list. From
`MODERATE` risk, every engagement row is withheld and only *Nastavi igrati*
survives.

---

## 6. Two data problems solved on the way

**The name bridge** (`src/pipeline/name_bridge.py`). The overwhelming majority
of stake sat on opaque codes like `pop_9f571b7a_egtfeg` that could never be
shown to a player; **58.4% still does**, and the codes this bridge resolved
carry **37% of all stake** on their own. All 91
event-log players also appear in the stake export, so co-occurrence on
(player, day), constrained to matching providers, identifies which code is which
game. It recovered **180 codes, 128 newly nameable**, taking the recommendable
catalogue from 351 to **479 games**.

The check that it is not wishful matching: it independently produced
`gpas_3chken_pop` → *"4 Crazy Cluckers"* (111 votes) and `gpas_wpisto_pop` →
*"Mega Fire Blaze: Wild Pistolero"* (48 votes). Both slugs decode to their
resolved titles, which the algorithm has no way to read.

**Twelve months of game features** (`src/pipeline/game_features.py`).
`CA_MOM.csv` was unused and holds a year, not a month. It gives real release
age (275 genuinely new titles, rather than "absent from our window"), stake
momentum, jackpot eligibility and a payout-ratio proxy. Payout ratio is a
**similarity feature only** — never used to rank and never shown, because
advertising "this game pays more" is the inducement the AI Act prohibits.

---

## 7. Results

Tail discovery (global top-50 removed — where 76.5% of discovery happens),
test window, NDCG@10:

| Model | NDCG@10 | Coverage | vs popularity |
|---|---|---|---|
| **ranker (trained)** | **0.0708** | 732 | **4.28×** |
| hybrid blend | 0.0655 | 773 | 3.96× |
| sequence | 0.0649 | 887 | 3.92× |
| item-item CF | 0.0490 | 731 | 2.96× |
| most_played | 0.0165 | 29 | 1.00× |

On **overall** discovery, popularity still wins outright (0.305 vs 0.056 for
CF). That is why *Popularno* is kept unchanged. Full tables, protocol and
limits: [`evaluation.md`](evaluation.md).

---

## 8. What it does not do

- No online experiment. Every number is offline, on one month. "Longer
  sessions" is an assumption an A/B test must check.
- No thumbnails — the data has none, so tiles are generated art.
- No session-level model, for the coverage reason in §3b.
- No live exclusion-register integration: the gate is implemented and tested,
  the caller supplies the flag.
