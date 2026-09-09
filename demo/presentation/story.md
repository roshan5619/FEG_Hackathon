# The story

**How to tell it.** The deck supports you; this is what you actually say.

---

## The one sentence

> **The lobby should know who is looking at it.**

If the jury remembers one line, that is the line. Everything else is evidence
for it.

## The through-line — say only what you measured

Every beat of this story is the same character trait shown a different way:

| Beat | What it shows |
|---|---|
| We kept the popularity row | We tested our own idea and it lost, so we didn't ship it |
| We refuse a revenue number | We ran three tests and reported the negative result |
| The name bridge validates itself | We checked our own inference against something it couldn't see |
| We found our own data leak | We audited ourselves and said so |

A hackathon jury has spent all day hearing teams claim things. **The team that
says "we tested this and it didn't work" is the one they believe about
everything else.** Your credibility is the product here — spend it deliberately.

---

## Act 1 — The situation *(slide 2, ~60s)*

Open on the signed-out lobby. Let them look at it for a beat before you speak.

> "This is psk.hr's casino lobby. Two rows. Every one of 23,673 players sees
> exactly this — someone who has played one game, and someone who has played
> three hundred, get the same screen.
>
> And the most common way a player reaches a game here is typing its name into
> the search box. Think about what that means. **If you have to search, the
> lobby didn't do its job.**
>
> Here's the part that surprised us: 74% of plays in a held-out week were games
> the player had never played before. These people are *already* exploring.
> They explore constantly. They just explore through a search box and one row
> that never changes."

**The point to land:** the demand already exists. Nobody needs persuading. The
shelf is the problem.

---

## Act 2 — The product *(slide 3 + LIVE DEMO, ~2 min)*

Do not describe this. Do it.

> "So — same page. I'm going to sign in."

Click, submit. Two rows become six.

> "Now it knows who's looking at it."

Then slow down and name what changed:

> "*Nastavi igrati* is her own history. *Preporučeno za tebe* and *Otkrij nešto
> novo* are the trained model. And **Popularno is still there, unchanged** —
> that's deliberate, and in about ninety seconds I'll tell you why, because it's
> the most interesting thing we found."

That forward-reference is doing work. It makes the negative result feel like a
reveal you're building to, rather than a confession.

Then read one tile aloud:

> "*Jer igraš 3 Mystic Lamps Buy Bonus.* That is not a sentence we generated.
> It's the single feature with the largest weight times value in the model's own
> score. We can reconstruct the model's exact probability from what's printed on
> that tile — and there's a test that asserts it."

---

## Act 3 — The twist *(slides 6–7, ~2 min)*

This is the centre of the story. Say the first line flatly, without hedging.

> "We built a recommender, and we tested it against the row PSK already ships.
> **It lost.** NDCG 0.049 against 0.211. Not close.
>
> We didn't accept that quickly — we swept popularity correction, shrinkage,
> neighbourhood size, eight different blend weights. Nothing beat plain
> popularity.
>
> And the reason turns out to be a real fact about PSK: what players try next is
> overwhelmingly what's already popular. The correlation is 0.79. One title takes
> 13% of all discovery plays on its own.
>
> So we kept the popularity row. Replacing it would have made the lobby worse."

Pause. Then turn it:

> "But then we asked the question that actually matters. Not *is popularity
> good* — **what can popularity never do?**
>
> And the answer is: it only ever reaches 29 games out of 3,202. About 1% of the
> library, and it's the same 1% for everybody.
>
> So we took the global top 50 out — the blockbusters everyone already sees —
> and ran it again. It reverses completely. Our trained ranker beats popularity
> **4.28 times over**, while reaching **732 games instead of 29**.
>
> And this is the number that matters: **76.5% of all discovery already happens
> down there.** That's not a niche we invented to win a benchmark. It's where
> most exploration on PSK already is."

**Land it:** "Popularity owns the head. We own the tail. We're not replacing
what works — we're adding what it structurally cannot do."

---

## Act 4 — The discipline *(slides 8–11, ~2 min)*

Two things to convey: this is real engineering, and it is safe.

**On the model (slide 8)** — keep it short unless they're technical:

