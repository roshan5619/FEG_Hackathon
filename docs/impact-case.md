# Impact case & cost-value analysis

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

---

## 0. What we claim, and what we refuse to claim

**Claimed, and measured on FEG's own data:**

| | |
|---|---|
| Catalogue a player can actually be shown | **732 games**, against **29** from the popularity row — **25×** |
| Ranking accuracy on the tail (NDCG@10, held-out week) | **0.0708** vs **0.0165** — **4.28×** |
| Marginal cost per recommendation | ~**25 ms**, no GPU, 18 MB of artifacts |
| Integration | six rows added alongside existing psk.hr surfaces, each behind its own flag |

**Refused: a revenue uplift number.** We looked for one. The data does not
support it, and §3 shows the tests that failed. A claim that collapses under
one follow-up question is worth less than an honest gap.

---

## 1. The problem, in money

`CA_Player.csv`, August 2026, 23,673 players × 3,202 games.

- **€19.6M of stake — 13.7% of the entire window — sits on games a player was
  playing for the first time.** 138,041 first-time adoptions in 14 days, median
  **€16.16** each.
- That flow is currently served by **search** — the single most common route to
  a game in the event logs (3,580 launches, ahead of every browsable surface) —
  and by one global row, *Najigranije*, identical for all 23,673 players.
- **The popularity row can only ever surface 29–32 games** of 3,202.

So a seventh of all stake depends on discovery, and discovery is served by a
search box and a list that never changes.

**Tail games are not the cheap end.** Median stake on a newly-adopted tail game
is **€17.00**, against **€10.50** on a top-50 game. (Head games have a higher
*mean*, €157 vs €102 — blockbusters carry the whales.) The long tail is worth
defending on its own economics.

---

## 2. What the recommender demonstrably changes

Held-out test week, tail discovery — outside the global top 50, where **76.5%**
of all discovery happens:

| Model | NDCG@10 | Games reachable | vs popularity |
|---|---|---|---|
| **Trained ranker** | **0.0708** | **732** | **4.28×** |
| Blend (sequence + CF) | 0.0655 | 773 | 3.96× |
| Sequence only | 0.0649 | 887 | 3.92× |
| Item-item CF | 0.0490 | 731 | 2.96× |
| `most_played` (live today) | 0.0165 | 29 | 1.00× |

On **overall** discovery, popularity still wins outright (0.2110 vs 0.0489 for
CF). We kept it unchanged as the *Popularno* row for exactly that reason. The
recommender is additive: it reaches the 3,000 games popularity structurally
cannot.

---

## 3. The claims we tested and could not make

We tried to establish that broader discovery drives value. Three tests, three
negative results. All are reproducible from `CA_Player.csv`.

### 3.1 Breadth correlates with value — but it is confounded

| Distinct games | Players | Median stake | Median active days |
|---|---|---|---|
| 1–2 | 8,681 | €16 | 1 |
| 3–5 | 5,728 | €137 | 3 |
| 6–10 | 4,413 | €685 | 5 |
| 11–25 | 4,597 | €1,924 | 8 |
| 26+ | 3,433 | €5,446 | 16 |

A 334× spread. Tempting, and unusable: active players play more games almost by
definition. The correlation is real; the causal direction is not established.

### 3.2 Adoption does not improve retention once matched on activity

Of 12,743 players active in week 3 with prior history, 75% tried at least one
new game. Raw retention into the held-out week 4 favoured them — 77.5% against
74.0%. Matched on how active they already were, the effect disappears:

| Week-3 days played | Adopters retained | Non-adopters retained |
|---|---|---|
| 1 day | 56.8% | **57.6%** |
| 2–3 days | 78.1% | 77.9% |
| 4–7 days | 94.2% | **96.5%** |

### 3.3 Adoption is associated with *lower* subsequent stake

Matched on week-3 stake band, median week-4 stake:

| Week-3 stake | Adopters | Non-adopters |
|---|---|---|
| €50–200 | €34.65 | **€49.15** |
| €200–1,000 | €155.35 | **€245.97** |
| €1,000–5,000 | €855.51 | **€1,098.95** |

Consistently lower. On this evidence, "personalised discovery grows revenue" is
not a claim we can make.

---

## 4. The reframe — and it is a better story

The obvious reading of §3.3 is that discovery destroys value. We think the
opposite, and the mechanism is worth FEG's attention regardless of whether this
prototype ships:

