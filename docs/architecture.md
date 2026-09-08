# Architecture

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

---

## 1. What this is

A recommendation layer that personalises the psk.hr casino lobby on login. It
does not replace the casino platform. It answers one question per request:
**given this player's history, what rows should their lobby show?**

Design constraint that shapes everything: **additive, not a re-platform.** The
popularity row PSK ships today (*Najigranije*) is kept, because the evaluation
says it wins its job. The recommender adds what popularity structurally cannot
do — reach the 3,000 games outside the top 50.

---

## 2. Components

```
  Browser                     ┌────────────────────────────────────┐
  ┌──────────────────┐        │  src/dashboard/index.html          │
  │ Personalised     │◄───────┤  rows · tiles · "why" · RG toggles │
  │ lobby            │        └──────────────┬─────────────────────┘
  └──────────────────┘                       │ GET /recommendations/{id}
                                             ▼
                        ┌──────────────────────────────────────────┐
                        │  src/api/app.py         FastAPI          │
                        │  request validation · envelope           │
                        └──────────────┬───────────────────────────┘
                                       ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  src/recsys/serve.py     LobbyService                                │
   │                                                                      │
   │   responsible.assess()   ◄── HARD GATES, run FIRST                   │
   │            │                 blocked ⇒ return zero rows, never score │
   │            ▼                                                         │
   │   row builders: continue · because · discover · trending · new       │
   │            │                                                         │
   │            ▼                                                         │
   │   display filter (nameable only) · provider cap · dedup              │
   │            │                                                         │
   │            ▼                                                         │
   │   suppression  ◄── MODERATE+ withholds every engagement row          │
   └──────────────┬───────────────────────────────────────────────────────┘
                  ▼
   ┌──────────────────────────────┐   ┌─────────────────────────────────┐
   │ artifacts/model.npz          │   │ artifacts/interactions.npz      │
   │ item-item similarity, pop,   │   │ train matrix, index maps,       │
   │ cold-item list               │   │ displayable mask                │
   └──────────────▲───────────────┘   └──────────────▲──────────────────┘
                  │                                  │
   ┌──────────────┴───────────────┐   ┌──────────────┴──────────────────┐
   │ src/recsys/train.py          │   │ src/pipeline/build_dataset.py   │
   │ fits once, offline           │   │ CA_Player.csv → matrices +      │
   └──────────────────────────────┘   │ catalogue, temporal split       │
                                      └─────────────────────────────────┘
```

**No model is fitted at request time.** `train.py` runs offline and writes
`model.npz`; the service loads it once (~0.3 s) and a request is a handful of
sparse lookups — measured at **~60 ms** end to end for a full five-row lobby.

---

## 3. Technology stack

FEG's approved stack is binding. Source: the stack diagram supplied with the
challenge brief, which rules out Velocity, PHP, C++, MS SQL and Ignite.

| Layer | FEG stack | This prototype | Production target |
|---|---|---|---|
| Front-end | **Vue.js** | plain HTML/CSS/JS, no framework | Vue 3 lobby components |
| Back-end | **Java · Python · .NET** | Python 3.10 + FastAPI | Python or Java; the model is NumPy/SciPy and portable |
| Integration | **NGINX · Kafka · RabbitMQ** | direct HTTP | Kafka for the interaction stream |
| Data | **PostgreSQL · Redis · Mongo · Elastic** | `.npz` on disk | Redis for player vectors, PostgreSQL for the impression log |

---

## 4. Data flow

### Offline (batch, daily)

1. `CA_Player.csv` — daily per-player stake by game — is read in one pass.
2. Codes are classified (`src/recsys/catalog.py`): named / opaque hash / gpas
   slug / short code / **non-game**. The accounting row
   `NA - Deposit / Withdrawal / Corrections` is dropped from the item space
   entirely; left in, it co-occurs with everything and becomes the most similar
   item to every game on the site.
3. Interactions are aggregated per (player, game) and split temporally —
   train 08-01→24, test 08-25→31. Index maps are built from **training only**,
   so the test window cannot define the item space.
4. Confidence = `log1p(stake)`. Raw stake spans orders of magnitude; one whale
   would otherwise dominate every similarity.
5. `train.py` fits item-item cosine with shrinkage, keeps the top-300
   neighbours per item, and saves the similarity matrix, popularity vector and
   cold-item list.

### Runtime (per request)

1. Responsible-play assessment — **before** any scoring.
2. Row builders score against the loaded artifacts.
3. Display filter: only nameable games reach a tile.
4. Diversity: at most 3 games per provider per row; no game appears twice.
5. Suppression: at `MODERATE`+ every engagement row is withheld.

