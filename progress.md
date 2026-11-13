# DrivePulseAI: implementation progress audit

**Baseline:** local checkout `main` at `9d79a59` (commit subject “Audit and organize datasets…”), as of 2026-11-13. The workspace already had extensive modifications before this report; they were preserved. Audit reports and `tasks_done.md` are documentation additions; Component X v3 publisher files were acquired under `data/automotive_prognostics/scania_component_x/v3/raw/` and retained unchanged. **User scope decision: passenger cars and passenger EVs only.** Truck datasets are excluded from car performance claims.

## Step 0 — environment and baseline (2026-11-13)

**Status: ✅ Done and verified for the existing ML environment.**

- Created branch `pipeline/data-and-training` from commit `9d79a59`.
- Host: WSL2 Linux x86_64, Python 3.12.3, 12 CPUs, 15 GiB RAM (14 GiB available), 175 GiB free on the repository filesystem.
- The repository’s existing root `.venv` imports NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.7.2 and XGBoost 3.4.0. `./.venv/bin/python -m pytest -q ml/tests --disable-warnings --maxfail=1` passed **41 tests in 8.15 seconds**.
- A system Python 3.12.3 outside `.venv` lacks the ML dependencies. MLflow is listed in `ml/requirements.txt` but is not installed in the existing `.venv`; no MLflow run was claimed or created. The current repository tracking helper is a comment-only stub (`ml/src/training/mlflow_utils.py`).
- Added exact versions for the verified local environment in `ml/requirements.lock.txt` and the shared seed helper in `ml/src/reproducibility.py`; the global seed convention is `GLOBAL_SEED = 42`.
- Data layout is mapped under `data/automotive_obd/`, `data/automotive_failure/`, and `data/automotive_prognostics/`; model code is under `ml/src/`, tests under `ml/tests/`, and model artifacts are ignored under `ml/artifacts/`.

Step 0 gate: **pass** using the existing `.venv`; the system interpreter alone is not a valid ML environment. Step 1 dataset validation is next.

## Repository map

Top-level directories: `.agents/`, `.aws/`, `.codex/`, `.github/`, `backend/`, `data/`, `docs/`, `frontend/`, `ml/`, `mobile/`, `scripts/`, `simulator/`; root configs include `.env.example`, `requirements.txt`, `docker-compose.yml`, `docker-compose.dev.yml`, `.pre-commit-config.yaml`, and `LICENSE`. Generated/local directories also present: `.venv`, `.pytest_cache`, `.ruff_cache`, `backend/.venv`, `backend/node_modules`, `frontend/node_modules`, `frontend/.next*`, `mobile/node_modules`, and `mobile/.expo` (environment/runtime, not source components). No Dockerfile found in the current file inventory; compose files exist.

| Area | Language/framework/package manager | Entry points and evidence |
|---|---|---|
| ML | Python, pandas/scikit-learn/XGBoost; `ml/requirements.txt`, `ml/pyproject.toml` | Working APS training script `ml/src/training/train_failure.py`; comment-only `train_anomaly.py`, `train_rul.py`; notebooks `02_eda_cmapss`, `03_anomaly_isolation_forest`, `04_failure_classification_xgboost`, `05_rul_regression` |
| Backend | Python, FastAPI, SQLAlchemy/Alembic; `backend/pyproject.toml`, `backend/requirements.txt` | `backend/app/main.py`; only `backend/app/api/routes/users.py` contains implemented routes; other route/service files are one-line comments |
| Mobile | TypeScript/React Native/Expo Router; npm lockfile and `mobile/package.json` | `mobile/src/app/_layout.tsx`, route tree under `mobile/src/app/`; screens include auth, tabs, vehicle, sensor, report and insight routes |
| Website | TypeScript/Next.js; npm lockfile and `frontend/package.json` | `frontend/src/app/page.tsx`, `layout.tsx` |
| Simulator | Python | `simulator/src/telemetry_generator.py`, `fault_injection.py`, `stream_client.py`; `simulator/pyproject.toml` |
| Data/scripts/docs | CSV/XLSX/XML/zip/text, Python/shell/Markdown | `data/README.md`, `scripts/download_datasets.sh` (comment-only), `scripts/seed_database.py`, `docs/diagrams/`, `docs/screenshots/` |

