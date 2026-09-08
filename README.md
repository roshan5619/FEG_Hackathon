# PSK Game Recommender

**A personalised casino lobby for psk.hr — popularity owns the head, collaborative filtering owns the tail.**

| | |
|---|---|
| **Team** | Q'Makers |
| **Challenge** | FEG Innovation Challenge 2026 — Croatian brand (PSK) track |
| **Status** | Working prototype: trained model, decisioning API, personalised dashboard, 22 passing tests, full offline evaluation |

---

## 1. Problem statement

psk.hr's casino lobby is **static**. Every player sees the same rows. The
biggest one is *Najigranije* — "most played" — an identical global list for all
27,000 players.

The behavioural evidence says that matters. In the FEG event export, the single
most common way a player reaches a game is **typing its name into search**
(3,580 launches, ahead of every browsable surface). If you have to search, the
lobby did not surface it.

And players are not narrow. In a held-out final week, **74% of interactions are
with games the player has never played before**. They explore constantly — they
just explore badly, through a search box and one global row.

---

## 2. What we built, and the finding that shaped it

A hybrid lobby. Five rows, each justified by a measured result rather than a
guess — including one result that went against us.

> **Collaborative filtering loses to "most played" on next-game prediction, and
> loses badly: NDCG@10 0.056 against 0.305.** We tuned it hard before accepting
> that — swept popularity correction, shrinkage, neighbourhood size, and a
> popularity-blended hybrid across eight weights. Nothing beat plain popularity.
>
> The reason is a real fact about PSK: what players try next is overwhelmingly
> what is already popular. Spearman correlation between training popularity and
> next-week discovery is **0.79**, and one title takes **13%** of all discovery
> plays on its own.

That would be the end of it, except popularity can only ever reach 41 games.
So we asked the question that actually matters for a lobby — *what happens
below the blockbusters?*

> **Remove the global top-50 and it reverses. A trained ranker beats popularity
> 4.28× on NDCG@10 while reaching 732 games against 29 — 25× the catalogue. And
> 76.5% of all discovery plays live in that tail.**

So the product answer is not "replace the popularity row". It is **keep it, and
add what it structurally cannot do**. Full tables and method in
[`docs/evaluation.md`](docs/evaluation.md).

### The rows

| Row | Model | Why it exists |
|---|---|---|
| **Trending now** | `most_played` | Wins the head outright. This is *Najigranije* — we kept it |
| **Continue playing** | `user_top` | NDCG 0.73 on repeat; labelled as the easy task it is. Serves **100%** of players |
| **Preporučeno za tebe** | **trained ranker** (sklearn LogisticRegression) | Explainable: every tile names the game that caused it |
| **Otkrij nešto novo** | trained ranker, top-50 removed | The 4.28× result above |
| **New releases** | cold items | 12.1% of discovery is on games with *zero* history — no CF can ever reach them |

---

## 3. Key features

- **Every tile carries its reason.** "Because you played *4 Scarab Coins: Hold
  and Win*" is the literal top contributor to that score, not a generated
  rationale. Where the source game has no name in the data, the copy says so
  rather than inventing one.
- **Responsible play runs before scoring, not after.** A self-excluded account
  is never scored at all — the API returns zero rows, not a filtered list. At
  `MODERATE` risk every engagement row is withheld and only *Continue playing*
  survives. One chokepoint, covered by tests.
- **Nothing unnameable is ever *recommended*.** 83% of stake sits on opaque
  game codes (`pop_9f571b7a_egtfeg`). They train the model — their
  co-occurrence is real signal — but they can never appear in a recommendation
  row, because a player has no way to know what they are being offered.
  *Continue playing* is the single exception: **54% of players have no
  nameable game in their history at all**, so there they are labelled by what
  we genuinely know — "Amusnet slot", visibly dimmed and marked
  `named: false`. Reminding someone of a game they already play is not the
  same as recommending an unidentifiable one. Guarded by a test.
- **Diversity caps** — at most 3 games per provider in a row, so a single
  studio cannot own the lobby.

---

## 4. Technology stack

