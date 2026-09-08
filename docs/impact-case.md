# Impact case & cost-value analysis

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

---

## 0. Summary

The lobby is static: 26,904 players see the same *Najigranije* row. We built a
hybrid personalised lobby and measured it against that incumbent rather than
against a straw man.

The result was not the one we wanted, and the honest version is the one that
makes the case:

- On **next-game prediction**, global popularity beats collaborative filtering
  outright — NDCG@10 **0.305** vs **0.056**. We do not claim otherwise, and we
  kept the popularity row because of it.
- On the **tail** — where **76.5%** of all discovery plays happen — CF beats
  popularity **2.25×** on NDCG@10 with **18×** the catalogue coverage: **680
  games against 37**.

The value proposition is therefore *not* "better predictions". It is
**catalogue reach**: 680 games become discoverable where 37 were before, for
the 3,000-game majority of the library that popularity can never surface.

---

## 1. The addressable problem, counted

| | |
|---|---|
| Players in the training window | **23,673** |
| Games in the catalogue | **3,202** |
| Games the popularity row can ever surface (top-10 @ k=10) | **41** |
| Share of the catalogue currently reachable by the lobby's main row | **1.3%** |
| Discovery plays occurring outside the global top-50 | **76.5%** |
| Most common route to a game today | **search** (3,580 launches — ahead of every browsable surface) |
| Games with zero play history (unreachable by any CF) | **92** (12.1% of discovery) |

**Search being the top route is the problem statement in one number.** If a
player has to type a game's name, the lobby did not surface it.

---

## 2. What the recommender changes

Measured, not modelled:

| Metric | Popularity row (today) | Item-item CF | Change |
|---|---|---|---|
| Distinct games recommended (tail, @10) | 37 | **680** | **18.4×** |
| NDCG@10 (tail discovery) | 0.0205 | **0.0462** | **2.25×** |
| Novelty (mean unpopularity) | 0.017 | 0.033 | 1.9× |
| Recall@10 (tail discovery) | 0.0280 | **0.0581** | 2.08× |

Cohort: 6,323 players with ≥3 games of history and a new tail game in the
held-out week.

---

## 3. Value model

### 3.1 Why there is no euro figure here

`CA_Player.csv` contains stake, but attributing incremental revenue to a lobby
row requires knowing what a player *would* have done otherwise — which needs an
online experiment, not a held-out week. **Inventing a revenue number from this
data would be exactly the borrowed-benchmark problem we set out to avoid.**

So the value is expressed in the quantity we can actually measure, and the
conversion to revenue is left to FEG, who have the ARPU we do not.

### 3.2 The mechanism, stated as a falsifiable claim

> A player shown 680 candidate games instead of 37 will find more games worth
> playing, and a player who finds more games worth playing stays longer.

The first half is measured (§2). **The second half is an assumption**, and it
is the one an A/B test must check. We are not going to dress it up as a result.

### 3.3 Three scenarios

Against a base of 23,673 monthly active players, expressed in *additional
players finding at least one new game per month*:

| | Assumption | Effect |
|---|---|---|
| **Pessimistic** | Tail exposure changes nothing; players who wanted the head still pick the head | **0** — the popularity row still serves them, so nothing is lost either |
| **Central** | The 2.08× tail recall improvement converts at a quarter of its offline rate | **~+1,900 players/month** find a new game they would not have found |
| **Optimistic** | Tail recall converts at half its offline rate, plus the "New releases" row captures part of the 12.1% cold-item discovery | **~+4,400 players/month** |

The pessimistic case is genuinely zero-loss, not a hedge: because the
popularity row is retained unchanged, the downside of this design is bounded at
the cost of screen space.

---

## 4. Cost

### 4.1 Build

| Workstream | Effort | Status |
|---|---|---|
| Pipeline, catalogue parser, temporal split | — | **done** |
| Item-item model + offline evaluation harness | — | **done** |
| Serving layer, API, responsible-play integration | — | **done** |
| Vue 3 lobby components | 3–4 weeks | not built |
| Kafka consumer + Redis player vectors | 2–3 weeks | not built |
| A/B framework + impression logging | 2 weeks | not built |
| Game catalogue integration (names, art, categories) | 1 week | **blocked on FEG** |

**Critical path ≈ 6–8 weeks** with 2 engineers. The model is finished and is
not on it.

### 4.2 Run

Cheap, and unusually so:

- **Training** is one sparse matrix product over 296,205 interactions —
  seconds, daily, on a single core. No GPU, no cluster.
- **Serving** is ~60 ms per lobby with zero I/O on the request path. The
  artifacts are 3.4 MB and fit in memory many times over.
- **No third-party ML service**, no per-inference cost, no model API.

The dominant marginal cost is the impression log needed for A/B measurement,
not the recommender.

### 4.3 The highest-return item is not engineering

**A game catalogue — code → title, category, thumbnail — from FEG.** 83% of
stake sits on games we cannot name, so the servable catalogue is 351 of 3,202.
That single file would multiply the addressable inventory ~9×, and it costs
FEG a database export rather than a sprint.

---

## 5. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Offline NDCG does not translate to engagement | **High** | The core untested assumption (§3.2). Shadow mode then A/B, measuring session length and breadth, not NDCG |
| Exposure bias flatters the popularity baseline | Medium | Players choose from what PSK shows them today. This biases §2 *against* us, so the tail result is if anything understated |
| One month of data; no seasonality | Medium | Retrain daily; revisit after a full quarter |
| 83% of catalogue undisplayable | Medium | Ask FEG for the catalogue (§4.3) |
| Personalisation increases play for at-risk players | **High** | Hard gates run before scoring; MODERATE+ withholds every engagement row. Tested, not asserted — `docs/compliance-note.md` |

---

## 6. What would change our mind

- If tail exposure shows no lift in breadth of play under A/B, the Discover row
  is not worth its screen space and should be cut.
- If the head/tail split is unstable across months, the top-50 boundary is
  arbitrary and the design needs rethinking.
- If a sequence-aware model beats item-item substantially on the tail, the
  neighbourhood approach should be replaced rather than tuned.
