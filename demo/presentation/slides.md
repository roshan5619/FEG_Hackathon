# Pitch deck — slide content

**PSK Personalised Lobby** · Team Q'Makers · FEG Innovation Challenge 2026

A ready-to-present HTML version of this deck exists; this file is the source
content so it can be rebuilt as `.pptx` if FEG expects that format. Every figure
here is computed by `src/pipeline/build_dataset.py` and
`src/recsys/evaluate.py` — see [`docs/evaluation.md`](../../docs/evaluation.md).

> **The old `MindTheGap_Pitch_Deck.pptx` is obsolete.** It describes an
> abandoned sportsbook session-intelligence concept and must not be submitted.

---

## 1 — Title

**PSK Personalised Lobby**

A game recommendation system that rebuilds the casino lobby around what each
player actually plays — their history, their favourites, their next game.

Team Q'Makers · FEG Innovation Challenge 2026 · PSK
Built on 26,904 players · 3,203 games · 741,679 rows

---

## 2 — The problem: 26,904 players. One lobby.

psk.hr's casino lobby is static. The biggest row is **Najigranije** — "most
played" — and it is identical for every single player, whether they have played
one game or three hundred.

| | |
|---|---|
| **Search** | The top route to a game — 3,580 launches, ahead of every browsable surface. If you have to type the name, the lobby didn't surface it. |
| **41** | Games the top row can ever reach, of 3,203. 1.3% of the library, for everyone. |
| **0** | Personalised rows today. Widgets exist — top_10, providers, categories — but none adapt to the player. |

---

## 3 — The insight: players already explore, they just explore badly

# 74%

of plays in a held-out week were games the player had **never played before**.

This is not an audience that needs persuading to try something new. They try
new games constantly — through a search box and one global row. The demand for
discovery is already there; the lobby simply doesn't serve it.

**And they have clear favourites.** A median **78%** of a player's launches sit
in their top-3 games, and **65%** come from a single provider. So the lobby has
two jobs, not one: get them back to what they love, and show them what's next.
We built and measured both separately.

---

## 4 — What we built: five rows, each earns its place

Visual: mock lobby with three rows of tiles.

- **Continue playing** — their own history, most-played first
- **Picked for you** — "Because you played *4 Scarab Coins: Hold and Win*"
- **Trending now** — the row PSK ships today, kept

Plus **Discover something new** (the tail) and **New releases** (games with no
history at all).

---

## 5 — The finding we didn't want: our recommender *lost*

On predicting the next game a player tries, collaborative filtering was beaten
outright by the global popularity row PSK already ships.

| Model | NDCG@10 |
|---|---|
| **most_played** | **0.305** |
| provider_popular | 0.174 |
| item-item CF | 0.056 |

Discovery task, 9,102 players. We tuned hard before accepting it — popularity
correction, shrinkage, neighbourhood size, and a popularity-blended hybrid
across eight weights. Nothing beat plain popularity.

**Why — and it's a real fact about PSK:** what players try next is
overwhelmingly what is *already popular*. Correlation between a game's
popularity and its next-week discovery count is **0.79**. One title —
*Goal Goal Goal: Cash Collect* — takes **13%** of all discovery plays on its
own.

**So we kept the popularity row.** Replacing it would have made the lobby worse.

---

## 6 — The result: but popularity only knows 37 games

Remove the global top-50 — the blockbusters everyone already sees — and the
result reverses completely.

| Model | NDCG@10 |
|---|---|
| **item-item CF** | **0.0462** |
| provider_popular | 0.0359 |
| most_played | 0.0205 |

| | |
|---|---|
| **2.25×** | Accuracy on the tail vs the popularity baseline |
| **18×** | Catalogue reached — **680 games** instead of 37 |
| **76.5%** | Of all discovery lives in that tail |

Holds at top-20 and top-100 boundaries too (1.45× and 2.15×). Not an artefact
of where the line is drawn.

---

## 7 — The design that follows: popularity owns the head, we own the tail

