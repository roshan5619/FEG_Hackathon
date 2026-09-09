# Live demo — runbook

**PSK Personalised Lobby** · Team Q'Makers · presented live, not recorded.

> If FEG later requires a recorded video, this same run of show works unchanged
> — record the screen while following it, and put the link in this file.

---

## Pre-flight — do this before you're in the room

```bash
cd feg-hackathon-2026-QMakers
pip install -r requirements.txt
python -m pytest tests/ -q          # expect: 54 passed
python -m src.cli users             # the 12 logins — leave this terminal open
```

Then a full dry run of the launch command, so the first cold start isn't
happening in front of the judges:

```bash
python -m src.cli demo
```

**Checks before you present:**

- [ ] `54 passed` — if not, do not demo from this machine
- [ ] The browser opens on the **anonymous** lobby: two rows, *Popular* and
      *New games*. If you see six rows, the reset failed — see below.
- [ ] A second tab loaded on <http://127.0.0.1:8000/backend>
- [ ] Terminal font large enough to read from the back of the room
- [ ] Laptop on mains power, sleep and notifications off
- [ ] `python -m src.cli users` output visible — you never type a password

Cold start is ~2.7 s to first page; each lobby is ~27 ms. Nothing is fetched
from the network, so **the demo works with the wifi off** — say that if the
venue connection is bad.

---

## The 12 accounts

Password for all: **`psk2026`**. The login page lists them with one-click fill,
so you never type a credential on camera or on stage.

Three you must know by name:

| Account | What it shows |
|---|---|
| `ana.k` | A heavy player, 177 games — the richest personalisation |
| `davor.z` | **Sign-in refused** — age/ID unverified |
| `lucija.h` | **Signs in, zero rows** — self-excluded |
| `tomislav.j` | MODERATE risk — only *Continue playing* survives |

---

## Run of show (~4 minutes)

**0:00 — Say nothing for a second. Let them look at the signed-out lobby.**

> "This is psk.hr's casino lobby today. Two rows. Every one of 23,673 players
> sees exactly this — whether they've played one game or three hundred. And the
> single most common way a player reaches a game here is typing its name into
> the search box. If you have to search, the lobby didn't surface it."

**0:40 — Sign in as `ana.k`. This is the whole product in one gesture.**

Click the account to fill it, submit. Two rows become six.

> "Same page. Now it knows who's looking at it."

Name the rows as they land: *Continue playing* is her own history,
*Picked for you* and *Discover something new* are the trained ranker,
*Popular* is unchanged — **that's deliberate, and it's the next slide.**

**1:20 — Read a tile out loud.**

> "*Because you play 4 Scarab Coins: Hold and Win.* That is not a generated
> sentence.
> It's the literal top contributor to that score — the feature with the largest
> weight × value in the logistic regression. We can reconstruct the model's
> exact probability from what's on the tile, and there's a test that asserts it."

**1:50 — Sign out, sign in as a different account.**

Personalised rows change completely. *Popular* is identical.

> "That contrast is the argument."

**2:10 — The honest part. Second tab: `/backend`.**

> "On predicting the next game a player tries, our recommender **lost** to
> most-played — NDCG@10 0.049 against 0.211. We tuned hard before accepting it.
> What players try next is overwhelmingly what's already popular.
>
> So we kept the popularity row. But it can only ever reach 32 games out of
> 3,202. Remove the global top-50 and it reverses: **the trained ranker beats
> popularity 4.28× while reaching 732 games against 29 — and 76.5% of all
> discovery lives in that tail.**"

**3:00 — Responsible play. Two gates, and they are deliberately different.**

Sign in as `davor.z` → **refused**, no session at all.

> "Age unverified. Croatian law requires that check *before* play is allowed,
> so there's no session to filter."

Sign in as `lucija.h` → **succeeds**, lobby is empty.

> "Self-excluded. She signs in — she has to, she must be able to reach her
> account and support. But zero recommendations. Not filtered. **Never scored** —
> the gate runs before the model."

Then `tomislav.j`: MODERATE, only *Continue playing* survives, and the withheld
rows are returned in the response so the decision is auditable.

**3:40 — Close.**

> "54 tests, including one that asserts that tail result against the real
> artifacts. And one honest ask: 58% of stake is still on games we cannot name.
> A game catalogue from FEG costs them a database export and multiplies the
> addressable inventory."

---

## If something breaks

| Symptom | Fix |
|---|---|
| **Six rows at the start** — an old session survived | Open <http://127.0.0.1:8000/?fresh=1>. That is what `demo` opens, and it clears the cookie. |
| **Port 8000 in use** | `python -m src.cli demo --port 8010` |
| **Server won't start / artifacts missing** | `python -m src.cli status` says what's absent. Artifacts are committed, so this should not happen on a clean clone. |
| **Browser didn't open** | The terminal prints the URL. Paste it. |
| **Everything is broken** | Screenshots in `demo/screenshots/` cover the whole journey. Talk over those and carry on — do not debug on stage. |

The demo needs no network, no database, no API key. If the venue wifi dies,
nothing changes.

---

## Questions to expect

**"Isn't 0.0708 a tiny NDCG?"**
Yes, in absolute terms, and it should be — predicting which of 3,000 games
someone plays next week is hard, with few positives per player. The comparison
is what matters, and every model faces the identical task.

**"If your recommender lost, why build it?"**
It lost on the head, where popularity is unbeatable — so we kept the popularity
row. It wins 4.28× on the tail, and 76.5% of discovery happens there. We're not
replacing what works; we're adding what it structurally cannot do.

**"How do you know it isn't overfitting?"**
Three-way temporal split. Hyperparameters were chosen on a validation week and
never on the test week. We caught ourselves doing it the wrong way earlier and
fixed it — gradient boosting actually beat logistic regression on a player-split
validation and then *lost* on the temporally separate test, which is exactly the
overfitting you can't see if you only split by user.

**"What's the revenue impact?"**
We refuse to give one. We tested it three ways and it didn't survive: matched on
activity, adopters retain no better and stake *less* the following week. What we
have is €19.6M — 13.7% of all stake — sitting on first-time game plays served
today by a search box. The A/B test that would settle it measures first-time
adoptions replayed within 7 days.

**"Is it GDPR / AI Act compliant?"**
Every tile carries the literal top contributor to its score, so the
explainability obligation is met by construction rather than by a report. No
personal attribute exists in the data — the demo account names are invented
labels on pre-hashed anonymous ids. Details in `docs/compliance-note.md`.

**"Did you use quantum optimisation?"**
No. We looked seriously and the honest answer is that recommender systems are
the canonical *disproven* quantum speedup — the Kerenidis–Prakash algorithm was
dequantised by Ewin Tang in 2018. Claiming it would have been decoration.

**"Why are some games called 'Amusnet slot'?"**
Because we will not invent a name. 58% of stake sits on opaque codes. Our name
bridge recovered 180 of them from behavioural co-occurrence alone — it
independently derived that `gpas_3chken_pop` is *4 Crazy Cluckers*, from a slug
it cannot read. The rest need a catalogue export from FEG.

**"Is this production-ready?"**
The model and the API are. The auth is not, and we say so: hashed passwords and
signed cookies, but no rate limiting, no lockout, no MFA. It exists so the demo
has a real login journey.
