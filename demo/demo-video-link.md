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
python -m src.cli users     # print the 12 demo logins, keep this terminal visible
python -m src.cli demo      # serves on :8000 and opens the browser
```

Open <http://127.0.0.1:8000/>. Have a second tab ready on
<http://127.0.0.1:8000/backend>.

Every demo account uses the password `psk2026`, and the login page lists them
with one-click fill — you never have to type a credential on camera.

---

## Run of show (~4 minutes)

**0:00 — The problem, on screen, before you say anything.** You are signed out,
looking at the anonymous lobby. Two rows: *Popularno* and *Nove igre*.

> "This is psk.hr's lobby today. Two rows, and every one of 23,673 players sees
> exactly the same thing — whether they've played one game or three hundred.
> The most common way a player reaches a game here is typing its name into
> search. If you have to search, the lobby didn't surface it."

**0:40 — Sign in. This is the whole product in one gesture.** Click a demo
account to fill it, submit. The same page rebuilds into six rows.

> "Same page. Now it knows who's looking at it."

Name what each row is as it appears: *Nastavi igrati* is their own history,
*Preporučeno za tebe* and *Otkrij nešto novo* are the trained ranker,
*Popularno* is unchanged — that's deliberate, and slide 5 explains why.

**1:20 — Read a tile out loud.** "Jer igraš *4 Scarab Coins: Hold and Win*" —
the literal top contributor to that score, not a generated rationale.

**1:40 — Sign out, sign in as a different account.** The personalised rows are
completely different. *Popularno* is identical. That contrast is the argument.

**2:10 — The honest part.** Go to `/backend`. Say it plainly:

> "On next-game prediction, our recommender **lost** to most-played — NDCG@10
> 0.056 against 0.305. What players try next is overwhelmingly what's already
> popular. So we kept the popularity row.
>
> But it can only ever reach 29 games. Remove the global top-50 and it
> reverses: **our trained ranker beats popularity 4.28× while reaching 732
> games against 29 — and 76.5% of all discovery lives in that tail.**"

**3:00 — Responsible play, and it is two different gates.** Sign in as
`davor.z` — **refused**, no session at all, because the age check must precede
play. Then sign in as `lucija.h` — **succeeds**, because a self-excluded person
must still reach their account and support, but the lobby returns **zero rows**.

> "Not filtered. Never scored — the gate runs before the model."

Then `tomislav.j`: state is MODERATE, every engagement row is withheld, only
*Nastavi igrati* survives.

**3:40 — Close.** 53 tests, including one that asserts the tail result against
the real artifacts, and one proving `/explain` reconstructs the model's
probability exactly. Then the ask:

> "58% of stake is still on games we cannot name. A game catalogue from FEG
> costs them a database export and multiplies the addressable inventory."

---

## Screenshots — `demo/screenshots/`

1. **Signed out** — the anonymous lobby, two rows (the "before")
2. **The login page** — demo accounts listed, prototype banner visible
3. **Signed in** — six rows (the "after"), same page
4. Two different accounts side by side: personalised rows differ, *Popularno* identical
5. A tile close-up showing its "why"
6. `davor.z` — sign-in refused at the age gate
7. `lucija.h` — signed in, zero rows, support surfaces shown
8. `tomislav.j` — MODERATE, only *Nastavi igrati*
9. `/backend` showing both the loss and the tail win
10. Terminal: `53 passed`