Data tree summary: current data folders include `data/automotive_failure/scania_aps/raw/`, `data/automotive_obd/carobd/raw/`, `data/automotive_obd/dieselobd/raw/`, `data/automotive_obd/kit_obd/raw/`, plus acquired Component X truck data, the 20-car on-road EV capacity archives, and the 347-EV Figshare archives under `data/automotive_prognostics/`. The inventory records 129 carOBD CSVs and 81 KIT CSV recordings plus original KIT metadata/archive; Scania APS train/test CSVs; and two DieselOBD-named XLSX workbooks (`data/README.md`, sections “Status and canonical locations” and dataset-specific sections). Many raw files are individual recordings, so they are grouped here rather than enumerated one per line. No `.pt`/`.onnx` models or MLflow run directory were found. Three `.joblib` classifier bundles are present in `ml/src/models/failure_classification/`.

## Overall completion estimate

**20% complete for the passenger-car/EV target.** This is an audit estimate, not a measurement of product quality. Rubric: data 25% × 5% = 1.25 points; models 35% × average 6.7% (anomaly 0%, RUL 0%, failure-classification code 20%) = 2.33; backend 15% × 35% = 5.25; Android 15% × 65% = 9.75; tests/docs/deploy 10% × 16.5% = 1.65. Total = 1.25 + 2.33 + 5.25 + 9.75 + 1.65 = **20.2%** (rounded to 20%). Model credit reflects code artifact only: the existing failure baseline is Scania heavy-truck APS, outside the car domain, and earns no car validation credit.

## Milestone table

| Milestone | Status | % | Evidence |
|---|---:|---:|---|
| M1 Data decision/provenance | 🟡 Partial | 45% | Passenger-car/EV scope frozen by user; KIT exists; carOBD and DieselOBD provenance/labels remain unverified; Component X v3 truck audit complete; 347-EV archives acquired (CC BY 4.0) but passenger-car class unverified and local label inventory is 348 (55/293) vs paper 347 (55/292); 20-car data rights unresolved; #47 merged, #49 closed unmerged |
| M2 Anomaly baseline | ❌ Not started | 0% | `ml/src/training/train_anomaly.py` and `ml/src/models/anomaly_detector.py` are comments; no current artifact or evaluation |
| M3 RUL/health baseline | ❌ Not started | 0% | `train_rul.py`/`rul_regressor.py` comments only; no verified passenger-car/EV RUL target; acquired Component X v3 is heavy-truck data and excluded |
| M4 Failure classifier | 🟡 Partial code, out of domain | 20% | `train_failure.py`, three APS `.joblib` bundles and `ml/reports/figures/aps/output.md` implement a truck-only task; no passenger-car failure model or matched car label data |
| M5 Chained inference | ❌ Not started | 0% | `ml/src/inference/predictor.py` one-line comment; no model classes for two stages; backend inference service comment only |
| M6 API | 🟡 Partial | 40% | FastAPI app, Firebase auth and profile CRUD in `backend/app/main.py`, `app/api/routes/users.py`; prediction/telemetry/vehicle/report routes are comments |
| M7 Android app | 🟡 Partial | 70% | Real Expo Router screens/auth plus deterministic session-only demo provider; no API adapter; Android compilation/physical walkthrough not established |
| M8 Release quality | 🟡 Partial | 25% | CI workflows and test files exist; local data audit says checks passed in a prior work session; no current end-to-end deploy/model serving evidence |

## ML and data components

### Anomaly Detection — ❌ Not started

