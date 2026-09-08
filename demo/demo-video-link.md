# Demo video

> ⚠️ **ACTION REQUIRED BEFORE SUBMISSION** — add the link below.

| | |
|---|---|
| **Video URL** | `[TEAM TO ADD]` |
| **Access** | `[TEAM TO ADD — must be viewable by T-Hub / FEG reviewers]` |
| **Duration** | `[TEAM TO ADD]` |

Large media is gitignored (`*.mp4`), so the video is linked rather than
committed. Host it where reviewers can reach it without an account request.

---

## Setup

```bash
pip install -r requirements.txt
uvicorn src.api.app:app --port 8000
```

Open <http://127.0.0.1:8000/>. Have a second tab on
<http://127.0.0.1:8000/evaluation>.

---

## Run of show (~4 minutes)

**0:00 — The problem.** psk.hr's lobby is static. Every one of 26,904 players
sees the same *Najigranije* row. And the most common way a player reaches a
game today is **typing its name into search** — if you have to search, the
lobby didn't surface it.

**0:30 — The lobby.** Show the five rows. Name what each one is: *Trending* is
popularity, *Picked for you* and *Discover* are collaborative filtering,
*New releases* is games with no history at all.

**1:00 — Switch player.** *Picked for you* and *Discover* change completely.
*Trending* does not. That contrast is the whole product.

**1:30 — Read a tile.** "Because you played *4 Scarab Coins: Hold and Win*" —
the literal top contributor to that score, not a generated rationale.

**2:00 — The honest part.** Go to `/evaluation`. Say it plainly:

> On next-game prediction, collaborative filtering **lost** to most-played —
> NDCG@10 0.056 against 0.305. What players try next is overwhelmingly what's
> already popular.
>
> So we kept the popularity row. But it can only ever reach 29 games. Remove
> the global top-50 and it reverses: **our trained ranker beats popularity
> 4.28× while reaching 732 games against 29 — and 76.5% of all discovery lives
> in that tail.**

**3:00 — Responsible play.** Toggle **Self-excluded**: the lobby goes to zero
rows. Not filtered — never scored; the gate runs before the model. Then set
deposits to 3 and **Stake above own history**: state goes MODERATE and every
engagement row is withheld, leaving only *Continue playing*.

**3:40 — Close.** 22 tests, including one that asserts the tail result against
the real artifacts. Then the honest ask: **83% of stake is on games we cannot
name.** A game catalogue from FEG multiplies the addressable inventory ~9× and
costs them a database export.

---

## Screenshots — `demo/screenshots/`

1. The full lobby, five rows
2. Two players side by side (personalised rows differ, Trending identical)
3. A tile close-up showing its "why"
4. Self-excluded → zero rows
5. MODERATE → only *Continue playing*
6. `/evaluation` showing both the loss and the tail win
7. Terminal: 22 passed
