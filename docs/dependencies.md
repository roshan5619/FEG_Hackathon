# Dependency & third-party component disclosure

**PSK Game Recommender** · Team Q'Makers · FEG Innovation Challenge 2026

---

## 1. Summary

| Category | Count | Note |
|---|---|---|
| Model / pipeline dependencies | 2 | NumPy, SciPy |
| API dependencies | 3 | FastAPI, Uvicorn, Pydantic |
| Test dependencies | 2 | pytest, httpx |
| Front-end libraries | **0** | the dashboard is hand-written HTML/CSS/JS |
| External APIs / SDKs called at runtime | **0** | |
| Pre-trained models | **0** | |
| Third-party datasets | **0** | see §5 |

All licences are permissive (MIT / BSD-3-Clause). No copyleft, no commercial
licence, no attribution obligation beyond retaining licence text.

---

## 2. Python packages

| Package | Version | Licence | Used for | Scope |
|---|---|---|---|---|
| [numpy](https://github.com/numpy/numpy) | 1.26.4 | BSD-3-Clause | arrays, ranking, metrics | runtime |
| [scipy](https://github.com/scipy/scipy) | 1.16.2 | BSD-3-Clause | sparse matrices; the model is one sparse product | runtime |
| [fastapi](https://github.com/fastapi/fastapi) | 0.134.0 | MIT | HTTP API, OpenAPI docs | runtime (API) |
| [uvicorn](https://github.com/encode/uvicorn)[standard] | 0.40.0 | BSD-3-Clause | ASGI server | runtime (API) |
| [pydantic](https://github.com/pydantic/pydantic) | 2.11.7 | MIT | request validation | runtime (API) |
| [pytest](https://github.com/pytest-dev/pytest) | 8.3.4 | MIT | test runner | dev |
| [httpx](https://github.com/encode/httpx) | 0.28.1 | BSD-3-Clause | required by `fastapi.testclient` | dev |

`uvicorn[standard]` pulls transitive extras (`httptools`, `uvloop`,
`watchfiles`, `websockets`, `python-dotenv`, `PyYAML`) — all MIT or
BSD-3-Clause. Plain `uvicorn` works if a smaller tree is preferred.

### Deliberately not used

| Package | Why not |
|---|---|
| **pandas** | The pipeline reads one CSV in a single pass with the stdlib `csv` module. Pandas would add ~60 MB for no benefit. |
| **implicit** | ALS is ~30 lines in `src/recsys/item_item.py`. A compiled dependency for one comparison model is not worth the install friction. |
| **scikit-learn** | Nothing here needs it. |
| **torch / tensorflow** | No neural model. Item-item CF is the right tool at this density. |

---

## 3. Front-end

`src/dashboard/index.html` is a single hand-written file. No React, no Vue, no
CSS framework, no charting library, no build step.

| Component | Source | Licence |
|---|---|---|
| **Archivo** typeface | Google Fonts | SIL Open Font License 1.1 |
| **IBM Plex Mono** typeface | Google Fonts | SIL Open Font License 1.1 |

**This is the only outbound network request the project makes**, and it is
cosmetic — both faces have fallback stacks. Delete the `<link>` for an
air-gapped review.

Game tile artwork is generated from a deterministic hash of the title. **No
stock imagery, icon set or third-party asset is included** — and none could be,
since 83% of games in the data cannot even be named.

---

## 4. Algorithms and references

Not code dependencies, but intellectual provenance that should be disclosed:

| Input | Use |
|---|---|
| Item-item collaborative filtering (Sarwar et al., 2001) | The primary model. Standard formulation with shrinkage and top-k neighbour pruning. |
| Implicit-feedback ALS (Hu, Koren & Volinsky, 2008) | Hand-implemented comparison model in `item_item.py`. Untuned, unreported. |
| NDCG (Järvelin & Kekäläinen, 2002) | Ranking metric; implementation verified by hand against a fixture in `tests/`. |
| FEG stack diagram (supplied with the brief) | Basis for the stack alignment in `architecture.md` |
| FEG EU & Croatia Compliance Guide (4 Sep 2026) | Basis for `compliance-note.md` |

No code was copied from a tutorial, sample repository or Stack Overflow answer.

---

## 5. Data

| Dataset | Origin | In repo | Permission |
|---|---|---|---|
| `CA_Player.csv` | FEG hackathon data | **NO** — gitignored | Property of Fortuna Entertainment Group |
| `SB_Player.csv`, `CA_MOM.csv`, `SB_MOM.csv`, `EPS_Offers.csv` | FEG | **NO** — not used | as above |
| `top_casino_users_event_logs*` | FEG | **NO** — used only for exploratory analysis of lobby surfaces | as above |
| `artifacts/catalog.json` | derived | yes | game codes + parsed names; no personal data |
| `artifacts/interactions.npz` | derived | yes | sparse matrix keyed by **pre-hashed** player ids |
| `artifacts/model.npz` | derived | yes | item-item similarity, popularity, cold-item list |
| `artifacts/eval_full.json`, `dataset_report.json`, `model_report.json` | derived | yes | aggregate metrics only |

Player identifiers arrive **pre-hashed** from FEG and are used only as opaque
keys. **No name, email, document, balance, transaction or device attribute
exists anywhere in this repository.** Total committed artifacts: 3.4 MB.

No third-party dataset, no scraped data, no purchased data, no public dataset
is used anywhere in this project.

---

## 6. Models

**No pre-trained model, no model API, no embedding service, no hosted
inference.**

The shipped model is an item-item cosine similarity matrix computed from the
FEG export by `src/recsys/train.py`. It is arithmetic over a sparse matrix,
contained entirely in `artifacts/model.npz` (902,348 non-zero similarities),
and fully reproducible from the source data in one command.

---

## 7. AI assistance

Disclosed in full in [`ai-use-disclosure.md`](ai-use-disclosure.md).

---

## 8. Verifying this disclosure

```bash
# Every import in the shipped source
grep -rhoE "^[[:space:]]*(import|from) [a-z_]+" src/ --include=*.py | sort -u

# Confirm no data or media files are staged
git status --porcelain | grep -E "\.(csv|xlsx|xls|parquet|mp4|mov)$"   # expect none

# Confirm committed artifacts are small
du -sh artifacts/                                                       # ~3.4 MB
```
