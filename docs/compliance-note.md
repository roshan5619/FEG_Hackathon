# Compliance note

**PSK Game Recommender**
Team Q'Makers · FEG Innovation Challenge 2026

> This note records the compliance considerations we designed against and the
> concrete implementation choices that follow from them. It is a hackathon
> proof-of-concept analysis, **not legal advice**, and does not replace the
> FEG Legal & Compliance review required before any of this processes real
> data or goes live. Sources are the FEG-supplied *EU & Croatia Compliance
> Guide* (4 September 2026) and the EUR-Lex instruments it cites.

---

> **Need the one-page version?** [`compliance-one-pager.md`](compliance-one-pager.md) covers the EU
> baseline and the responsible-gambling rules on a single page. This document is
> the full analysis behind it.

## 0. Why this document is short on promises and long on file paths

A personalisation engine on a gambling platform is the exact thing the EU AI
Act singles out. So rather than assert that the design is compliant, each
requirement below names the code that implements it and the test that holds it
in place. Everything here is checkable.

---

## 1. The one that shapes the architecture: EU AI Act

**Reg. (EU) 2024/1689.** Manipulative or exploitative AI practice is
**prohibited outright** — not high-risk, not conditional. Any recommendation,
risk-scoring or personalisation feature must avoid dark patterns and must not
exploit vulnerabilities.

This is not a constraint we work around. It is the reason the system is built
the way it is.

**What we implemented**

| Requirement | Implementation |
|---|---|
| No manipulative patterns | The lobby recommends games; it never nudges a stake. No countdown timers, no "X others are playing", no scarcity, no urgency copy anywhere in `src/recsys/serve.py` or the dashboard. |
| Must not exploit vulnerability | Harmful-play indicators **invert** the objective rather than tuning it: from `MODERATE`, every engagement row is withheld and only *Continue playing* survives. `src/recsys/responsible.py`; single chokepoint in `serve.LobbyService.lobby()`. Tested by `test_moderate_risk_suppresses_engagement_rows`. |
| Explainability | Two levels, both exact. Every tile carries a `why` string naming the **literal top contributor** to its score. And `GET /explain/{player}/{game}` returns the full per-feature attribution from the trained ranker: contribution = coefficient x standardised value, which sum to the logit and reconstruct the model's probability — asserted by `test_explanation_is_exact_for_logistic_regression`. Logistic regression was chosen over gradient boosting partly *because* a boosted ensemble has no such exact decomposition. |
| Human oversight | Ships in shadow mode: log recommendations against the live lobby without rendering them, and compare before switching traffic. Each row is independently feature-flagged; the responsible-play inversion is not. |
| Data minimisation in the model | The ranker's 14 features are behavioural and game-level only — which games, which providers, how recently, how popular. **No demographic, financial, device or location attribute is used, and none is available to it.** `src/recsys/features.py` |
| Payout ratio, used carefully | A per-game win/stake proxy is a *similarity* feature only. It never ranks games and is never shown to a player: advertising "this game pays more" is precisely the inducement the AI Act prohibits. |

**Status note.** The Digital Omnibus AI strand entered into force 27 July 2026
and defers the high-risk timeline by up to 16 months. The *prohibition* on
manipulative practice is not what was deferred. Re-check in-force provisions
before build-out.

---

## 2. Croatia — binding, not soft law

The **Act on Measures for Socially Responsible Organisation of Games of
Chance** requires ID/age verification **and a check against the register of
excluded players before play is allowed**. Regulator: Ministry of Finance.

The guide is explicit that this must be a real check pattern, **not a UI
checkbox**. That distinction drove our order of operations.

**What we implemented**

- `responsible.assess()` runs **before** the player is scored, not after.
  A blocked account is never scored at all — `/recommendations/{id}` returns
  **zero rows**. Not "scored then filtered": never scored. Tested by
  `test_self_excluded_account_is_blocked_before_scoring`.
- Hard gates: `self_excluded`, `on_exclusion_register`, `age_verified is
  False`, `deposit_limit_reached`. Each returns `BLOCKED`/`SEVERE` with
  `hard_gate: true` and the required surfaces.
- **Hard gates are deliberately absent from `config/thresholds.example.yaml`.**
  Every other threshold is tunable; these are legal preconditions and no
  configuration can relax them.
- Age verification is checked at *any* entry point, not only registration —
  `tests/test_recsys.py::test_unverified_age_is_a_hard_gate`.
- **The demo puts the two gates where the law puts them, and they differ.**
  An age/ID-unverified account is **refused sign-in entirely** and never
  receives a session, because the check must precede play. A self-excluded
  account **signs in successfully** — self-exclusion blocks inducements, not
  account access, and the person must still reach their account and support —
  but their lobby returns zero recommendations plus the required surfaces.
  Both directions are asserted:
  `tests/test_auth.py::test_age_unverified_is_refused_a_session` and
  `::test_self_excluded_signs_in_but_gets_nothing_to_play`.

