# Compliance note — one page

**PSK Personalised Lobby** · Team Q'Makers · FEG Innovation Challenge 2026

*The full analysis, with every claim mapped to code and tests, is
[`compliance-note.md`](compliance-note.md). This page is the summary.*

---

## The position

A personalisation engine on a gambling platform is the exact thing the EU AI
Act singles out. So compliance is not a layer on top of this system — it
determines the order of operations inside it. **The responsible-play gate runs
before the model, not after it.** A blocked account is never scored; the API
returns zero rows rather than a filtered list.

## EU baseline

| Instrument | What it requires | What we did |
|---|---|---|
| **AI Act** Reg. (EU) 2024/1689 | Manipulative or exploitative AI practice is **prohibited outright** | No urgency, scarcity, countdowns, "others are playing", or near-miss framing anywhere. Harm indicators **invert** the objective instead of tuning it |
| **AI Act** — explainability | Meaningful information about the logic | Every tile names the **literal top contributor** to its score. `GET /explain` returns per-feature attribution that reconstructs the model's probability exactly — asserted by a test. Logistic regression was chosen partly *because* boosting has no exact decomposition |
| **GDPR** Reg. (EU) 2016/679 | Lawfulness, minimisation | The 14 features are behavioural and game-level only. **No demographic, financial, device or location attribute is used or available.** Player ids arrive pre-hashed; no personal data is in the repository |
| **ePrivacy** Dir. 2002/58/EC | Consent for non-essential storage | One session cookie, strictly necessary, `httponly`, signed, expiring |
| **Rec. 2014/478/EU** | Risk information, limits, self-exclusion | Required surfaces are returned in the API response, not left to the client |

## Responsible gambling

**Two gates, and they fire in different places, because the law treats them
differently.** Croatia's *Act on Measures for Socially Responsible Organisation
of Games of Chance* requires ID/age verification and an exclusion-register check
**before play is allowed** — a real check pattern, not a UI checkbox.

- **Age / ID unverified → sign-in refused.** No session is issued at all.
- **Self-excluded → sign-in succeeds, lobby returns zero rows.** Self-exclusion
  blocks *inducements*, not account access: the person must still reach their
  account and support.

Getting either backwards would be a real compliance failure, so both directions
are asserted in tests rather than described in prose.

**Graded inversion.** As indicators accumulate — long sessions, repeated
in-session deposits, stake above the player's own history, loss-chasing — the
objective flips from surfacing more to surfacing less. From `MODERATE` every
engagement row is withheld and only *Continue playing* survives; withheld rows
are returned in the response, so the audit log records what was **not** shown.
Hard gates are deliberately absent from the config file: every other threshold
is tunable, these are legal preconditions.

**The system recommends games, never amounts.** Stake appears only as a
training weight. No code path can produce a monetary suggestion. Payout ratio is
a similarity feature only — never ranked on, never shown, because advertising
"this game pays more" is precisely the prohibited inducement.

## Known gaps

Prototype auth (no rate limiting, lockout or MFA). Harm indicators are supplied
by the caller from the player record — the recommender never infers them, and
production would need those fields wired from FEG's systems. No DPIA has been
run; one is required before any live deployment.
