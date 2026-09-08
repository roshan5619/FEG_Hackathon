# Integration guide

**PSK Game Recommender** · how FEG ships this

The design constraint throughout: **additive, not a replacement.** Nothing that
works today is removed. *Popularno* is the row psk.hr already ships and it stays
byte-identical, because it measurably wins the head (`evaluation.md` §2.1). The
new rows go beside it, each behind its own flag, and the worst case is screen
space rather than lost revenue.

---

## 1. What FEG actually has to build

Three pieces. Only the first is on the critical path.

| # | Piece | Effort | Owner |
|---|---|---|---|
| 1 | **Vue 3 row component** — renders a row of tiles from a JSON contract | 3–4 days | front-end |
| 2 | **Daily batch job** — runs the pipeline, drops new artifacts | 1 day | data |
| 3 | **Service deployment** — a stateless Python (or Java) service reading those artifacts | 2–3 days | platform |

Everything else in this repository is done.

---

## 2. The contract — one endpoint, one shape

```http
GET /recommendations/{player_id}
```

```jsonc
{
  "player_id": "…",
  "known_player": true,
  "responsible_play": { "state": "NORMAL", "hard_gate": false,
                        "conversion_nudges_suppressed": false },
  "rows": [
    {
      "key": "for_you",
      "title": "Preporučeno za tebe",
      "subtitle": "Na temelju onoga što si igrao",
      "source": "sequence+cf",
      "personalised": true,
      "tiles": [
        { "code": "pop_9f571b7a_egtfeg",
          "title": "40 Burning Hot",
          "provider": "Amusnet",
          "badges": ["NOVO", "JACKPOT"],
          "why": "Jer igraš 4 Scarab Coins: Hold and Win",
          "named": true, "score": 0.8373 }
      ]
    }
  ],
  "suppressed_rows": []
}
```

**Three rules that make the integration safe:**

1. **Render the rows you recognise, ignore the rest.** `key` is stable. The
   service can ship a new row type before any client supports it, and nothing
   breaks.
2. **`rows: []` means show nothing personalised.** Not an error, not a retry —
   a blocked or at-risk account. Fall back to the existing static lobby.
3. **`named: false` means the title is a placeholder** (`"Amusnet slot"`).
   Render it dimmed and never in a recommendation row. The service already
   enforces the second half; the flag lets the client style it.

`GET /explain/{player_id}/{code}` returns the per-feature attribution behind any
tile — for internal tooling, audit, and the regulator conversation.

---

## 3. Where each row goes on the live lobby

Mapped to surfaces that already exist on casino.psk.hr:

| New row | Replaces / sits with | Flag |
|---|---|---|
| **Nastavi igrati** | new — top of lobby | `continue_playing` |
| **Preporučeno za tebe** | `category_game_row` slot | `picked_for_you` |
| **Otkrij nešto novo** | `top_10` slot | `discover` |
| **Jackpoti** | existing *Jackpoti* category | `jackpot_personalised` |
| **Popularno** | **unchanged** — this is *Najigranije* | `trending` (on) |
| **Nove igre** | existing *Nove Igre* category | `new_releases` |

Ship order we would recommend: `continue_playing` first (safest, highest
recognition), then `picked_for_you`, then `discover`.

---

## 4. Rollout

**Shadow mode first.** Score every session, log every decision, render nothing.
The A/B comparison starts before a single player sees a change, and the model
can be validated against live traffic at zero product risk.

```
MTG_SHADOW_MODE=true
MTG_ROLLOUT_FRACTION=0.0
```

Then raise `MTG_ROLLOUT_FRACTION` per row. Each row is independently
switchable; the responsible-play inversion is **not** behind a flag that can be
turned off.

---

## 5. On FEG's stack

From the supplied stack diagram — Vue.js front-end, Java/Python/.NET back-end,
NGINX/Kafka/RabbitMQ, PostgreSQL/Redis/Mongo/Elastic.

```
Vue 3 row component
        │  GET /recommendations/{id}
        ▼
NGINX ──► Recommender service  (Python or Java, stateless, horizontally scaled)
              │  reads at startup
              ▼
          artifacts/  ── 18 MB, from object storage or the image
              ▲
              │  daily
          Batch job ──► reads the same warehouse tables CA_Player is exported
                        from; no new instrumentation required
```

**Redis** holds player vectors once the batch cadence moves below daily.
**Kafka** is only needed for near-real-time updates — the daily batch is
sufficient to start, which is why neither is on the critical path.

### Sizing

| | |
|---|---|
| Latency | **~25 ms** per lobby, no I/O on the request path |
| Memory | ~200 MB resident per instance |
| Compute | training is seconds on one core, daily. **No GPU.** |
| Storage | 18 MB of artifacts per model version |
| Scaling | stateless — add instances behind NGINX |

---

## 6. What FEG must supply

| Item | Needed for | Status |
|---|---|---|
| `CA_Player` warehouse table (or its source) | daily batch | exists — this is the export we were given |
| Player responsible-play flags | the hard gates | **required** — self-exclusion, exclusion-register hit, age verification, deposit-limit state |
| **Game catalogue: code → title, category, thumbnail** | showing games | **the one real blocker.** 58% of stake is on games we cannot name; only 479 of 3,202 are recommendable without it |
| Impression/click log | A/B measurement | needed before the experiment, not before shadow mode |

The catalogue is a database export and it multiplies the addressable inventory
roughly ninefold. It is the highest-return thing anyone could hand this project.

---

## 7. Verifying the integration

```bash
python -m src.cli status            # what is built, and what the ranker learned
python -m src.cli explain <player>  # a full lobby with the model's reasoning
python -m src.cli demo              # server + browser
python -m pytest tests/ -q          # 53 tests
```

The contract tests that matter for an integrator:

- `test_self_excluded_account_is_blocked_before_scoring` — `rows: []`, and the
  account is never scored rather than filtered afterwards
- `test_moderate_risk_suppresses_engagement_rows` — only *Nastavi igrati*
  survives, and `suppressed_rows` records what was withheld
- `test_unnamed_games_appear_only_in_continue_playing` — no unnameable game can
  reach a recommendation row
- `test_explanation_is_exact_for_logistic_regression` — the attribution
  reconstructs the model's probability, so `/explain` can be trusted in an audit