| Layer | Used here | Production target (FEG stack) |
|---|---|---|
| Model | Python 3.10+, NumPy, SciPy sparse | same |
| API | FastAPI · Uvicorn | Python or **Java** |
| Dashboard | Hand-written HTML/CSS/JS, no framework | **Vue 3** |
| Pipeline | csv + NumPy, offline | Kafka → Redis feature store |
| Tests | pytest | same |

FEG's approved stack (from the supplied stack diagram) is **Vue.js** front-end,
**Java / Python / .NET** back-end, **NGINX / Kafka / RabbitMQ**,
**PostgreSQL / Redis / Mongo / Elastic**. See
[`docs/architecture.md`](docs/architecture.md).

---

## 5. System requirements

- **Python 3.10+**, pip
- ~200 MB disk (artifacts are 3.4 MB; the rest is the virtualenv)
- No database, no broker, no external service, no API key

Verified on Windows 11 with CPython 3.11.9.

---

## 6. Installation

```bash
git clone <this-repo>
cd feg-hackathon-2026-QMakers

python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

That is the whole setup. **The trained model and catalogue are committed**
(`artifacts/`), so the FEG dataset is *not* required to run the prototype.

---

## 7. Configuration

Everything has a working default; nothing below is required.

```bash
cp .env.example .env          # non-secret defaults; .env is gitignored
```

| Setting | Default | Meaning |
|---|---|---|
| `MTG_PORT` | `8000` | API port |
| `HEAD_N` (`src/recsys/train.py`) | `50` | Games treated as "head"; excluded from the Discover row |
| `MAX_PER_PROVIDER` (`src/recsys/serve.py`) | `3` | Diversity cap within a row |
| `DEFAULT_ROW_SIZE` | `8` | Tiles per row |

`config/thresholds.example.yaml` holds the responsible-play thresholds. **Hard
gates are deliberately absent from it** — self-exclusion, exclusion register,
age verification and deposit limits are legal preconditions, not tunables, and
no configuration can relax them.

**No secret is required to run anything here.**

---

## 8. How to run

```bash
uvicorn src.api.app:app --reload --port 8000
```

| URL | What |
|---|---|
| <http://127.0.0.1:8000/> | **The personalised lobby** — switch player, toggle risk flags, watch rows change |
| <http://127.0.0.1:8000/docs> | Interactive API docs |
| <http://127.0.0.1:8000/health> | Model provenance, dataset size, catalogue counts |
| <http://127.0.0.1:8000/players> | Sample player ids with enough named history to demo |
| <http://127.0.0.1:8000/recommendations/{id}> | Widget rows for one player |
| <http://127.0.0.1:8000/evaluation> | The measured results behind the design |

### Use it directly

```python
from src.recsys.serve import LobbyService

svc = LobbyService()                      # loads artifacts, ~0.3s
out = svc.lobby(svc.players[1])           # ~60 ms

for row in out["rows"]:
    print(row["title"], "->", [t["title"] for t in row["tiles"][:3]])

