# DrivePulseAI: requirements and milestones

Audit baseline: checked-out `main` at `9d79a59` plus the current workspace contents on 2026-11-13. The intended product flow below follows the user-supplied project description; current implementation evidence is summarized in [progress.md](progress.md). GitHub records are linked directly in the issue/PR map there.

**Scope decision (2026-11-13): passenger cars only, including passenger EVs.** Heavy trucks, buses, aircraft, industrial machines, and component benchmarks from those domains are excluded from DrivePulseAI car performance claims. Scania Component X v3 and Scania APS may remain documented as separate external truck benchmarks, but are not car-model training data and cannot support a passenger-car claim. Evidence: user decision; Component X publisher describes Scania truck fleet data ([SND catalogue](https://researchdata.se/en/catalogue/dataset/2024-34)); APS source is Scania trucks (`data/README.md`).

## Project goal

DrivePulseAI should turn vehicle telemetry into a component-aware maintenance assessment that a driver or technician can understand and act on. Its intended ML flow is anomaly detection, then remaining useful life (RUL)/health estimation, then a binary failure decision, served through an API to an Android application. The user value is earlier, more understandable maintenance planning, with clear provenance and uncertainty rather than unsupported diagnosis. The product is decision support; the README says it does not control the vehicle (`README.md`, lines 135–136).

## System architecture and contracts

```text
Vehicle / sensor streams
  {vehicle_id, observed_at, component_id, signal_name:value, unit, source,
   optional DTC/maintenance event}
  → validation, unit normalization, missingness handling, temporal windowing
  → Stage 1: per-component Anomaly Detection
       input: a timestamped component window + component type + normalized signals
       output: {anomaly_score [0,1], anomaly_flag, component_id, window_end,
                contributing_features, model_version}
  → Stage 2: RUL / Health Score
       input: component signal window + Stage 1 output and its uncertainty
       output: {rul_value, rul_unit, health_score [0,100], uncertainty,
                component_id, model_version}
  → Stage 3: Failure Classification
       input: health_score, anomaly_score/flag, component identity, agreed signal features
       output: {failure_probability [0,1], failure_label 0|1, threshold,
                prediction_horizon, model_version}
  → API/backend: authenticated vehicle data and prediction/report endpoints
  → Android app: vehicle overview, health, sensor history, alerts, reports,
                 stale/offline/error states; consumes API response schema
```

The signal list is defined by the selected dataset and version; it must not pretend anonymous counters, industrial measurements, or aircraft sensor channels are named car sensors. Components without a measured signal/label mapping are out of scope until that mapping is evidenced. The above is the required product contract, not a description of current code: current routes other than user profile endpoints are one-line placeholders (`backend/app/api/routes/{predictions,reports,telemetry,vehicles}.py`); see [progress.md](progress.md).

## Functional requirements

### Data ingestion and preparation

- **FR-1** Ingest timestamped vehicle or component observations with source, unit, and stable vehicle/recording/component identifiers; reject malformed or provenance-unknown inputs unless explicitly marked exploratory. (The current raw OBD inventory lacks stable verified vehicle IDs; `data/README.md`, carOBD/KIT sections.)
- **FR-2** Preserve raw source bytes and source splits; produce versioned, deterministic preprocessing that handles units, missingness, ordering, duplicates, and component-specific features without fabricating labels. Fit all transforms on training data only. (`ml/src/data/preprocessing.py` exists; risks and current dataset-specific loader gaps in `data/README.md`.)
- **FR-3** Split by vehicle/component and time as appropriate before windowing; maintain official benchmark test splits untouched. Record dataset/version/checksum and split IDs.

### Anomaly Detection

- **FR-4** Fit or configure anomaly detectors using only the selected component’s available signals, with explicit per-component eligibility and missing-signal behavior.
- **FR-5** Return a stable schema containing anomaly score, flag/threshold, component, time window, model version, and interpretable top contributing signals. Calibrate the score/threshold on validation data and report false-alert rate/precision-recall where ground truth exists; otherwise label results unsupervised and do not call them confirmed faults.

### RUL / Health Score

- **FR-6** Predict RUL in a declared physical/operational unit from longitudinal degradation or time-to-event labels. Do not infer RUL from a one-time snapshot or map a non-automotive cycle count to kilometers/days.
- **FR-7** Define health score as a documented mapping of calibrated RUL and/or independently labeled condition to [0,100], including horizon, uncertainty, direction, and behavior when RUL is unavailable. Score semantics must be consistent across API and app.
- **FR-8** Report MAE/RMSE and a per-asset or per-vehicle held-out evaluation against the dataset’s official RUL/TTE target.

### Failure classification and orchestration

- **FR-9** Predict `failure_label ∈ {0,1}` and probability for a specified component and prediction horizon. Define label from a documented future failure event within horizon; preserve an explicit “unknown/not observed” state rather than treating it as healthy.
- **FR-10** At inference, Stage 3 must consume only upstream values/features available at prediction time. If health score contributes to the label definition, exclude it from primary classifier predictors or independently define/validate the label to avoid target leakage. Report threshold selection and precision, recall, PR-AUC/F1 or cost on untouched test data.
- **FR-11** Orchestrate stages in the exact order anomaly → RUL/health → failure, with schema validation, missing-stage behavior, model-version metadata, and a single end-to-end function that accepts a raw sample/window and returns the complete assessment.

### Backend/API

- **FR-12** Provide versioned, authenticated endpoints: `POST /api/v1/vehicles/{vehicle_id}/telemetry` to ingest observations; `GET /api/v1/vehicles` and `GET /api/v1/vehicles/{id}` for vehicle records; `POST /api/v1/vehicles/{id}/assessments` to run inference; `GET /api/v1/vehicles/{id}/assessments/latest`; `GET /api/v1/vehicles/{id}/reports/{report_id}`. Validate payloads and return documented schemas, timestamps, unit, confidence/uncertainty, provenance, model version, and safe errors. (These are target contracts; only profile routes are currently implemented.)
- **FR-13** Load pinned, validated model bundles at startup or through a controlled registry; readiness must fail clearly if required bundles are absent. Persist assessments and audit metadata where the app needs history.

### Android app (`mobile/`)

- **FR-14** Provide sign-in/account, vehicle list/add/edit/detail, overview, sensor history, insights/alerts, report detail, and data freshness/error states. Current designs exist in Expo Router routes under `mobile/src/app/` and are described in [progress.md](progress.md).
- **FR-15** Use an authenticated provider backed by the API contract, not demo fixtures, for production data. Clearly label demo/replay data; never derive telemetry or diagnosis from vehicle make/model. Cache last known data with its timestamp and mark it stale offline; permit viewing saved history and retrying sync. Never claim a cached assessment is current.

### Explainability, tracking, and versioning

- **FR-16** Show contributing inputs and limitations in explanations. If SHAP or deviation explanations are used, calculate against the deployed model and its actual feature names; distinguish statistical deviation from causal fault explanation. Current explanation modules are comments only (`ml/src/explainability/*.py`).
- **FR-17** Track dataset/version, code/config hash, seed, split, parameters, metrics, artifacts, and model version for every accepted experiment. Register/approve model bundles before API use. Current MLflow helper is a one-line comment (`ml/src/training/mlflow_utils.py`).

## Non-functional requirements

These are proposed acceptance targets, not current measured performance. **NFR-1 Latency:** local batch inference p95 ≤500 ms per vehicle assessment on documented hardware, excluding network; streaming ingestion must meet a separately agreed sample rate. **NFR-2 Quality:** no blanket accuracy target until labels/horizon are settled; minimum candidate gates are failure PR-AUC above prevalence and recall/precision meeting an agreed operating-cost target, RUL MAE/RMSE materially better than a per-unit baseline, and anomaly false alerts/hour reported. **NFR-3 Reproducibility:** fixed seeds, pinned dependencies, immutable dataset manifest, deterministic splits/transforms, recorded environment and command. **NFR-4 Testing:** unit/schema tests for each stage, leakage/split tests, API integration tests, mobile provider/state tests, and one end-to-end fixture; CI green. **NFR-5 Deployment:** reproducible local Docker compose and documented cloud deployment/secret setup; health/readiness checks and model artifact retrieval. **NFR-6 Security:** TLS in deployed environments, Firebase identity verification, owner-level authorization for vehicle records, secret isolation, no credentials in client bundle, safe logs and rate/size limits. **NFR-7 Mobile:** explicit stale/offline/error states, cached last result, retries, no fabricated offline predictions; Android build and physical-device acceptance documented.

## Milestones

Targets below are project acceptance criteria to decide, not claims that the current project already meets them.

| ID | Definition of done | Requirements | Measurable acceptance criteria |
|---|---|---|---|
| M1 Data decision and provenance | One selected domain/task plan, license/access notes, source files, schemas, IDs, splits and immutable manifest accepted | FR-1–3 | Every file has source/version/license/checksum; schema and label audit reproducible; no unresolved train/test identity overlap |
| M2 Validated anomaly baseline | Component eligibility and window schema implemented; baseline trained/evaluated on proper temporal or unit split | FR-2–5, FR-17 | Repeated run gives same result; report false-alert rate and, if labeled, PR-AUC/recall; no unsupported fault claims |
| M3 RUL/health baseline | Longitudinal target and score mapping documented and trained | FR-2–3, FR-6–8, FR-17 | Held-out-unit RUL MAE/RMSE and baseline comparison published; score bounded [0,100] with uncertainty behavior tested |
| M4 Failure classifier | Label/horizon documented, classifier evaluated on untouched test | FR-2–3, FR-9–10, FR-17 | PR-AUC, precision, recall, F1/cost and threshold reported; no leakage; required operating point met after product owner sets values |
| M5 Chained inference | One raw schema sample runs three stages in mandated order | FR-4–11, FR-16–17 | Contract test verifies all outputs, order, missing-stage errors, versions and repeated deterministic inference |
| M6 API | Authenticated telemetry and assessment endpoints deployed locally and documented | FR-12–13, NFR-5–6 | OpenAPI schemas validate; tests cover success, auth, invalid inputs, missing model and database unavailable |
| M7 Android app | Android build connected to API with demo/real mode clearly separated | FR-14–15, NFR-7 | Build succeeds; physical-device walkthrough of sign-in, vehicle, assessment, history and offline stale mode passes |
| M8 Release quality | Reproducible end-to-end demo, quality evidence, docs and CI/deployment complete | FR-16–17, NFR-1–7 | CI green; inference p95 measured; model/data cards and setup docs complete; no hardcoded secrets; end-to-end test passes |

## Assumptions and open questions

1. The product scope is passenger cars, including passenger EVs. Decide whether the first supported subsystem is combustion/powertrain OBD or EV traction battery; truck/bus datasets are excluded from car claims.
2. Choose named car subsystem(s) and source signals/failure events. Component X and APS are truck data, so they cannot resolve passenger-car labels.
3. Define RUL unit and score semantics: cycles, engine operating time, distance, time to service, or calibrated health percentage; establish a real label source.
4. Define failure horizon, positive/negative/unknown semantics, and whether negative means no failure observed within horizon. Scania APS negatives are other-component failures, not healthy vehicles, and APS is truck-only (`data/README.md`).
5. Decide whether the three-stage chain is a hard production architecture or a staged research demonstration. Stage 3 must not get a synthetic proxy label derived from Stage 2 and then be presented as independent prediction.
6. Set quantitative operating targets and latency hardware only after choosing the deployment context.
7. README drift: root README describes AI4I/C-MAPSS mapped to automotive equivalents and three models as a platform (`README.md`, lines 48–54, 135); current data audit rejects cross-domain column relabeling and notes AI4I/C-MAPSS removed from canonical data (`data/README.md`). PR #49 proposed reducing the original three-task plan to a feasible two-task plan; PR #50 proposes a Nissan Leaf battery anomaly/replay scope. The user decision now resolves the vehicle domain to passenger cars/EVs; the subsystem and label source remain open.

## Execution record note

No scope contract was changed during PR-readiness verification. The current contract remains passenger cars/passenger EVs only, with the three-stage chain gated until a valid car/EV RUL or time-to-event source is acquired. The current PR objective is dataset collection/provenance, validation, and safe loader updates—not model training. Local verification found no backend/mobile changes and 43 ML tests passed; the PR itself could not be created because GitHub credentials/CLI access were unavailable (recorded in `tasks_done.md`).

## Change log

- 2026-11-13 — Scope frozen to passenger cars/passenger EVs; truck and surrogate datasets excluded from car claims.
- 2026-11-13 — PR-readiness verification recorded without changing functional requirements or model contracts.
- 2026-11-13 — Clarified that this PR prioritizes dataset verification and loader updates; model training remains out of scope.