| Row | Source | Why |
|---|---|---|
| Trending now | popularity | The incumbent row, kept unchanged because it wins its job |
| Continue playing | history | Their own games, most-played first. Serves **100%** of players |
| Picked for you | item-item CF | "Because you played X" — the literal top contributor to the score |
| Discover something new | item-item CF | The same model with blockbusters removed. Where the 2.25× lives |
| New releases | cold start | Games with zero history — **12.1%** of discovery, unreachable by any recommender |

The recommender is **additive**. Nothing that already worked was removed, so
the downside is bounded at screen space — and each row ships behind its own
feature flag.

---

## 8 — Responsible by construction: the gate runs *before* the model

**Hard gates — a self-excluded account is never scored.** Self-exclusion, the
national exclusion register, unverified age and a reached deposit limit are
checked **before** any recommendation is generated. The API returns **zero
rows** — not a filtered list. Croatia's Act on Socially Responsible
Organisation of Games of Chance requires a real check pattern, not a UI
checkbox.

**Graded inversion — the same signals, opposite objective.** As harm indicators
accumulate, the lobby's target flips from surfacing more to surfacing less.
From `MODERATE`, every engagement row is withheld and only *Continue playing*
survives. Withheld rows are returned in the response so the decision is
auditable.

- **Explainable by construction** — every tile carries the literal top
  contributor to its score, not a generated rationale. EU AI Act 2024/1689.
- **No stake suggestion exists in the codebase.** The system recommends games,
  never amounts. Stake appears only as a training weight.
- **No countdowns, no scarcity, no "others are playing", no outcome or
  near-miss framing.**
- **One chokepoint, covered by tests** — 23 of them, including one that asserts
  the tail result against the real artifacts.

---

## 9 — The honest constraint: 83% of stake is on games we cannot name

The export identifies most games by opaque codes like `pop_9f571b7a_egtfeg`.
They train the model — their co-occurrence is real signal — but they can never
be recommended, because a player has no way to know what they're being offered.

| | |
|---|---|
| **351** | Recommendable catalogue, of 3,202 games |
| **54%** | Players with no named game in their history. Handled honestly: "Amusnet slot", visibly dimmed, marked `named: false` |
| **~9×** | Unlock if FEG shares a game catalogue |

**The ask:** a game catalogue — code → title, category, thumbnail. It is the
single highest-value thing we could be given, it costs FEG a database export,
and it is the only limit here we cannot engineer around.

---

## 10 — Where it stands

**Shipped**
- Pipeline → model → API → dashboard, end to end
- **~60 ms** per personalised lobby, no model fit at request time
- **23 tests**, green on a clean clone
- Six documents including a full evaluation — **with the negative result in it**

**Not built, and said so**
- No Vue SDK yet — the dashboard is plain HTML
- No Kafka/Redis — the pipeline is offline
- No session-level sequence model
- **No online experiment.** Every number is offline. "Longer sessions" is an
  assumption an A/B test must check.

One month of data (August 2026). Offline metrics measure next-week game
selection, not engagement — catalogue coverage is our proxy, and it remains a
proxy.

---

## 11 — Close

**The lobby should know who is looking at it.**

Today it doesn't. One row, 26,904 players, 41 games.

We measured what personalisation can and can't do here — kept the row that
already worked, and added the 680 games it could never reach.

Q'Makers · FEG Innovation Challenge 2026 · `feg-hackathon-2026-QMakers`

---

## Delivery notes

**The strongest slide is 5, not 6.** Leading with a result that went against us
is what makes 6 credible. Do not soften it — say "our recommender lost" in
those words, then explain why we kept the popularity row anyway.

**If you have 90 seconds:** slide 2 (one lobby, 41 games) → slide 5 (we lost) →
slide 6 (2.25×, 680 games vs 37) → slide 9 (the catalogue ask).

**Numbers to never round up:** 74%, 78%, 0.305, 0.056, 2.25×, 18×, 76.5%, 54%,
83%, 23 tests.

**Expect this question:** *"Isn't 0.046 a tiny NDCG?"* — Yes, in absolute
terms, and it should be: predicting which of 3,000 games someone tries next
week is a hard task with few positives per player. The comparison is what
matters, and it is against the same task for every model.
