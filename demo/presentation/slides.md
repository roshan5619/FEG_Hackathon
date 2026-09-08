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
Built on 23,673 players · 3,202 games · 741,679 rows · a trained ranker

---

## 2 — The problem: 23,673 players. One lobby.

psk.hr's casino lobby is static. The biggest row is **Najigranije** — "most
played" — and it is identical for every single player, whether they have played
one game or three hundred.

| | |
|---|---|
| **Search** | The top route to a game — 3,580 launches, ahead of every browsable surface. If you have to type the name, the lobby didn't surface it. |
| **29–32** | Games the top row can ever reach, of 3,202. ~1% of the library, for everyone. |
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

## 4 — What we built: sign in, and the lobby becomes yours

**This is the demo, and it is one gesture.**

Signed out, you see exactly what a psk.hr visitor sees today: **two rows**,
*Popularno* and *Nove igre*, identical for all 23,673 players. Sign in and the
same page rebuilds into **six rows** from that player's own history.

| Row | What it is |
|---|---|
| **Nastavi igrati** | Their own games, recency-weighted |
| **Preporučeno za tebe** | "Jer igraš *4 Scarab Coins: Hold and Win*" — the trained ranker |
| **Otkrij nešto novo** | The tail: same model, blockbusters removed |
| **Jackpoti** | 136 jackpot-eligible titles, filtered to their taste |
| **Popularno** | The row PSK ships today, kept unchanged |
| **Nove igre** | 275 genuinely new titles |

Twelve demo accounts are generated from real player histories in the model, so
the change is never a mock-up — it is the ranker running on that player's data.

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

## 6 — The result: but popularity only knows 29 games

Remove the global top-50 — the blockbusters everyone already sees — and the
result reverses completely.

| Model | NDCG@10 |
|---|---|
| **Trained ranker** | **0.0708** |
| Blend (sequence + CF) | 0.0655 |
| Sequence | 0.0649 |
| Item-item CF | 0.0490 |
| most_played | 0.0165 |

| | |
|---|---|
| **4.28×** | Accuracy on the tail vs the popularity baseline |
| **25×** | Catalogue reached — **732 games** instead of 29 |
| **76.5%** | Of all discovery lives in that tail |

The ranker is a scikit-learn logistic regression trained on ~200,000 labelled
rows, with hyperparameters chosen on a separate validation week — never on the
test week. Ordering holds at top-20 and top-100 boundaries, so it is not an
artefact of where the line is drawn.

---

## 7 — The design that follows: popularity owns the head, we own the tail

| Row | Source | Why |
|---|---|---|
| Popularno | popularity | The incumbent row (*Najigranije*), kept unchanged because it wins its job |
| Nastavi igrati | recency-weighted history | Their own games, most recent first. Serves **100%** of players |
| Preporučeno za tebe | trained ranker | "Because you played X" — the literal top contributor to the score |
| Otkrij nešto novo | trained ranker | Same model, blockbusters removed. Where the 4.28× lives |
| Jackpoti | ranker + eligibility | **136** jackpot titles, ordered by the same model |
| Nove igre | real release age | **275** titles first released in the last 3 months, from 12 months of history |

The recommender is **additive**. Nothing that already worked was removed, so
the downside is bounded at screen space — and each row ships behind its own
feature flag.

---

## 8 — Responsible by construction: the gate runs *before* the model

**Two gates, and they are deliberately different — because the law makes them
different.**

| Gate | Where it fires | Why |
|---|---|---|
| **Age / ID unverified** | **At sign-in** — refused, no session issued | The check must precede play |
| **Self-excluded** | **After sign-in** — account opens, lobby returns **zero rows** | Self-exclusion blocks *inducements*, not account access. The person must still reach their account and support. |

Getting either backwards would be a real compliance failure, so both directions
are asserted in tests rather than described in prose. Croatia's Act on Measures
for Socially Responsible Organisation of Games of Chance requires a real check
pattern, not a UI checkbox.

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
- **One chokepoint, covered by tests** — 53 of them, including one asserting the
  tail result against real artifacts, and one proving `/explain` reconstructs
  the model's probability exactly.

---

## 8b — The business case, and what we could not prove

**€19.6M — 13.7% of all stake — sits on games a player was trying for the first
time.** 138,041 first-time adoptions a fortnight, median €16.16 each. That flow
is served today by a search box and one unchanging row.