> "Two stages. Cheap models propose about 200 candidates; a trained logistic
> regression over 14 features re-ranks them. We chose logistic regression on
> purpose — every score decomposes into weight times value, which is exactly
> what makes the tile's reason honest.
>
> One thing I'd point at: 2,723 games in this export have no title at all. We
> recovered 180 of them from behaviour alone — co-occurrence on player and day,
> constrained to matching providers. It independently worked out that
> `gpas_3chken_pop` is *4 Crazy Cluckers*, from a slug it has no way to read.
> That's 37% of all stake we can now name."

**On compliance (slide 10)** — this is a gambling product; do not rush it:

> "Two gates, and they're deliberately different, because the law treats them
> differently.
>
> Age unverified: **sign-in refused.** No session at all. The check has to
> precede play, so there's nothing to filter.
>
> Self-excluded: **she signs in.** She has to — she must be able to reach her
> account and support. Self-exclusion blocks inducements, not account access.
> But her lobby returns zero rows. Not filtered afterwards — **never scored.**
> The gate runs before the model.
>
> Getting either of those backwards would be a real compliance failure, so both
> directions are asserted in tests rather than described in a document."

**On business impact (slide 11)** — lead with the refusal; it's stronger:

> "€19.6M a fortnight — a seventh of all stake — sits on games a player was
> trying for the first time. That flow is served today by a search box.
>
> We wanted to tell you personalisation grows that. So we tested it. Three ways.
> **And it didn't survive.** Matched on how active players already were,
> adopters retain no better and actually stake *less* the following week.
>
> So we're not going to give you a revenue number. What we'll argue instead is
> this: exploration correlates with lower value **because exploration currently
> fails.** Players hunt and don't find. The job isn't to make people try more
> games — it's to make the exploring they're already doing succeed.
>
> And that's testable. A/B on the lobby, and the metric is first-time adoptions
> that get *played again* within seven days. That separates 'found something
> good' from 'tried it and bounced' — which is exactly what our failed tests
> couldn't."

---

## Act 5 — The ask *(slides 12–13, ~45s)*

> "One honest constraint. 58% of stake is still on games we cannot name — and
> we will not invent a title for a game we can't identify.
>
> So the ask is a game catalogue. Code, title, category, thumbnail. It costs FEG
> a database export, and it roughly multiplies our addressable inventory
> ninefold. It's the only limit here we can't engineer around."

Close on the opening line:

> "The lobby should know who is looking at it. Today it doesn't — one row,
> 23,673 players, 32 games. We measured what personalisation can and can't do
> here, kept the row that already worked, and added the 732 games it could never
> reach."

---

## Transitions — the part people fumble

| From → To | Say |
|---|---|
| Problem → Demo | "So we built the version where it does." |
| Demo → The loss | "I said I'd tell you why Popularno is still there." |
| Loss → Tail win | "But then we asked what popularity can *never* do." |
| Tail → How it works | "So how does the thing that wins the tail actually work?" |
| Model → Compliance | "This is a gambling product, so the more important question is what it refuses to do." |
| Compliance → Business | "Which brings us to what it's worth — and what we couldn't prove." |
| Business → Ask | "One thing would change all of this, and it isn't engineering." |

---

## If you have 5 minutes instead of 20

Slide 2 (one lobby) → **live demo** → slide 7 (the 4.28× tail result) →
slide 10 (the two gates) → slide 12 (the ask). Skip 4, 6, 8, 9, 11.

Do not skip the demo to save time. It is the only part they cannot get from
reading the repo.

## If they cut you off early

The three sentences that must be said, in this order:

1. "Every player sees the same lobby, and 74% of what they play is something new
   — the demand is already there."
2. "Our own recommender lost to popularity on the head, so we kept popularity —
   and we beat it 4.28× on the tail, where 76.5% of discovery actually happens."
3. "A self-excluded account is never scored, and 58% of stake is on games we
   can't name — a catalogue export from you fixes that."

---

## Questions — see `demo/live-demo.md`

The Q&A prep lives there, including the two you should *want* asked: why you
kept the popularity row, and why there's no revenue number.