- **Algorithm/features:** README says Isolation Forest on multivariate data (`README.md`, lines 48–54) and notebooks are named accordingly. Current implementation evidence is absent: `ml/src/models/anomaly_detector.py`, `ml/src/training/train_anomaly.py`, and `ml/notebooks/03_anomaly_isolation_forest.ipynb` exist, but source modules are one-line comments; notebook saved outputs were not relied on as execution proof.
- **Training data:** no current anomaly model training pipeline. `data/README.md` identifies KIT Automotive OBD-II (real Seat Leon OBD trips, 2,693,824 rows, 11 columns, CC BY 4.0 metadata) and carOBD candidate (304,299 rows, provenance unverified) as exploratory anomaly data only. Neither has fault ground truth. The local data README says current ML loaders do not implement KIT loaders; note the current `ml/src/data/loaders.py` does now contain `load_kit_obd` and `load_carobd`, but this contradicts that older audit text. Source inspection shows these are recent/current implementations and they preserve trips as pseudo IDs; loader existence does not verify source data or anomaly results.
- **Saved model/metrics/per-part:** no anomaly artifact or metrics found. No code loops or routes per component. Status remains ❌.

### RUL / Health Score — ❌ Not started; EV capacity/SOH data acquired but not true RUL

- **Algorithm/features/target:** `ml/src/models/rul_regressor.py`, `ml/src/training/train_rul.py`, and `ml/src/inference/predictor.py` are one-line comments. Notebook `05_rul_regression.ipynb` exists; no saved model/verified output is established. README claims a degradation model (`README.md`, lines 48–54), but code does not substantiate it.
- **Dataset:** KIT/carOBD are passenger-car trips without run-to-failure or service-time labels. Component X v3 is now acquired and audited under `data/automotive_prognostics/scania_component_x/v3/raw/`, but it is real Scania heavy-truck data; this cars-only project must not use it to substantiate car RUL. The on-road EV capacity dataset now provides per-charge estimated capacity over time for 20 passenger EVs (`data/automotive_prognostics/onroad_ev_capacity/source_release/`; details in `tasks_done.md`). This can support future capacity/SOH estimation. It does not label failure or an end-of-life time, so it is not yet an RUL target and no health score/model exists.
- **Metrics/artifact/per-part:** none; no RUL artifacts. Status ❌.

### Failure Classification — 🟡 Partial code, out of domain for passenger-car claims

- **Algorithm:** `ml/src/training/train_failure.py` implements Logistic Regression, Random Forest, and XGBoost on Scania APS; threshold tuned against validation recall target 0.90; preprocessing medians fit from train. Feature engineering in `ml/src/data/feature_engineering.py` adds missingness and per-prefix aggregates to 170 anonymized APS fields.
- **Data/label:** official Scania heavy-truck APS data; 60,000 training rows (1,000 positive), 16,000 test rows (375 positive), 170 anonymized features plus class. `failure=1` means APS failure; `failure=0` means another component failure, not healthy. Files have no longitudinal IDs or timestamps (`data/README.md`; `ml/src/data/loaders.py`). Thus it is a narrow heavy-truck APS classification task, not a passenger-car failure prediction; it earns no car-domain validation credit.
- **Reported held-out metrics:** `ml/reports/figures/aps/output.md` reports test metrics after validation threshold selection: Logistic Regression threshold .473, precision .4733, recall .9200, F2 .7739; Random Forest threshold .170, precision .7189, recall .8933, F2 .8520; XGBoost threshold .048, precision .5805, recall .9227, F2 .8254. The file says official test evaluated once, but no independent audit established the exact run provenance. Do not equate accuracy near 99% with quality under severe imbalance.
- **Artifacts:** `logreg_aps.joblib`, `rf_aps.joblib`, `xgb_aps.joblib` exist. They are code artifacts with training output evidence; no model card or registry/version lock exists. `train_failure.py` uses random stratified train/validation splitting, which is acceptable for this row-level benchmark only as a baseline; absence of IDs means group leakage cannot be evaluated, and APS is not temporal.
- **Chaining:** trained independently from raw APS inputs. It does not consume an anomaly score or RUL/health score; no stage hand-off or shared joined labels.

### Pipeline integration — ❌ Not started for passenger cars/EVs

No raw-sample-to-all-stages implementation: predictor and backend `inference_service.py` are comment-only; anomaly and RUL stages absent; API prediction route is comment-only. Cannot provide 0/1 plus health score from one sample/window.

## Backend/API — 🟡 Partial

