# AI Assistance Disclosure

## PSK Game Recommender
**Team Q'Makers · FEG Innovation Challenge 2026**

---

## 1. Overview

AI-assisted tools were used during the development of this project, primarily as **development and technical support tools**.

The **problem definition, product direction, core concept, scope decisions, solution direction, evaluation objectives, and final submission ownership remained with Team Q'Makers**.

As team leader, I was responsible for defining and steering the core product direction, coordinating the team's decisions, evaluating technical approaches, and determining what was ultimately included in the submission.

AI assistance was used where it accelerated implementation, analysis, documentation, debugging, testing, and iteration. The team reviewed the resulting work and remains responsible for the final submission.

---

## 2. What the Team Originated and Owned

The following aspects were **team-led**:

| Area | Team contribution |
|---|---|
| **Problem identification** | Identified the static PSK lobby/discovery experience as the core product problem |
| **Product concept** | Developed the concept of using a game recommender to improve game discovery |
| **Product direction** | Defined the intended user experience and project objectives |
| **Core solution decisions** | Determined what the recommender should and should not attempt to solve |
| **Scope** | Defined the practical scope, including nameable games and the final deliverable |
| **Technical direction** | Evaluated alternative technical approaches and selected the approach used |
| **Quantum approach decision** | Investigated whether quantum optimisation provided a meaningful advantage and decided not to pursue it |
| **Evaluation objectives** | Defined the need to compare recommendation approaches against meaningful baselines |
| **Product interpretation** | Interpreted the recommendation results and their implications for PSK |
| **Final submission** | Team-owned the final product direction, review, decisions, and submission |

### Team Leadership

As team leader, I coordinated the transition from the initial concept through technical exploration and into the final recommender direction.

The team made the final decisions about:

- what problem to solve;
- what solution to pursue;
- what evidence was sufficient;
- what experiments were meaningful;
- what limitations should be reported;
- and what claims could responsibly be made.

---

## 3. Where AI Assistance Was Used

AI assistance was used during implementation and supporting analysis.

| Area | AI assistance |
|---|---|
| Dataset exploration and preliminary analysis | AI-assisted |
| Recommendation-system implementation | AI-assisted |
| Dataset construction pipeline | AI-assisted |
| Baseline implementations | AI-assisted |
| Item-item recommendation implementation | AI-assisted |
| ALS implementation | AI-assisted |
| Evaluation utilities | AI-assisted |
| API implementation | AI-assisted |
| Dashboard implementation | AI-assisted |
| Automated tests | AI-assisted |
| Documentation and repository structure | AI-assisted |
| Debugging and technical iteration | AI-assisted |

**AI tool:** Anthropic Claude via Claude Code  
**Date of use:** 8 September 2026

AI-generated implementation was **not treated as automatically correct**. Outputs were examined through testing, reruns, parameter checks, comparison against expected behavior, and technical review.

---

## 4. Human Review and Decision-Making

The team did not treat AI output as evidence by itself.

The development process followed:

> **Team problem → Team direction → AI-assisted implementation → Testing → Human review → Iteration → Final team decision**

The team retained responsibility for:

- deciding whether an approach was appropriate;
- checking whether results were plausible;
- identifying misleading or incorrect outputs;
- deciding which experiments were meaningful;
- interpreting the results;
- determining which claims could be made in the submission.

---

## 5. Examples of Human–AI Iteration

During development, the team identified implementation issues that required investigation rather than simply accepting generated output.

### Example 1 — Popularity Correction

A parameter sweep produced suspiciously identical results.

Investigation showed that the initial popularity correction was applied before L2 normalization, making the parameter effectively scale-invariant for the subsequent cosine calculation.

The implementation was corrected and a regression test was added to verify that the parameter actually changes recommendation behavior.

### Example 2 — Non-Game Accounting Record

The dataset contained:

`NA - Deposit / Withdrawal / Corrections`

The record could incorrectly behave like a game because of its co-occurrence pattern.

The team identified this as a data-quality issue, excluded it from the game catalogue, and added a regression test to ensure that it could not become a recommended game.

### Why These Examples Matter

These examples demonstrate that AI-generated implementation was **subject to technical scrutiny rather than accepted uncritically**.

---

## 6. Results and Verification

The reported evaluation results are generated from the project's artifacts and evaluation pipeline rather than manually fabricated for the submission.

The repository includes automated tests covering important recommendation-system behavior.

Where experiments produced results that did **not** support the expected hypothesis, those results were retained rather than selectively removed.

In particular:

> **Collaborative filtering does not outperform the most-played baseline for every evaluation objective.**

This limitation is reported as part of the result rather than hidden.

The team's position is that a credible recommendation system should be evaluated against strong baselines and should report both its strengths and limitations.

---

## 7. Important Product Decision: Quantum Optimisation

The team investigated whether quantum optimisation could provide a meaningful advantage for the recommender.

After evaluating the proposed mapping, the team determined that quantum optimisation did not provide a justified advantage for the problem at the current scale.

The team therefore **removed the quantum component from the final solution rather than making an unsupported quantum claim**.

This was a deliberate product and technical decision made by the team.

---

## 8. Data Handling

The supplied player dataset was processed locally during development.

Player identifiers were pre-hashed by FEG.

The project does not intentionally expose player-level personal information in the submitted documentation or dashboard.

AI assistance was used during development. The team will verify that this processing is consistent with the applicable FEG participant and data-use terms before submission.

---

## 9. Responsibility

The team accepts responsibility for the final submission, including:

- the problem definition;
- the product concept;
- the technical direction;
- the interpretation of results;
- the claims made in the submission;
- the AI-assisted implementation;
- and the final repository.

AI assistance does not transfer responsibility for the resulting work away from the team.

---

## 10. Final Statement

> **Team Q'Makers developed the problem definition, product direction, core solution concept, and key technical decisions for the PSK Game Recommender. AI-assisted development tools, including Claude Code, were subsequently used to accelerate portions of implementation, analysis, debugging, testing, and documentation. The team reviewed the resulting work, challenged unexpected results, made the final technical and product decisions, and takes full responsibility for the submitted system and claims.**