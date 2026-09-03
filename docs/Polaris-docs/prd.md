# Product Requirements Document (PRD)

## Product Goal

Turn simulated and public time-series telemetry into a reliable, explainable, and reviewable vehicle-health assessment that helps drivers, technicians, fleet operators, and ML engineers identify abnormal behaviour and prioritize maintenance.

DrivePulseAI is an educational engineering and machine-learning prototype. It provides risk and inspection guidance; it is not a certified diagnostic system and must not be presented as a replacement for a qualified technician.

## Feature Priorities

| Feature | Priority |
|---|---|
| Generate reproducible vehicle telemetry | Must |
| Validate and store telemetry | Must |
| Display live telemetry | Must |
| Detect deterministic threshold violations | Must |
| Detect multivariate anomalies | Must |
| Estimate failure or maintenance risk | Must |
| Calculate a transparent vehicle health score | Must |
| Explain predictions and alerts with evidence | Must |
| Show model version, confidence, and limitations | Must |
| Manage alert lifecycle | Must |
| Provide vehicle and fleet dashboard views | Must |
| Generate technician maintenance reports | Should |
| Monitor model quality and evaluation metrics | Should |
| Support reproducible training and model tracking | Should |
| Estimate remaining useful life (RUL) | Could |
| Ingest consented OBD-II telemetry | Won't for MVP |
| Issue vehicle-control commands or certain diagnoses | Won't |

## User Stories

### US-001 Generate Telemetry

As a developer or demonstrator, I want to generate repeatable normal, degraded, and fault scenarios so that I can test the complete platform without requiring access to a real vehicle.

**Acceptance:** The simulator emits timestamped telemetry containing a synthetic vehicle ID, speed, engine RPM, coolant temperature, battery voltage, engine load, vibration, scenario label, and `source: "simulated"`. A fixed seed produces a repeatable scenario, and injected faults are recorded explicitly.

### US-002 Ingest and Validate Telemetry

As a platform operator, I want incoming readings validated before they enter the system so that downstream health assessments are based on usable data.

**Acceptance:** The API validates required fields, types, units, timestamps, identifiers, and plausible ranges. Invalid or duplicate readings are rejected or quarantined with a clear reason, while valid readings are stored and associated with the correct vehicle.

### US-003 Monitor Live Vehicle Conditions

As a driver or fleet operator, I want to see current sensor readings and recent trends so that I can understand a vehicle's operating condition.

**Acceptance:** The dashboard displays the latest telemetry and time-series charts for a selected vehicle. In the demo environment, at least 95% of simulator events appear in the UI within three seconds of generation. Connection loss and stale data are visibly indicated.

### US-004 Review Known Threshold Violations

As a technician, I want unsafe or unusual readings checked against documented rules so that known operating problems are easy to recognize.

**Acceptance:** Each threshold alert identifies the affected sensor, observed value, configured threshold, timestamp, severity, and rule version. Thresholds and units are documented and testable.

### US-005 Detect Abnormal Behaviour

As a fleet operator, I want unusual combinations of readings detected even when no single threshold is crossed so that emerging issues can be investigated early.

**Acceptance:** The anomaly detector returns an anomaly score and status using a versioned feature pipeline and model. The result includes the readings or deviations that provide supporting evidence, and its limitations are available to the user.

### US-006 Estimate Maintenance Risk

As a fleet operator, I want a clearly defined failure or maintenance-risk probability so that I can prioritize vehicles for inspection.

**Acceptance:** The system returns a bounded risk score or probability, prediction timestamp, prediction horizon or target definition, model version, and confidence or uncertainty indicator. The UI describes the result as risk guidance and never as a certain diagnosis.

### US-007 Understand the Health Score

As a driver, I want a simple vehicle health score with visible deductions so that I can understand the overall condition without interpreting raw model output.

**Acceptance:** The system displays a deterministic 0-100 score, its update time, status band, and component-level contributions. Given identical validated inputs and configuration, the same score is produced. No hidden random factors affect the score.

### US-008 Understand an Alert