`backend/app/main.py` creates FastAPI, `/health`, CORS and SQLAlchemy lifespan. `backend/app/api/routes/users.py` implements authenticated `GET/PUT /api/v1/users/me`; Firebase identity dependency is in `backend/app/api/deps.py`, user persistence in SQLAlchemy models/migration. `backend/app/api/routes/predictions.py`, `reports.py`, `telemetry.py`, `vehicles.py`, plus `backend/app/services/inference_service.py`, are each one-line comments. Thus the API does **not** load the ML bundles or offer vehicle/prediction endpoints. Tests exist under `backend/tests/`; their existence does not prove a current pass. Docker compose and CI configs exist, but no Dockerfile found in the current file inventory.

## Android app (`mobile/`) — 🟡 Partial

- **Framework:** Expo SDK / React Native / TypeScript with Expo Router (`mobile/package.json`, `mobile/src/app/`). `mobile/AGENTS.md` and app tree indicate Android focus; package supports iOS/web too.
- **Screens/navigation:** authentication welcome/login/email verification; main tabs Home, Vehicles, Insights, Account; dashboard and detail routes for vehicle, sensor, insight, report, and add/edit vehicle (`mobile/src/app/`).
- **Data:** `mobile/src/store/vehicleDataStore.tsx` directly instantiates `createDemoProvider`; `mobile/src/demo/provider.ts` uses deterministic fixtures and session-only state. No real backend vehicle or prediction provider. The UI explicitly labels prototype scenarios and unavailable/no-data states (`mobile/src/app/(main)/(tabs)/home.tsx`, `mobile/src/components/vehicle-health/data-state.tsx`).
- **Auth/API:** Firebase client auth and profile API client exist; profile sync only. `mobile/src/api/vehicle-data-provider.ts` defines a future abstraction but no production adapter. `mobile/.env.example` has API URL/Google client settings; `google-services.json` exists locally but config risk warrants normal secret review.
- **Build:** CI config runs type check/Jest; no independent Android build or physical-device validation was performed for this audit. PR #50 claims its own branch CI pass and physical visual acceptance pending, but is not merged/current `main`.

## Tests, CI, containers, docs, tracking

- **Tests:** test source exists in `ml/tests`, `backend/tests`, `mobile/tests`, and `simulator/tests`. `data/README.md` claims prior `pytest ml/tests -q` passed 37 tests and Ruff checks, but says this did not validate scientific mappings. No tests were run for this read-only audit (per task guardrail).
- **CI:** `.github/workflows/{ml,backend,frontend,mobile}-ci.yml` and Vercel/deploy workflows exist. Workflow definitions install dependencies and run lint/test/type-check. Presence is verified; latest run state not checked beyond GitHub PR body claims for #50.
- **Containers:** root `docker-compose.yml` and `docker-compose.dev.yml`; no Dockerfile located. Runtime readiness not verified.
- **Docs:** root README is not treated as truth. `data/README.md` is a detailed current inventory/audit but contains stale statements about loader absence relative to current loader source. `backend/README.md`, `mobile/README.md`, diagrams and website exist.
- **Tracking/versioning:** `mlflow` is listed in `ml/requirements.txt`, but `ml/src/training/mlflow_utils.py` is one comment and no MLflow runs found. No artifact registry/model version policy.

## Issues and PR map

GitHub public API was queried on 2026-11-13. Issue state is GitHub state; PRs marked “closed, unmerged” were abandoned/closed without merge, not shipped. PR #50 is open and not present in local `main`. All records mapped to the milestones in [scope.md](scope.md).

### Issues