---

## 5. Model

**Two stages.** Item-item collaborative filtering and a day-to-day sequence
model generate ~200 candidates per player; a **trained scikit-learn logistic
regression** re-ranks them. The ranker is the only component fitted with a loss
function — the candidate models are closed-form counting, and `how-it-works.md`
is explicit about that distinction.

The ranker learns over 14 features spanning candidate scores, player-game
affinity (provider, game type, recency) and game properties (popularity,
release age, momentum, jackpot). On the held-out week it reaches 0.0708 NDCG@10
on tail discovery against 0.0655 for the blend it re-ranks and 0.0165 for
popularity. Logistic regression over gradient boosting was chosen before
reading the test set, for exact attribution and because GBM was memorising
(0.920 train accuracy against 0.656 on an 8.1%-positive problem).

**Item-item collaborative filtering**, as the candidate generator, chosen over
matrix factorisation for three reasons in order of weight:

1. **Explainability.** Every score decomposes into "you played X, people who
   play X also play Y". The widgets need that sentence, and under the EU AI Act
   an unexplainable recommender on a gambling platform is a liability. The
   `why` string on each tile is the literal top contributor to the score.
2. **Density fit.** 0.39% with ~3,200 items is where neighbourhood methods do
   well. Matrix factorisation's advantage appears on sparser, larger
   catalogues, and is the obvious next comparison.
3. **No training loop to get wrong.** One sparse product.

**Trained wide, served narrow.** The similarity matrix covers all 3,202 games
including the 2,724 opaque codes carrying 58% of stake — their co-occurrence is
real signal. Only the 479 nameable games can ever be displayed. That filter is
applied at serving time, never at training time.

**Popularity correction α defaults to 0.0, and that is measured, not lazy.**
Positive α damps popular items and makes headline discovery strictly worse;
negative α improves it only by converging on the popularity baseline, with
coverage collapsing from 726 games to 87. Since this model's job is the tail,
0.0 is correct. See `docs/evaluation.md` §2.1.

---

## 6. Responsible play

Two mechanisms, deliberately not the same thing:

**Hard gates** — self-exclusion, national exclusion register, unverified age,
deposit limit reached. These are legal preconditions. They are evaluated in
`responsible.assess()` **before** the player is scored, so a blocked account is
never scored at all — the API returns zero rows, not a filtered list. They are
absent from `config/thresholds.example.yaml` on purpose: no configuration can
relax them.

**Graded suppression** — behavioural indicators accumulate into
NORMAL → MILD → MODERATE → SEVERE. From `MODERATE`, every engagement-driving
row is withheld and only *Continue playing* survives, with the withheld rows
returned in `suppressed_rows` so the decision is auditable.

There is exactly **one** place a row can be suppressed and **one** place hard
gates are evaluated. Both are covered by tests.

---

## 7. External dependencies

NumPy, SciPy, FastAPI, Uvicorn, Pydantic — full list with licences in
`docs/dependencies.md`. The prototype calls no external API, loads no remote
model and sends no data anywhere. The dashboard loads two Google Fonts; that is
the only outbound request and it is cosmetic.

---

## 8. Deployment assumptions

- **Shadow mode first.** Log recommendations against the live lobby without
  rendering them, and compare before switching any traffic.
- **Per-row feature flags.** Each row can ship independently; *Trending* is
  the existing behaviour, so the rollout is genuinely incremental.
- **Stateless service**, horizontally scalable. Artifacts are read-only.
- **Daily retrain** is a batch job whose output is a file; promoting a new
  model is a deploy, not a live retrain.
- **Latency.** ~60 ms per lobby with no I/O on the request path. The binding
  constraint in production would be the player-vector lookup, not scoring.

---

## 9. What is not built

Stated plainly, because a prototype that overclaims is worse than one that
does not.

- **No Vue SDK.** The dashboard is plain HTML; production would be Vue 3.
  `docs/integration.md` specifies the component contract and sizing.
- **No Kafka consumer, no Redis.** The pipeline is offline; the API reads files.
- **No session/sequence model.** Recommendations are per player, not per
  session, so "what to play next *right now*" is not modelled.
- **No live exclusion-register integration.** The gate is implemented and
  tested; the caller supplies the flag.
- **No thumbnails.** 83% of games cannot even be named, let alone illustrated.
  Tiles use a deterministic colour derived from the title.
- **No online experiment.** Every number in `docs/evaluation.md` is offline.
