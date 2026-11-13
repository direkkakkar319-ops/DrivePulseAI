# DrivePulseAI: remaining work and recommended order

This is the gap between the target in [scope.md](scope.md) and the checked-out implementation audited in [progress.md](progress.md). Scope is now **passenger cars and passenger EVs only**. Estimates assume one student developer part-time (roughly 10–15 hours/week) and access to a usable machine; dataset acquisition/permissions can add calendar delay.

## Step 0 update

The Step 0 gate passed in the existing repository `.venv`: 41 ML tests pass. Use `./.venv/bin/python` for the workflow. The system Python is missing the ML dependencies, and MLflow is listed but not installed; installing or activating a different environment is a setup dependency before any MLflow-backed experiment. The global seed convention is 42 (`ml/src/reproducibility.py`).

## Step 1 update

The Step 1 gate failed for the intended chain. Validation evidence is in `ml/reports/data_validation/step1.json`. KIT can support only unsupervised anomaly exploration; carOBD requires provenance/schema work; DieselOBD has unresolved semantics and cross-split duplicates; APS and Component X are truck-only; the 20-car source lacks cleared data rights and independent EOL; the 347-EV source lacks confirmed passenger-car body type, complete joins, an explained count discrepancy, and a dated horizon. No RUL or forward car-failure model may start yet.

## Gap analysis

| Component | Remaining work | Size / effort |
|---|---|---:|
| Scope/data decision | Domain frozen to passenger cars/EVs; choose initial subsystem and intended product claim; reconcile PR #49 two-task proposal and PR #50 battery anomaly demo | S–M, 1–2 days |
| Dataset acquisition/governance | Resolve 347-EV body style, 347/348 label discrepancy, full sample joins and horizon; get explicit 20-car data rights; find verified car RUL/event labels. Component X v3 is truck-only and excluded. | L, 5–10 days plus external response delay |
| Preprocessing | Rewrite/validate schema-specific loaders, time/ID semantics, windowing, train-only imputation/scaling, trip/asset split protocols; deprecate cross-domain aliases | L, 4–7 days |
| Anomaly | Implement component/vehicle anomaly pipeline, calibration and metrics; use KIT/verified Nissan Leaf where suitable; record unsupervised limitation | M, 3–5 days |
| RUL / health | Do not model on 20-car data until data rights are granted; if resolved, choose capacity/SOH forecasting versus true EOL-based RUL. Obtain independent EOL labels for RUL and evaluate by held-out vehicle. | L, 5–8 days after rights/data decision |
| Failure classification | Hold 347-EV data until car body type, count discrepancy, complete label joins and cutoff/horizon are clarified; then decide if narrow vehicle-level abnormality classification is valid. Obtain dated car failure events for forward-horizon claims. | L, 5–8 days after clarification |
| Chained inference | Freeze stage contracts, train with pipeline-generated out-of-fold upstream predictions, orchestrate, version and test end to end | L, 5–8 days |
| Backend/API | Implement telemetry, vehicles and assessment CRUD/inference endpoints; persist result; authz; error/readiness behavior; integration tests | L, 5–8 days |
| Mobile | Implement production API provider, auth token integration, history/assessment refresh, offline cache/staleness, test on Android device | L, 5–8 days |
| Release quality | CI data/model protocol checks, deployment, monitoring, model/data cards and docs; benchmark latency on target | M–L, 4–7 days |

**Overall remaining: about 80%** by the progress rubric. **Realistic effort: 35–55 part-time workdays (roughly 7–12 weeks at 10–15 h/week)**, with dataset access/cleaning and scope decisions the main source of calendar uncertainty. This is not a precision schedule; the chained model may require a revised scope if no aligned automotive labels can be obtained.

## Next three steps

1. **Choose the Step 2 dataset strategy.** Confirm the recommended per-stage passenger-car/EV strategy versus waiting for one unified source. Done when the strategy, accepted claims and download candidates are recorded in `datasets.md`. (S, 30 minutes.)
2. **Resolve dataset eligibility before model work.** Request confirmation from the 347-EV publisher/authors about passenger-car body class, why local release labels enumerate 348 vehicles versus 347 in the paper, how PKL `car` IDs join label CSVs, and how an eligible prediction cutoff/horizon is defined. Separately obtain an explicit data-specific license/permission for the 20-car archive. Done when written evidence is recorded or the candidate is rejected. (S effort, external response time unknown.)
3. **Complete gated validation or reject the candidate.** If written answers/permission arrive, validate all vehicle/sample joins with safe parsing, record schema and group split, and decide if the labels support the claim. Otherwise keep data quarantined and source a licensed passenger-car dataset. Done when an explicit keep/reject decision is documented. (M–L, 2–5 days plus access.)
4. **Freeze the task contract, then start a baseline.** Select only a cleared dataset/label, define component/window schema, target horizon, vehicle-level split, and leakage exclusions. Touch ML loaders/preprocessing only after the data gate passes. Done when held-out assets and a baseline metric can be reproduced from a documented config. (L, 4–7 days.)