| Issue | State | Title | Milestone / finding |
|---|---|---|---|
| #1 | closed | Basic Project Requirements | M1/M8; initial scope |
| #2 | closed | README.md | M8 docs; README not reliable source |
| #3 | closed | RAW DATA | M1; initial AI4I, NASA, vehicle/OBD data acquisition |
| #6 | closed | Data flow architecture | M5/M6; PR #21 closed unmerged, author said generated/unreviewed |
| #7 | open | Project discussion | M1/M6/M7; DB, mobile scope and architecture unresolved |
| #8 | closed | Data pre-processing | M1/M2/M3/M4; remains incomplete despite closure |
| #9 | closed | data loaders functions | M1; PR #11 merged, but old AI4I/C-MAPSS mappings later deemed wrong |
| #10 | closed | Premium frontend dashboard start | Website/deploy work, outside target Android app; PR #20 Vercel check merged, #19 dashboard closed unmerged |
| #16 | closed | Data pre-processing | M1/M2/M3/M4; checklist remains unchecked in description; PR #22 implemented shared preprocessing, not all dataset-specific validation |
| #17 | open | Feature engineering | M2–M4; unresolved |
| #18 | open | Data pipe-line | M5; unresolved |
| #25 | open | basic set-up of mobile application | M7; stale checklist, basic setup actually merged in #24; #45 later builds UI |
| #30 | open | EDA for all the datasets | M1–M4; unresolved broad task |
| #31 | closed | EDA for ai4i dataset | M1/M4; PR #37 merged, industrial dataset not automotive |
| #32 | open | EDA for cmapss dataset | M1/M3; aircraft RUL benchmark, not automotive |
| #33 | open | EDA for simulated dataset | M1/M2; unresolved; simulator exists but not evidence of data suitability |
| #34 | closed | Feature engineering for failure classification model | M4; PR #39 merged against AI4I; scope was later superseded |
| #35 | open | Feature engineering for RUL_score model | M3; unresolved |
| #36 | open | Feature engineering for anomaly detection model | M2; unresolved |
| #40 | open | Model training | M2–M4; unresolved umbrella task |
| #41 | closed | train failure classification model | M4; PR #44 closed unmerged; later current APS training exists in #48 branch/work but this issue is not a robust acceptance record |
| #42 | open | train anomly detection model | M2; unresolved in current `main` |
| #43 | open | train RUL score model | M3; unresolved in current `main` |

### Pull requests

| PR | State | Title | Milestone / result |
|---|---|---|---|
| #4 | merged | docs: add PRD-based project README | M8 docs; old plan |
| #5 | merged | Upload data | M1; initial data upload later audited/reorganized |
| #11 | merged | feat: loader functions | M1; old loaders existed but cross-domain mappings now flagged |
| #12 | merged | improved checks | M8 CI |
| #13 | closed, unmerged | Chore/update gitignore | M8; not shipped |
| #14 | closed, unmerged | docs: add DrivePulseAI product requirements document | M8; superseded/abandoned |
| #15 | closed, unmerged | fix: audit fixes | M8 frontend audit |
| #19 | closed, unmerged | feat(frontend): add premium dashboard foundation and Vercel setup | M8 website foundation not merged |
| #20 | merged | ci: check for vercel deployment | M8 deployment check |
| #21 | closed, unmerged | System Design | M5; author notes AI-generated and unreviewed |
| #22 | merged | Data Preprocessing | M1; shared preprocessing utility, not proof of dataset validity |
| #23 | merged | Update README | M8; README is contradicted by later data evidence |
| #24 | merged | mobile application basic setup | M7; scaffold only |
| #26 | merged | product website | M8; marketing website, not Android app |
| #27 | merged | Lint fixes | M8 |
| #28 | merged | mobile password and Google authentication | M7; authentication shipped |
| #29 | closed, unmerged | ignore local backend database | M8; not merged |
| #37 | merged | EDA for AI4I | M1/M4; industrial synthetic data, not vehicle failure validation |
| #38 | merged | Firebase auth and PostgreSQL profiles | M6/M7; profile endpoints only, no vehicle ML API |
| #39 | merged | features for AI4I | M4; later scope/data critique applies |
| #44 | closed, unmerged | model training for failure classification | M4; work not merged in this PR |
| #45 | merged | mobile vehicle-health UI with deterministic demo data | M7; polished prototype UI, local data only |
| #46 | closed, unmerged | EDA RUL score model | M3; no RUL baseline shipped by this PR |
| #47 | merged | Audit and organize datasets with provenance | M1; local data inventory/provenance documentation |
| #48 | closed, unmerged | EDA Scania APS classification | M4; proposal and report not merged in PR; current `main` nonetheless has APS training/artifacts as workspace content, but exact merge attribution is not established |
| #49 | closed, unmerged | Organize passenger-car datasets and define a feasible two-task ML plan | M1/M2/M3/M4; proposed scope reduction to two tasks, not shipped |
| #50 | open | Build Nissan Leaf ML baseline and recorded mobile replay | M2/M7; latest PR proposal, not merged/current `main`; PR says no verified fault labels, no backend inference, physical Android acceptance pending |