**Tail games are not the cheap end:** median stake €17.00 against €10.50 for a
top-50 game.

**We tested whether broader discovery drives value. It did not survive.**

- Breadth correlates hugely with value (1–2 games €16 → 26+ games €5,446) but
  is confounded by activity level.
- Matched on week-3 activity, adopters retain no better — 1 day: 56.8% vs
  57.6%; 4–7 days: 94.2% vs 96.5%.
- Adopters stake **less** the next week at every matched band (€200–1,000:
  €155 vs €246).

**So we make no revenue claim.** The reframe we do make: exploration correlates
with lower value *because exploration currently fails*. Players hunt and don't
find. The product's job is not more exploration — it is making the exploration
they already do succeed.

**The experiment that settles it:** A/B on the lobby, primary metric = first-time
adoptions **replayed within 7 days**. That separates "found something good" from
"tried and bounced" — exactly what the failed tests could not.

---

## 9 — The honest constraint: 58% of stake is on games we cannot name

The export identifies most games by opaque codes like `pop_9f571b7a_egtfeg`.
They train the model — their co-occurrence is real signal — but they can never
be recommended, because a player has no way to know what they're being offered.

| | |
|---|---|
| **58.4%** | Of all stake, still on games with no title we can show |
| **180** | Codes our name bridge recovered from behavioural co-occurrence alone — **37% of all stake**, taking the recommendable catalogue from 351 to **479** games |
| **54%** | Players with no named game in their history. Handled honestly: "Amusnet slot", visibly dimmed, marked `named: false` |

The bridge validates itself: it independently produced `gpas_3chken_pop` →
*"4 Crazy Cluckers"* (111 votes) and `gpas_wpisto_pop` → *"Mega Fire Blaze:
Wild Pistolero"* (48). Both slugs decode to their resolved titles, which the
algorithm has no way to read.

**The ask:** a game catalogue — code → title, category, thumbnail. It is the
single highest-value thing we could be given, it costs FEG a database export,
and it is the only limit here we cannot engineer around.

---

## 10 — Where it stands

**Shipped**
- Pipeline → model → API → dashboard, end to end
- A real login journey: anonymous landing → personalised lobby, 12 demo accounts
- **~25 ms** per personalised lobby, no model fit at request time
- **53 tests**, green on a clean clone
- Eight documents including a full evaluation — **with the negative result in it**

**Not built, and said so**
- No Vue SDK yet — the dashboard is plain HTML
- No Kafka/Redis — the pipeline is offline
- No session-level sequence model
- Prototype auth only — hashed passwords and signed cookies, but no rate
  limiting, lockout or MFA
- **No online experiment.** Every number is offline. "Longer sessions" is an
  assumption an A/B test must check.

Twelve months of data. Offline metrics measure next-week game selection, not
engagement — catalogue coverage is our proxy, and it remains a proxy.

---

## 11 — Close

**The lobby should know who is looking at it.**

Today it doesn't. One row, 23,673 players, 32 games.

We measured what personalisation can and can't do here — kept the row that
already worked, and added the 732 games it could never reach.

Q'Makers · FEG Innovation Challenge 2026 · `feg-hackathon-2026-QMakers`

---

## Delivery notes

**The strongest slide is 5, not 6.** Leading with a result that went against us
is what makes 6 credible. Do not soften it — say "our recommender lost" in
those words, then explain why we kept the popularity row anyway.

**Slide 4 is the one to demo live, not describe.** Sign in on screen. The page
going from two rows to six is the entire product in one gesture, and it lands
harder than any slide about it.

**If you have 90 seconds:** slide 2 (one lobby, 32 games) → slide 4 (sign in,
live) → slide 5 (we lost) → slide 6 (4.28×, 732 games vs 29) → slide 9 (the
catalogue ask).

**Numbers to never round up:** 74%, 0.305, 0.056, 0.0708, 4.28×, 25×, 76.5%,
54%, 58.4%, 53 tests.

**Expect this question:** *"Isn't 0.046 a tiny NDCG?"* — Yes, in absolute
terms, and it should be: predicting which of 3,000 games someone tries next
week is a hard task with few positives per player. The comparison is what
matters, and it is against the same task for every model.