## Phased plan

### Phase A — scope and data contract
Passenger-car/EV domain is settled. Select the first supported subsystem, verify car/EV dataset access and terms, then define RUL unit, failure horizon, health-score mapping, signal eligibility, stage handoff and unsupported-data behavior. Reconcile PR #49 two-task proposal and PR #50 Leaf battery anomaly/replay with the three-stage intent.

### Phase B — data foundation and baselines
Implement dataset-specific loaders and a source manifest. Use KIT for exploratory passenger-car anomaly detection, clearly limited to the Seat Leon telemetry available. Use only a verified car/EV source for RUL and failure labels. Keep Component X and APS in separate truck benchmark records; they cannot validate car results. Establish official and held-out-vehicle evaluation.

### Phase C — model contracts and chain
Train/evaluate anomaly and RUL components; generate out-of-fold Stage 1/2 values for training Stage 3 to prevent optimistic upstream predictions. Evaluate the complete chain on held-out units using the same upstream inference path used in deployment. Start with a simple calibrated baseline. Add health mapping only after product semantics are approved.

### Phase D — backend integration
Implement typed FastAPI schemas and authenticated vehicle/telemetry/assessment endpoints; load pinned artifacts; return model/data versions, prediction timestamp, units, uncertainty and explanation. Persist history and add request validation/authz and failure modes.

### Phase E — Android connection
Replace `createDemoProvider` at a clear configuration boundary with a real API provider; preserve demo mode as an explicit preview. Add refresh/history and stale/offline cache. Confirm auth token handling, permissions, and phone/emulator API reachability. Walk through all screens on Android.

### Phase F — release gate
Run unit, data protocol, model, API, end-to-end and mobile checks in CI; deploy reproducibly; report latency and limitations. Publish dataset/model cards and a demo whose wording distinguishes observed telemetry, anomaly, component RUL and failure probability.

## Blockers and dependencies

- **True car RUL cannot proceed credibly without passenger-car/EV end-of-life/time-to-event labels.** A 20-car EV longitudinal capacity source is now acquired and audited and can support capacity/SOH trajectory work, but not observed RUL to failure. Component X v3 is heavy-truck data and excluded.
- **A car-only three-stage chain is blocked by aligned labels.** KIT/carOBD have car time series but no mechanical fault/RUL labels. Component X and APS have truck labels and are out of domain. Separate datasets can support separate benchmarks, but not a joined car chain.
- **Production failure-risk claims are blocked until the prediction horizon, event definition, and negative/right-censoring semantics are settled.** APS `neg` means another component failed, not healthy.
- **Mobile/API completion depends on model and response contracts**, but the UI’s navigation and demo flow can be built independently. A production health score should not be represented from the current mock fixtures as measured vehicle health.

## Pipeline design risks and decisions

### Feasibility and label origins
Anomaly can be explored on unlabeled passenger-car telemetry (KIT) to score statistical novelty, but that does not train “fault detected.” Car RUL needs repeated degradation and a defensible end-of-life/time-to-event label from passenger cars or passenger EVs. The acquired 20-car dataset has derived per-charge capacity targets but no independent EOL event, and its data reuse rights are unresolved. The 347-EV source has CC BY 4.0 and weak vehicle-level abnormality labels, but passenger-car body type, the paper/release vehicle-count discrepancy (347 versus 348), exhaustive joins, and horizon semantics remain unresolved. Component X has verified time-to-event data, but it is heavy-truck data and cannot support this project’s car claims. Battery-cycle data may support battery capacity/SOH prediction, not generic vehicle component RUL. Failure classification needs an observed future passenger-car subsystem failure within a defined horizon. Scania APS labels are also truck-only and cross-sectional.

### If no single source covers all stages