As a driver or technician, I want every alert explained in plain language so that I can decide whether inspection is appropriate.

**Acceptance:** Every visible alert includes severity, supporting readings, expected or baseline values, time of occurrence, source (rule or model), model/rule version, and a safe recommended next step. Model-driven alerts expose feature contributions through SHAP or an equivalent method.

### US-009 Manage Alert Status

As a technician, I want to acknowledge, resolve, or dismiss an alert so that the fleet record reflects the investigation outcome.

**Acceptance:** Alerts support `NEW`, `ACKNOWLEDGED`, `RESOLVED`, and `DISMISSED` states. Each transition records the previous state, new state, timestamp, and actor or system source, and invalid transitions are rejected.

### US-010 View Fleet Priorities

As a fleet operator, I want a fleet-wide summary sorted by risk and alert severity so that I can focus on vehicles needing attention.

**Acceptance:** The fleet view shows each vehicle's latest health score, active-alert count, highest severity, most recent telemetry time, and data freshness. Users can select a vehicle to inspect its detailed evidence.

### US-011 Generate a Maintenance Report

As a technician, I want a reviewable maintenance report so that observations and evidence can be shared or retained.

**Acceptance:** A report includes vehicle ID, reporting period, health-score summary, relevant telemetry trends, alerts, risk results, evidence, model/rule versions, limitations, and technician notes. Missing data is called out rather than silently omitted.

### US-012 Evaluate Models

As an ML engineer, I want reproducible, component-level evaluation results so that I can compare models and detect weak or misleading performance.

**Acceptance:** Failure classification reports precision, recall, F1, PR-AUC, confusion matrix, and calibration. Anomaly and RUL models use task-appropriate metrics. Dataset version, feature version, split strategy, parameters, artifacts, and results are tracked, with time-aware or group-aware splitting used where applicable.

### US-013 Inspect Data and Model Limitations

As an ML engineer or reviewer, I want dataset provenance, leakage controls, error examples, and known limitations documented so that reported results can be interpreted responsibly.

**Acceptance:** Public, synthetic, and any future consented data remain distinguishable. Dataset source, licence, field mapping, preprocessing, split strategy, imbalance, domain mismatch, and known failure modes are documented. Benchmark performance is not represented as real-world automotive diagnostic performance.

## Product States

Telemetry processing:

`GENERATED/RECEIVED -> VALIDATING -> ACCEPTED -> STORED -> ANALYZED -> PUBLISHED`

Validation failure:

`VALIDATING -> REJECTED/QUARANTINED`

Prediction lifecycle:

`PENDING -> PROCESSING -> COMPLETED`

Prediction failure:

`PROCESSING -> FAILED`

Alert lifecycle:

`NEW -> ACKNOWLEDGED -> RESOLVED`

Alternative terminal path:

`NEW/ACKNOWLEDGED -> DISMISSED`

Telemetry freshness shown in the product:

`LIVE -> DELAYED -> STALE -> DISCONNECTED`

## Product Principles

- **Evidence before interpretation:** show the readings, thresholds, deviations, and feature contributions behind each conclusion.
- **Explicit uncertainty:** communicate confidence, limitations, data freshness, and failure states instead of implying certainty.
- **Rules and models have separate roles:** use deterministic rules for known conditions and ML for learned patterns, and identify the source of every alert.
- **Transparent scoring:** make health-score inputs and deductions visible, versioned, deterministic, and testable.
- **Reproducibility:** version datasets, features, rules, models, configurations, and evaluation results.
- **Data quality first:** validate schema, units, ranges, timestamps, duplicates, and source before inference.
- **Safe decision support:** recommend inspection or review; do not issue control commands or claim a confirmed diagnosis.
- **Privacy by design:** use synthetic identifiers by default, minimize personal data, and require consent and a separate review before real vehicle-data ingestion.
- **Honest evaluation:** prevent leakage, use defensible splits and metrics, and disclose benchmark-to-automotive domain mismatch.
- **Observable operation:** surface service, stream, model, and data failures clearly enough for users and developers to investigate.