Data protection is supervised nationally by **AZOP**; AML/KYC by the
Anti-Money-Laundering Office under the Ministry of Finance. Croatia has adopted
a DSA implementing act (see §6).

---

## 3. Responsible gambling — the ground rules

The challenge ground rules require: no dark patterns; no inducements targeting
vulnerable or self-excluded customers; 18+ respected throughout.

**No inducements to at-risk or excluded accounts.** This is the property we
tested hardest, because it is the one most easily broken by a later change.
There is exactly **one** place a row can be withheld — the suppression block at
the end of `serve.LobbyService.lobby()`. From `MODERATE`, every row except
*Continue playing* is withheld, and the withheld row keys are returned in
`suppressed_rows` rather than silently dropped, so the audit log records what
was *not* shown.

**Graded inversion** (`src/recsys/responsible.py`):

| State | Trigger | Response |
|---|---|---|
| `NORMAL` | no indicators | normal operation |
| `MILD` | score ≥ 1 | lobby unchanged; session timer surfaced by the host client |
| `MODERATE` | score ≥ 3 | **every engagement row withheld**; only *Continue playing* remains |
| `SEVERE` | score ≥ 5 | as MODERATE, plus limit tools and cool-off, non-dismissable |
| `BLOCKED` | hard gate | **zero rows**. Nothing from the recommender reaches the account |

Indicators: session duration past 1h/2h, repeated in-session deposits, stakes
above the player's own history, loss-chasing re-stake pattern, limit-increase
request, sustained overnight play. All are supplied by the caller from the
player record; the recommender never infers them.

**Design choices that follow from "no dark patterns":**

- **The recommender suggests games, never amounts.** Stake appears only as a
  training weight (`log1p`), never in any output. There is no code path that
  can produce a monetary suggestion.
- **No urgency, scarcity or social pressure.** The only social signal is
  aggregate popularity, labelled plainly as "Popular across PSK".
- **No outcome data is shown** — no wins, no near-misses, no jackpot counters.
- **Explanations are decompositions, not persuasion.** A tile's `why` is the
  literal largest contributor to its score. Where the source game has no name
  in the data, the copy says so rather than inventing one.
- **The fallback for a suppressed lobby is the incumbent**, not a blank page:
  a player who opts out of personalisation sees the popularity row psk.hr
  already ships.

**EU soft-law baseline:** Commission Recommendation 2014/478/EU (risk
information, deposit/spend limits, self-exclusion, responsible advertising).
Croatia's national rules make several of these binding, as above.

---

## 4. GDPR — Reg. (EU) 2016/679

| Requirement | Implementation |
|---|---|
| **Never use real personal data** | The repository contains **no** personal data. Every FEG source file is gitignored (`*.csv`, `*.xlsx`). Only derived artifacts ship. |
| Anonymisation | `PlayerID` arrives **pre-hashed** from FEG and is used only as an opaque key. No name, email, document, balance, transaction or device attribute exists anywhere in the repository. |
| Data minimisation (Art. 5) | The model consumes exactly one signal — which games a player staked on, and how much. Nothing else is read from the export, and the API request carries only account-level booleans supplied by the caller. |
| Privacy by design (Art. 25) | A blocked account is never scored: the privacy-preserving default is to not compute rather than to compute-and-discard. |
| DPIA for high-risk profiling | **Required before production.** This is behavioural profiling of gambling customers; a DPIA is not optional and we flag it as a gating item, not a formality. See §9. |
| Right to object to profiling (Art. 21) | Not implemented. A production build needs a "don't personalise my lobby" control that falls the player back to the popularity row — which, usefully, is exactly what the incumbent already is. |
| Player rights | The decision log is keyed by session and player id so decisions are retrievable and erasable on request. Not implemented in the prototype. |
| 72h breach notice | Deployment-time obligation; out of prototype scope. |

Practical guidance for Art. 25: **EDPB Guidelines 4/2019**.

---

## 5. ePrivacy — Directive 2002/58/EC (as amended)

Still the binding instrument; the proposed ePrivacy Regulation is not adopted.

The prototype sets **no cookies**, uses **no client-side storage**, and runs
**no marketing or notification flow**. It consumes events the platform already
collects rather than adding instrumentation, so it introduces no new
terminal-equipment storage of its own.

Where this layer is integrated, the existing PSK consent state must gate event
ingestion, and any push/notification surfacing an adaptation would need genuine
opt-in — never pre-ticked.

---

## 6. Other instruments considered

