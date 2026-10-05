# Passenger-car ML plan

The agreed scope is **two experimental ML tasks**, not three deployed models:

1. Detect unusual sensor behaviour relative to a chosen reference population.
2. Distinguish the recorded healthy condition from the recorded intake-related condition.

RUL, general passenger-car healthy/faulty diagnosis and broad mechanical-fault diagnosis are deferred. The available data does not support those claims. Telemetry display and diagnostic-code assistance remain separate application capabilities, not additional ML models.

This README records the plan discussed with the user. It does not announce implemented passenger-car models. Existing loaders, truck classification code, notebooks and reports remain; their presence does not establish the new scope's performance. Dataset organization and limitations are in [data/README.md](../data/README.md).

## Why the scope changed

Scania APS is a heavy-truck APS-versus-other-failures benchmark, not healthy/faulty passenger-car data. Its `neg` class contains other failures. Industrial AI4I and aircraft C-MAPSS cannot establish passenger-car classification or remaining-life accuracy merely by renaming their features.

DieselOBD is closer to passenger-car OBD inputs, but its verified workbooks contain 173 shared train/test sensor patterns, 5,487 all-zero P-code rows and no vehicle/session IDs or timestamps. `P0000` and `Mode` need an explicit dictionary. No active DTCs cannot certify mechanical health. It remains a candidate, not a validated training/evaluation source.

Edge Impulse provides clearer `healthy` and `airleak_nox` labels, but only two condition-specific source recordings. Its many samples are not many independent cars. KIT provides real passenger-car telemetry, but no verified mechanical-health labels. More complex algorithms cannot make those missing labels or independent sessions appear.

## Task 1: unusual-behaviour detection

**Question:** Does this sensor observation/window deviate from the selected reference behaviour?

**Data:** `data/passenger_cars/kit_obd/` for telemetry exploration, and the labeled healthy Edge Impulse recording for a narrow reference-condition experiment. Neither source establishes a representative healthy population across passenger cars. Do not call all KIT recordings healthy or treat road-condition names as faults.

**Models to compare:** a simple statistical baseline, then Isolation Forest. These are candidate approaches; the statistical formula, feature set and threshold are not yet decided. Choose one model for the prototype after evaluation. An unusual-pattern score is not a fault diagnosis.

**Preparation and evaluation:** inspect schema, units, missing values, timing, operating conditions and duplicate/near-duplicate patterns. Preserve recording boundaries; investigate KIT's backward timestamp jumps. Do not invent missing NOx or voltage readings, vehicle identities, mechanical labels or sampling continuity. Split related observations by verified recording/session/vehicle groups before constructing windows. Fit learned preprocessing on training only.

Without confirmed mechanical labels, KIT cannot establish fault-detection recall. Edge Impulse can illustrate unusual behaviour under its recorded condition, but does not establish new-car or independent-session performance. Independent healthy/faulty recordings are required for that evaluation.

## Task 2: narrow condition classification

**Question:** Can the available measurements distinguish the recorded healthy condition from the recorded intake-related condition?

**Data:** `data/passenger_cars/edge_impulse_airleak/`. Its manifest records labels, sample IDs, original names and supplied train/test membership. The four channels are RPM, pedal input, MAF and NOx. Read the manifest together with the JSON samples; do not ingest the original source CSVs again as additional examples.

**Models to compare:** Logistic Regression as a baseline, then Random Forest. Choose one after evaluation; the plan does not commit to either as the final model. Features/window summaries, hyperparameters and probability threshold are still undecided.

Predictor inputs must exclude targets and identifying metadata. The output concerns the recorded condition, not every possible component fault. Investigate whether RPM/pedal/operating-regime differences explain class separation rather than the induced condition. The supplied split has no exact sensor overlap under the saved check, but draws from the same two recordings. It cannot independently validate performance across cars.

Use precision, recall and the confusion matrix to explain mistakes; choose any decision threshold on validation rather than test data. The acceptance targets and costs are not decided. Training learns from training data, validation guides model/threshold choices, and an independent test set evaluates the frozen choice. Current recordings cannot provide a credible held-out-session comparison of both classes; any demonstration must disclose that limitation instead of pretending a random row split solves it.

## Ensemble and neural-network decisions

Start with classical models. Random Forest already combines many trees; Isolation Forest also uses an ensemble of trees. The two tasks answer different questions and are not automatically one ensemble when shown in the same app.

Voting/stacking is deferred until individual models show complementary improvements on independent validation data. No combined health-score formula or classifier/anomaly fusion rule has been agreed.

Neural networks are not required initially. A small 1D CNN or GRU for sequence comparisons and an autoencoder for anomaly comparisons were discussed only as possible later experiments. No neural architecture, network size, training schedule or adoption decision has been agreed. More independent data must precede claims that these improve generalization.

## Agreed procedure

1. Audit selected source data, schemas, units, missingness, timing, labels and operating conditions.
2. Investigate exact/near duplicates and split contamination; record what each check proves and cannot prove.
3. Establish trustworthy grouping/splits before overlapping windows. Preserve original datasets and supplied partitions; do not silently recombine official test data.
4. Explore training data: imbalance, distributions, correlations, constants and outliers. Do not automatically delete unusual readings that may carry relevant information.
5. Select preprocessing using training/validation. Fit imputation, scaling or feature selection on training only and reuse the fitted transformations for evaluation; never fabricate targets.
6. Compare the agreed simple baseline and candidate model for each task. Avoid heavy optimization during initial EDA.
7. Use independent evaluation when the needed data exists. Do not report demonstration scores as passenger-car fault accuracy, or tune against the test set.
8. Preserve reproducible analyses, split membership, source checksums and clearly bounded reports. Product inference integration follows a separately agreed implementation phase.

These are planned procedures. No new passenger-car pipeline was implemented or trained as part of the folder/documentation change.

## Data needed before broader claims

- Multiple independent passenger cars and recording sessions, with reliable vehicle/session IDs and timestamps.
- OBD signals our app can actually collect, with documented units and sensor availability.
- Confirmed fault diagnoses and documented healthy checks, with comparable operating conditions across labels.
- Original per-vehicle recordings and label/split definitions for DieselOBD, including `P0000`, `Mode` and all-zero labels.
- More independent labeled recordings for the Edge Impulse condition task; repeated windows from the same recordings do not fill this gap.

No suitable passenger-car time-to-failure dataset has been verified for this project. RUL requires longitudinal observations linked to failures/replacements; it remains outside the current two-task plan. Truck Component X and aircraft C-MAPSS remain separate research options, not substitutes for passenger-car validation.

## Decisions still open

Final features and sensor subset; statistical anomaly baseline definition; window size; split proportions; hyperparameters; operating-condition treatment; probability calibration; alert thresholds; acceptable precision/recall; ensemble adoption; neural-network adoption; deployment performance targets; and any health-score/maintenance-action formula.

The existing Scania training script is a retained truck benchmark. Its data default now points to `data/deferred/scania_aps/raw/`; its algorithm is unchanged. Existing EDA notebooks/reports were preserved, including any legacy defaults. None should be presented as the passenger-car models described above.