## Discrepancies and red flags

- **README claims vs code/data:** README describes Isolation Forest, XGBoost, RUL, SHAP and automotive mappings (`README.md`, lines 48–54, 135). Only APS failure model is executable/trained in current source; anomaly/RUL/XAI are comments. Data audit says AI4I is industrial/synthetic and C-MAPSS is aircraft, and records both as removed from current canonical folders (`data/README.md`). Do not say these datasets validate passenger-car health.
- **Data audit contradiction:** `data/README.md` says no dataset-specific KIT/carOBD loaders were found, but current `ml/src/data/loaders.py` contains `load_kit_obd` and `load_carobd`. Treat the loader source as current; the audit document is stale on this point. Conversely, source attribution and label limitations remain unresolved.
- **Model-target mismatch:** APS `neg` is failure of another component, not a healthy vehicle. Classifier is independent and has no RUL/anomaly inputs. It cannot be directly represented as generic 0=no failure.
- **Split/leakage:** APS has no vehicle IDs/time; sample independence cannot be verified. Training script imputes on train and keeps official test split. For DieselOBD, local data audit records 173 exact identical rows shared train/test, a direct evaluation contamination concern; the alleged dataset source, label semantics, and unit identities are unverified. Existing loader/preprocessing warnings in `data/README.md` identify whole-input scaling and inappropriate random/time splitting in older loader paths. APS `n_missing` is a strong failure-correlated feature; investigate source/collection mechanism and report ablation before interpreting deployment performance (`ml/src/data/feature_engineering.py`, APS EDA report).
- **Metrics:** APS metrics are present in `ml/reports/figures/aps/output.md` and correspond to official test set according to its text; model script tunes threshold on validation. No evidence these metrics were evaluated on training data. Still, results do not establish real-world generalization or chained performance.
- **Hardcoded paths/seeds:** APS script uses repo-derived default path and fixed seed 42; old mapping loaders reportedly use synthetic row IDs and whole-input stats (`data/README.md`). No seed configuration/reproducibility manifest across all stages.
- **Synthetic data:** AI4I family itself is synthetic and industrial; local derivative source/version/license is unverified per `data/README.md`. Simulator profiles generate synthetic signals (`simulator/src/`); these are not real vehicle faults.
- **Artifacts:** three APS bundles are saved, unlike anomaly/RUL. No `.pt`/`.onnx`, MLflow run, registry, or end-to-end inference bundle found.
- **Repository state:** many tracked paths were modified before audit began; reported current-tree conclusions may differ from pristine `9d79a59`. No source modifications were made by this audit.


## Dataset audit update — 2026-11-13

- **347-EV battery dataset:** 🟡 Three Figshare v1 archives are acquired unchanged under `data/automotive_prognostics/ev_fault_347/v1/raw/`; archive sizes match official Figshare metadata and SHA-256/inventory are recorded in `tasks_done.md`. CC BY 4.0 is verified. The paper verifies EV charging signals and vehicle-level abnormal/normal labels, but does not establish passenger-car body style. Local label files contain 348 IDs (55 abnormal/293 normal) versus the paper’s 347 (55/292). No exact future-failure horizon is documented, and complete PKL-to-label joins were not exhaustively validated. **Not approved for training in this cars-only project yet.**
- **20-car BAIC EU500 capacity dataset:** ⚠️ Rights remain unresolved. The public repository has an MIT LICENSE whose grant refers to software/documentation; no separate data license or data-specific permission was found. Keep raw archives quarantined from training and redistribution.
- **Model readiness:** no model training was performed. The 347-EV data may be considered for narrow vehicle-level battery abnormality work only after passenger-car status, count discrepancy and joins are clarified; it is not RUL data. The 20-car data cannot be used for capacity/SOH work until data rights are resolved.

## Change log

- 2026-11-13 — Step 0: recorded the reproducible environment baseline, test result, branch, seed convention, and dependency/tracking limitation.