> **Exploration currently correlates with lower value because exploration
> currently fails.**

A player hunting through a search box and a 32-game list is behaving like
someone who has not found what they want. Exploration on psk.hr today is
plausibly a **symptom of dissatisfaction, not a driver of it** — which is
exactly what §3.3 would look like.

That changes the product's job. It is not to make players try *more* games. It
is to make the exploration they are **already doing** — 138,041 adoptions and
€19.6M a fortnight — succeed faster and more often.

This is a hypothesis. It is falsifiable, and §6 defines the experiment.

---

## 5. Cost

### 5.1 Build

| Workstream | Effort | Status |
|---|---|---|
| Pipeline, catalogue, name bridge, three-way split | — | **done** |
| Candidate models (item-item CF, day-sequence) | — | **done** |
| Trained re-ranker + evaluation harness | — | **done** |
| Serving layer, API, CLI, responsible-play gates | — | **done** |
| Vue 3 lobby components | 3–4 weeks | not built |
| Kafka consumer + Redis player vectors | 2–3 weeks | not built |
| A/B framework + impression logging | 2 weeks | not built |
| Game catalogue integration (titles, art) | 1 week | **blocked on FEG** |

**Critical path ≈ 6–8 weeks, 2 engineers.** The model is finished and not on it.

### 5.2 Run — unusually cheap

- **Training:** sparse matrix products plus a logistic regression over ~200,000
  rows. Seconds, daily, on one core. **No GPU, no cluster, no model API.**
- **Serving:** **~25 ms** per lobby, zero I/O on the request path once the
  18 MB of artifacts are in memory.
- **No third-party ML service** and no per-inference cost.

The dominant marginal cost is the impression log needed for A/B measurement —
not the recommender.

### 5.3 The highest-return item is not engineering

**A game catalogue from FEG: code → title, category, thumbnail.** 58% of stake
sits on games we cannot name, so only **479 of 3,202** can be recommended. Our
name bridge recovered 128 of them from behavioural co-occurrence; a database
export would recover the rest. **One file, ~9× the addressable inventory.**

---

## 6. The experiment that would settle it

Because §3 is honest, the value case rests on a test, and the test is cheap.

- **Design:** A/B on the lobby. Control = today's static rows. Treatment = the
  six personalised rows. Randomise by player, run four weeks.
- **Primary metric:** *successful* discovery — first-time game adoptions
  **that are played again within 7 days**. This distinguishes "found something
  good" from "tried and bounced", which §3.3 cannot.
- **Secondary:** distinct games played, search-initiated launches (should
  **fall** if the lobby is working), days active, stake per active day.
- **Guardrail:** harmful-play indicator rate must not rise. Ship behind the
  responsible-play gates from day one.
- **What would falsify us:** if treatment shows no lift in repeat-played
  adoptions and no fall in search-initiated launches, the Discover row is not
  earning its screen space and should be cut.
- **Cost:** shadow mode first — score and log everything, render nothing —
  so the comparison starts before any player sees a change.

---

## 7. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Offline ranking accuracy does not translate to engagement | **High** | The core untested assumption. §6 is the test. Shadow mode makes waiting free. |
| The §4 reframe is wrong and discovery genuinely destroys value | **High** | Then the A/B shows it and the row is cut. Bounded downside: *Popularno* is retained unchanged, so the worst case costs screen space, not revenue. |
| Exposure bias flatters the popularity baseline | Medium | Players choose from what PSK shows them today. This biases §2 **against** the recommender, so the 4.28× is if anything understated. |
| One month of data, no seasonality | Medium | 12 months exist in `CA_MOM.csv` for game-level features; player-level is one month. Retrain daily. |
| 83% of catalogue unnameable | Medium | §5.3 — ask FEG for the catalogue. |
| Personalisation increases play for at-risk players | **High** | Hard gates run **before** scoring; from `MODERATE` every engagement row is withheld. Tested, not asserted — `docs/compliance-note.md`. |

---

## 8. Reproducing every figure

```bash
python -m src.cli build --data-dir <FEG csv folder>
python -m src.cli evaluate
```

§2 comes from `artifacts/eval_full.json`. §1 and §3 are single passes over
`CA_Player.csv`; the exact aggregations are described inline above and use no
data other than `PlayerID`, `reporting_bet_type`, `local_transaction_date` and
`total_stake_amt`.