| Option | Benefits | Costs and limits | Recommended use |
|---|---|---|---|
| One unified real passenger-car/EV dataset | Common vehicles, units and event timelines; most defensible for chaining | Such public datasets with aligned anomaly, RUL and failure labels are scarce; each target must be verified | Preferred if found and labels are genuinely aligned |
| Join per-stage car/EV datasets through a fixed schema | Lets separate passenger-car sources support individual tasks | Different vehicles/sensors/targets cannot be joined as if same samples; cannot claim end-to-end empirical validation | Separate benchmark cards; validate handoff only with a clearly marked interface simulation |
| Synthetic or simulator-derived unified data | Enables contract, orchestration and mobile demo testing with known injected events | Artificial distributions/labels; no external validity; easy leakage if target is generated from the same score | Use only for software integration tests and explicitly synthetic demo |
| Transfer from surrogate domains (C-MAPSS, XJTU-SY, NASA battery, Component X) | Mature run-to-failure labels and method debugging | Aircraft/bench bearing/cell/heavy-truck domain mismatch; cannot support passenger-car performance claims by sensor renaming | Keep outside car model claims; use only as explicitly separate research benchmark |

### Failure-label leakage
If `failure=1` is created by thresholding predicted RUL/health and Stage 3 receives that same score, the classifier merely learns the label-generation rule. That can be a transparent policy layer, but it is not independent predictive evidence. For a learned failure classifier, define target as an independently observed future event within horizon H; train with time-indexed covariates available at cutoff and censoring handled explicitly. Exclude target-derived fields and post-event readings. Generate upstream training features out of fold, tune thresholds on validation only, and evaluate the whole chain once on held-out units/time. If the project intentionally uses `health_score < threshold`, call it a deterministic rule, not a separately validated classifier.

### Per-part anomaly and interface
Per-part detection is appropriate only when signals and labels correspond to that part. Establish a component registry with supported signal names, units and missingness. The interface should be a versioned fixed schema rather than loosely named vectors: `vehicle_id`, `component_id`, `observed_at`, `window_start/end`, `feature_schema_version`, `features: {name: {value, unit}}`, `anomaly_score`, `anomaly_flag`, `anomaly_model_version`, optional confidence/feature contributions. RUL and classifier stages consume this schema plus their prior-stage outputs. Reject unsupported components rather than mapping arbitrary signals to “engine/clutch/brakes.”

## Mobile plan

The current app already has navigation, auth/profile integration, vehicle forms, sensor/detail/report/insight screens, and deterministic demo state (see [progress.md](progress.md)). Remaining work: add a real API-backed `VehicleDataProvider`; bind Firebase bearer token to vehicle/assessment endpoints; define loading/error/empty/stale state semantics and last-known cache; display timestamp, source and model version; distinguish demo vs live; test offline refresh and stale state; verify Android debug/release builds and Firebase signing configuration; run device acceptance for add/select vehicle, view assessment/history, sign out and retry. The open PR #50 proposes a replay path but is not merged into current `main` and explicitly says backend inference is absent.

## Whole-project definition of done

- [ ] Product domain, data license, labels, prediction horizon, health-score definition and known limitations approved and documented.
- [ ] Every training source has provenance/version/license/checksum and reproducible schema/split inventory.
- [ ] Anomaly, RUL/health and failure stages have separate valid training labels/protocols and held-out metrics; unsupported claims removed.
- [ ] No target leakage, post-event features, identity overlap or train/test contamination in accepted evaluation.
- [ ] One raw sample/window can traverse anomaly → RUL/health → failure and returns schema-valid outputs, uncertainty and version metadata.
- [ ] API authenticates and authorizes users, stores telemetry/assessments, and provides documented vehicle/assessment endpoints.
- [ ] Android app uses the API for real mode, labels demo mode, displays freshness and supports offline viewing/retry without fabricating predictions.
- [ ] Unit/data/model/API/mobile/end-to-end tests and CI pass; reproducible deployment and latency are documented.
- [ ] User-facing reports explain what is observed, predicted, simulated, and not established.

## Requests to backend/mobile

No request from Step 0. Backend and mobile were not modified.

Step 1 adds no backend/mobile request; model output contracts remain unchanged because no model was trained.

## Change log

- 2026-11-13 — Step 0: recorded the environment gate, interpreter requirement, seed convention, and no backend/mobile requests.
- 2026-11-13 — Step 1: recorded the failed data gate, validation evidence, strategy decision point, and updated next steps.
