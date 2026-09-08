# AI assistance disclosure

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

> ⚠️ **ACTION REQUIRED BEFORE SUBMISSION** — sections marked
> **[TEAM TO CONFIRM]** need the team's own answer. Everything else is an
> accurate record of how the code in this repository was produced.

---

## 1. Summary

AI assistance was used **materially**. An AI coding assistant (Anthropic
Claude, via Claude Code) performed the dataset analysis and wrote the
substantial majority of the source code and documentation here, working from
the team's problem statement, direction and decisions.

We disclose this in full rather than minimally, because the submission
guidelines ask for disclosure "where materially applicable" and this is
squarely that case.

---

## 2. What the AI did

| Area | Extent |
|---|---|
| Feasibility analysis of `CA_Player.csv` (scale, sparsity, split viability) | **AI-performed** |
| `src/pipeline/build_dataset.py`, `src/recsys/*` (catalogue, baselines, item-item, ALS, evaluation, training, serving) | **AI-written** |
| `src/api/app.py`, `src/dashboard/index.html` | **AI-written** |
| `tests/test_recsys.py` | **AI-written** |
| All five documents in `docs/`, the README, repository scaffolding | **AI-written** |

**Tool:** Anthropic Claude (Claude Code), 8 September 2026.

---

## 3. What the team did

| Area | Extent |
|---|---|
| The problem statement — a static lobby, and a game recommender to fix it | **Team-originated** |
| The pivot away from the earlier session-intelligence concept | **Team decision** |
| Dropping quantum optimisation after reviewing the AI's assessment | **Team decision** |
| Scope decisions during the build (nameable games only, deliverable shape, keeping the repo scaffolding) | **Team** |
| Review and acceptance of the code and documentation | **[TEAM TO CONFIRM]** |
| Repository ownership and submission | **Team** |

### A decision worth recording

The team asked whether **quantum optimisation** could accelerate the
recommender. The AI's answer was that it could not, and gave the reasons:
recommendation systems is the canonical case of a *disproven* quantum speedup
(Kerenidis & Prakash 2016, dequantised by Ewin Tang 2018); the only honest
mapping is slate assembly as a QUBO, and at 6 slots from ~3,200 candidates a
classical greedy solver runs in microseconds while a cloud QPU costs hundreds
of milliseconds. It also confirmed quantum appears nowhere in FEG's agenda,
guidelines or regulations guide. **The team dropped it.** No quantum claim
appears anywhere in this submission.

---

## 4. Verification we can evidence

- **Every figure** in `docs/evaluation.md` regenerates from
  `artifacts/eval_full.json` via `python -m src.recsys.evaluate`. None is typed
  by hand.
- **22 tests pass**, including `test_item_item_beats_popularity_on_tail_discovery`,
  which asserts the headline claim against the real artifacts.
- **The headline result is a partial negative** and is reported as such:
  collaborative filtering loses to most-played on next-game prediction. An
  AI-written submission that only reported flattering numbers would be the
  thing to worry about; this one leads with the loss.

---

## 5. Two bugs the AI introduced, found, and fixed

Recorded because they are exactly the failure mode AI-assisted work is
criticised for, and because both are now regression-tested.

1. **The popularity-correction parameter was a silent no-op.** The first
   implementation damped item columns and *then* L2-normalised them. Cosine is
   scale-invariant per column, so every `alpha` produced byte-identical output.
   Caught because a parameter sweep returned suspiciously identical numbers.
   Fixed by applying the correction to the similarity matrix.
   Test: `test_popularity_correction_actually_has_an_effect`.
2. **An accounting row was nearly treated as a game.** The export contains
   `NA - Deposit / Withdrawal / Corrections`. Left in, it co-occurs with
   everything and becomes the most similar item to every game on the site.
   Test: `test_accounting_row_is_not_a_game`.

An earlier, discarded direction also had a measurement error found the same
way — an event-weighted conversion rate that did not survive being recomputed
per session. That work is not part of this submission.

---

## 6. Known risks of the approach

| Risk | Mitigation |
|---|---|
| Plausible-but-wrong statistics | Every figure traces to a re-runnable pipeline; the evaluation harness is short and commented |
| Overstated capability | `docs/architecture.md` §9 and README §11 list what is **not** built |
| Overconfident impact claims | `docs/impact-case.md` §3.1 refuses to invent a revenue figure and §3.2 names the untested assumption explicitly |
| Misread regulation | `docs/compliance-note.md` cites instruments by number, marks the DPIA and FEG Legal review as gating, and is explicitly not legal advice |
| Code that looks right but is unreviewed | **[TEAM TO CONFIRM]** — this is the residual risk, and team review is the control |

---

## 7. Data handling by the AI tool

`CA_Player.csv` was read **locally** by analysis code on the team's machine.
Only aggregate results — counts, rates, metrics — entered the assisted session.
Player identifiers are pre-hashed by FEG; none were transmitted, and no
personal data appears in this repository.

**[TEAM TO CONFIRM]** — if FEG's participant terms restrict processing the
supplied dataset with third-party AI tooling, check that against this
disclosure before submitting.

---

## 8. Statement

The team takes full responsibility for this submission, including all
AI-generated content within it. The problem statement and the key scope
decisions are the team's own. The implementation was substantially
AI-assisted and is disclosed as such above.