svc.lobby(svc.players[1], player={"self_excluded": True})["rows"]   # []
```

---

## 9. How to test and validate

```bash
python -m pytest tests/ -q          # expect: 22 passed
```

The suite holds the claims in place rather than describing them:

| Test | Asserts |
|---|---|
| `test_self_excluded_account_is_blocked_before_scoring` | Hard gate precedes scoring |
| `test_moderate_risk_suppresses_engagement_rows` | Only *Continue playing* survives at MODERATE |
| `test_accounting_row_is_not_a_game` | The deposit/withdrawal row cannot enter the item space |
| `test_slug_is_never_given_a_name` | `gpas_3chken_pop` is never guessed at |
| `test_discovery_never_scores_an_already_played_game` | No leakage between the tasks |
| `test_metrics_match_hand_computation` | NDCG/precision/recall verified by hand on a fixture |
| `test_popularity_correction_actually_has_an_effect` | Regression test for a silent no-op bug |
| **`test_item_item_beats_popularity_on_tail_discovery`** | **The headline claim, against the real artifacts** |

### Rebuilding from source data (optional)

Requires `CA_Player.csv`, which is **not** in this repository:

```bash
python -m src.pipeline.build_dataset --source path/to/CA_Player.csv
python -m src.recsys.train
python -m src.recsys.evaluate
```

Reconciles to 741,679 rows · 23,673 train players · 3,202 games · 296,205
training interactions.

---

## 10. Demo flow

1. **`/`** — the lobby. Point out that *Trending* is the row PSK ships today,
   and that we kept it because it wins.
2. **Switch player** — *Picked for you* and *Discover* change completely;
   *Trending* does not. That contrast is the product.
3. **Read a tile's reason** — "Because you played X", naming a real game.
4. **Toggle "Self-excluded"** — the lobby goes to zero rows. Not filtered:
   never scored.
5. **Set deposits to 3 + "Stake above own history"** — state goes MODERATE and
   every engagement row is withheld; only *Continue playing* remains.
6. **`/evaluation`** — the numbers, including the one where we lose.

---

## 11. Known limitations, assumptions and future work

### Data
- **One month** (Aug 2026). No seasonality; the test window is 7 days.
- **83% of stake is on unnameable games**, so the *recommendable* catalogue is
  351 of 3,202 and **54% of players have no nameable game in their history**. A
  game catalogue from FEG would remove this entirely — **the single
  highest-value thing we could be given.**
- **12.1% of discovery is unreachable by any CF model** (games with zero
  history). Recall ceiling 87.9%.

### Method
- **Offline metrics are not engagement.** Everything here measures next-week
  game selection. "Longer sessions" is a different quantity and only an online
  A/B test can measure it. Catalogue coverage is our proxy, and remains a proxy.
- **Exposure bias.** Players choose from what PSK already shows them — a
  popularity row — so popularity partly predicts its own success. This biases
  the headline comparison *in favour of* the baseline we lose to.
- **No confidence intervals** on the differences.

### Not built
- No Vue SDK — the dashboard is plain HTML.
- No Kafka/Redis — the pipeline is offline, the API loads a file.
- No live exclusion-register integration: the gate is implemented and tested,
  the caller supplies the flag.
- No session/sequence model — recommendations are per player, not per session.

### Next
1. Online A/B against *Najigranije*, measuring session length and breadth, not
   offline NDCG.
2. Ask FEG for the game catalogue; unlock the other 83%.
3. Sequence-aware model for within-session next-game.
4. Bandit exploration for cold items instead of a static "New releases" row.

---

## 12. Documentation

| Document | Contents |
|---|---|
| [`docs/how-it-works.md`](docs/how-it-works.md) | **Start here.** Every formula, the trained ranker, and both leaks we found and fixed |
| [`docs/integration.md`](docs/integration.md) | How FEG ships this: the contract, where each row goes, sizing, rollout, what FEG must supply |
| [`docs/evaluation.md`](docs/evaluation.md) | **Protocol, full results, the negative finding, and the limits** |
| [`docs/architecture.md`](docs/architecture.md) | Components, data flow, FEG stack alignment, what is not built |
| [`docs/impact-case.md`](docs/impact-case.md) | Value model built on measured coverage, not benchmarks |
| [`docs/compliance-note.md`](docs/compliance-note.md) | EU AI Act, Croatian binding rules, GDPR — mapped to code and tests |
| [`docs/dependencies.md`](docs/dependencies.md) | Third-party components, licences, data provenance |
| [`docs/ai-use-disclosure.md`](docs/ai-use-disclosure.md) | AI assistance disclosure — **has items the team must confirm** |

---

## 13. Data handling

**No personal data is in this repository.** The FEG source files (`CA_Player.csv`,
`SB_Player.csv`, `EPS_Offers.csv`, the event logs) are gitignored and are not
required to run anything. Player identifiers arrive **pre-hashed** in the export
and are used only as opaque keys.

Committed: `artifacts/catalog.json` (game codes and names), `interactions.npz`
(the sparse matrix, keyed by hashed ids), `model.npz`, and the evaluation
outputs. 3.4 MB total.

---

## 14. Team

| | |
|---|---|
| **Team name** | Q'Makers |
| **Team lead** | `[TEAM TO ADD]` |
| **Members** | `[TEAM TO ADD]` |
| **Contact** | `[TEAM TO ADD]` |

> ⚠️ Fill this in, plus the `[TEAM TO CONFIRM]` items in
> [`docs/ai-use-disclosure.md`](docs/ai-use-disclosure.md) and the video link in
> [`demo/demo-video-link.md`](demo/demo-video-link.md), before submitting.