| Instrument | Assessment |
|---|---|
| **AMLD 2015/849 / AMLR 2024/1624** | Not triggered. No onboarding, KYC, payment or source-of-funds flow. `deposits_this_session` is an integer count used as a *harm* indicator, not an AML control, and is supplied by the caller. |
| **eIDAS 2.0 (Reg. 910/2014, 2024/1183)** | Not implemented. If age/identity verification is built out, the EUDI Wallet attribute-based pattern is the forward-looking choice — attribute assertion ("over 18") rather than document transfer. |
| **Accessibility — EAA 2019/882 / WCAG 2.1 AA** | The dashboard uses semantic controls (`<select>`, real checkboxes), visible focus states, `prefers-reduced-motion`, and text labels on every state — the responsible-play banner names its state in words, never colour alone. Row identity is carried by a text label, not the accent colour. Known gap: game tiles are decorative colour blocks with no alt text, because no thumbnail or description exists in the data. |
| **DSA (Reg. 2022/2065)** + Croatian implementing act | Marginal. No user-generated content, no marketplace, no ads. It *is* a recommender system in the broad sense, so the transparency posture (§1 explainability) is the relevant mitigation. |
| **NIS2 (2022/2555)** | Below scope thresholds for a POC. Good practice applied: no hard-coded secrets, no real credentials, `.env` gitignored, `.env.example` carries only non-secret defaults with production integration keys left blank. |
| **EU Data Act 2023/2854** | Not relevant — no connected devices, no cloud-switching feature. |
| **CSRD / CS3D / EU Taxonomy** | Corporate reporting obligations; not technical build requirements. Background only. |

---

## 7. Data handling in this repository

**Demo accounts.** `src/api/demo_users.json` holds 12 prototype logins. The
usernames and display names (`ana.k`, `Ana K.`) are **invented labels** attached
to pre-hashed anonymous player identifiers. The export contains no name, age,
gender, location or any other personal attribute, so none can be revealed. The
*play history* behind each account is real; the person is not. Passwords are
stored only as PBKDF2-SHA256 hashes with per-user salts — no plaintext
credential exists in the repository — and the session cookie is HMAC-signed,
`httponly` and expiring. This is prototype auth: no rate limiting, no lockout,
no rotation, no MFA, and it is not proposed as production authentication.

**Committed:** `artifacts/catalog.json` (game codes and parsed names),
`interactions.npz` (the sparse matrix, keyed by pre-hashed ids), `model.npz`
(item-item similarities), and the evaluation outputs. 18 MB total.

**Not committed, and gitignored:** every FEG source file (`*.csv`, `*.xlsx`),
the supplied video, and any `.env`.

**Judgement made:** `interactions.npz` contains, for 23,673 pre-hashed player
ids, which games each staked on. That is behavioural data about individuals,
even though it carries no direct identifier and no monetary value (stake is
stored as `log1p`, and only as a relative confidence). We assessed
re-identification risk as low — no demographic, financial, device or temporal
detail is retained, and the ids are FEG's own hashes. **If FEG's reviewers
prefer, the matrix can be dropped from the repository entirely**; the pipeline
regenerates it in one command from the source data, and only the demo would
need the source file present.

---

## 8. Prohibited-practice checklist

| Practice | Present? | Where verified |
|---|---|---|
| Countdown timers / fake urgency | No | no time-based copy anywhere in `serve.py` or the dashboard |
| Social proof pressure ("others are playing") | No | the only social signal is aggregate popularity, labelled plainly as "Popular across PSK" |
| Scarcity mechanics | No | no inventory or availability framing |
| Any stake suggestion | No | the recommender suggests **games**, never amounts. Stake appears only as a training weight |
| Autoplay / forced continuity | No | tiles are links; nothing launches itself |
| Inducements to at-risk accounts | No | `test_moderate_risk_suppresses_engagement_rows` |
| Inducements to self-excluded accounts | No | `test_self_excluded_account_is_blocked_before_scoring` — zero rows |
| Profiling that overrides a limit | No | hard gates precede scoring |
| Losses/near-miss framing | No | no outcome data is shown at all |
| Real personal data in the repo | No | `.gitignore`; ids are FEG's pre-existing hashes |
| Secrets in the repo | No | `.env` ignored; `.env.example` non-secret |

---

## 9. Gating items before any production build

1. **DPIA** — mandatory. Behavioural profiling of gambling customers.
2. **FEG Legal & Compliance review** of the responsible-play thresholds and of
   the adaptation catalogue.
3. **Live integration with the exclusion register.** The gate is implemented
   and tested; the data connection is not built.
4. **Lawful-basis determination** for behavioural profiling, and the consent
   architecture that follows from it.
5. **Re-check in-force AI Act provisions** — the Digital Omnibus timeline is
   still moving.
6. **Independent review of the priors for proxy discrimination.** Surfaces are
   not protected characteristics, but a platform-level prior (GM at 10.9%
   versus Casino Android at 58.2%) could correlate with device affordability.
   This should be checked before the platform term is allowed to influence any
   player-facing decision.

---

## 10. AI assistance disclosure

See [ai-use-disclosure.md](ai-use-disclosure.md).
