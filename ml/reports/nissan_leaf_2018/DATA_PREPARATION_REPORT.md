# Nissan Leaf Phase 1 — Data preparation report

Purpose: document reproducible, conditional experimental datasets without training models or changing source telemetry. Run ID: `d7e9e32e1ff2981a`. Raw data, preprocessing artifacts and prepared outputs are distinct.

## 1. Source datasets and provenance

Primary input: `data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv` (2,322,105 rows, 92 columns). Comparison audit only: `data/nissan_leaf_2018/processed/Dataset_Preprocessed.csv` (1,918,299 rows, 32 columns). Both source hashes, workbook and archived source page are verified against [download_manifest.json](metadata/download_manifest.json). Source bytes are never written. Dataset published by Macao Polytechnic University, [official source](https://ubilab.mpu.edu.mo/data.html).

Existing [EDA](EDA_REPORT.md), [readiness assessment](ML_READINESS_REPORT.md), workbook dictionary and readiness inventory informed the policy. The workbook was read using the existing extraction utility before implementation. Raw is chosen because processed fields show unexplained changes and derived-formula disagreements. Raw also includes publisher-derived columns, which are not selected. No claim is made that all publisher processing is known or causal.

Both releases overlap in 1,886,696 exact timestamps. They are never pooled or used as independent train/test sources. No new download or physical ground truth was obtained. Licensing uncertainty remains.

## 2. Preparation architecture

`ml/src/nissan_leaf_preparation/` contains reusable quality, temporal, split, transformation, window, export and independent validation functions. `ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py` is the CLI. JSON configuration lives at `ml/notebooks/nissan_leaf_2018/config/preparation.json`.

CSV scans read 75,000 rows per chunk and carry one incomplete trip. Audit Parquet writes one trip per row group. Exact robust statistics load only retained training input columns; independent output validation reads a selected-column ledger, not the full 92-column source. No dense sliding-window tensors are duplicated: sequence indices reference existing feature rows. Output source/config/code/library fingerprints determine the run ID. Re-execution builds a separate temporary result and requires identical output hashes before reusing an existing run directory; incomplete runs are not published as complete.

## 3. Quality audit findings

| version | rows | flagged_rows_any_flag | no_row_flags | quality_eligible_rows | quality_excluded_rows |
| --- | --- | --- | --- | --- | --- |
| processed | 1918299 | 369507 | 1548792 | 1918296 | 3 |
| raw | 2322105 | 675310 | 1646795 | 2050302 | 271803 |

Flags overlap; do not sum their counts as unique rows. `no_row_flags` means no configured row-level issue found, **not verified healthy**. Global unresolved current/ambient semantics apply even to rows without flags, so those channels are excluded from inputs altogether. Processed eligibility counts are audit-only hypothetical policy counts; no processed feature matrix is exported.

| flag | bit | category | meaning | raw_rows | processed_rows |
| --- | --- | --- | --- | --- | --- |
| missing_candidate | 1 | Missing | Candidate NaN; no silent fill | 0 | 0 |
| nonfinite_candidate | 2 | Invalid based on verified rules | Infinite measurement cannot be a finite physical reading | 0 | 0 |
| soc_domain | 4 | Invalid based on verified rules | SOC outside documented percentage domain [0,100]; may encode unavailable state, not a fault | 2040 | 0 |
| speed_negative | 8 | Suspicious | Negative speed magnitude/unavailable code unresolved | 266235 | 0 |
| voltage_review | 16 | Suspicious | Nonpositive or above review threshold; not a fault | 2141 | 3 |
| pack_sentinel | 32 | Unresolved | Pack reading near -1 may be unavailable or real; no conversion | 3850 | 0 |
| physical_temperature | 64 | Invalid based on verified rules | Temperature below absolute zero in documented Celsius channel | 0 | 0 |
| tire_zero_or_negative | 128 | Suspicious | Pressure code needs interpretation; excluded feature | 457168 | 222905 |
| odometer_decrease | 256 | Suspicious | Decrease within trip; not corrected | 202 | 321 |
| odometer_jump | 512 | Suspicious | Large short-interval jump; not corrected | 190 | 304 |
| soh_zero | 1024 | Unresolved | Reported zero health not treated as battery failure | 2853 | 0 |
| power_formula | 2048 | Suspicious | Stored power differs from V*I/1000; no replacement | 0 | 30057 |
| temperature_formula | 4096 | Suspicious | Stored mean differs from components; no replacement | 0 | 1395 |
| duplicate_timestamp | 8192 | Invalid based on verified rules | Ambiguous ordering for sequence use, not an invalid sensor reading | 0 | 0 |
| long_gap | 16384 | Suspicious | Start of new continuity segment | 15825 | 7984 |
| soh_missing | 32768 | Missing | SOH NaN retained; not a selected input | 2247 | 0 |
| irregular_interval | 65536 | Unresolved | Row interval outside 0.2–0.3s descriptive band; no resampling | 187435 | 130358 |

## 4. Cleaning policies

No numerical source corrections, outlier clipping, recomputation of stored fields or silent row deletion occur. All raw rows survive in `row_ledger.parquet` with original values, source row offsets, exported index, Trip, Timestamp, segment, split, flags and eligibility. Any raw row excluded from features remains inspectable there. Processed flagged rows are indexed separately against their unchanged CSV.

Selected-feature missing/infinite values, invalid SOC-domain values, negative speed, voltage review cases, narrow pack sentinel-band cases, impossible temperatures and duplicate timestamps are excluded under the configured policy. Flags on unselected tire pressure, odometer, SOH and derived fields remain contextual and do not independently remove usable feature rows. Retaining flagged data is intentional; flags are not fault labels. No statistical IQR outlier rule removes observations.

## 5. Missing-value handling

Every scanned candidate/context column has counts in [missingness.csv](tables/preparation/missingness.csv). Default policy: `exclude`. No forward fill, interpolation, temporal averaging or invented target values is used. The optional `training_median` policy fits medians only on eligible training rows and exports one missingness indicator per feature; the original missing measurements remain missing in the ledger. Imputed inputs would be computational substitutes, never newly measured observations. No median target imputation is implemented.

The actual run used no imputation. Raw SOH missingness is flagged independently despite SOH being excluded as an input. There is no blanket -1 replacement: negative torque may be valid; -1 in documented status codes can mean off.

## 6. Invalid and suspicious measurement policies

Verified-rule invalidity is limited to unrepresentable/nonfinite selected values, SOC outside its documented percentage domain, temperatures below absolute zero, or duplicate temporal keys unsuitable for sequence use. Invalid signal-domain values can still encode missingness rather than hardware faults.

Voltage threshold 500.0 V is an exploratory review screen, not a manufacturer limit. Nonpositive voltage and negative speed are suspicious/unresolved codes, not automatically confirmed sensor defects. Pack values in [-1.01, -0.99] °C are conservatively withheld as unresolved possible sentinel values; genuine readings in this band may also be excluded. This selection bias must be reviewed. Motor -40°C is not excluded merely because it is an extreme. Tire zeros, odometer decreases/jumps and raw zero SOH are flagged without correction. Power and mean-temperature formulas are audited with configured atol/rtol 1e-08/1e-08; formula consistency alone does not verify sensor truth.

No current sign flip, ambient temperature conversion, speculative pedal units or energy integration is performed.

## 7. Temporal segmentation

Microsecond epoch timestamps are parsed as UTC; original integers are preserved. Missing/unparseable timestamps, source time reversals or reused noncontiguous Trip IDs stop the pipeline for review rather than silently merging or sorting ambiguous journeys. Existing source rows are already ordered. Duplicate timestamps are flagged/excluded and break segments on both sides.

A new segment begins at every trip boundary and every gap >1.0 second. Justification: observed median interval 0.25s and p99 about 0.75s. The configurable [0.2, 0.3]s band is a descriptive irregularity flag only. Neither row cadence nor value-change frequency establishes sensor refresh frequency. Workbook channels have differing polling intervals, and pack update cadence is unknown. No interpolation across gaps occurs. Every segment's rows and duration are saved in [segments.csv](tables/preparation/segments.csv).

## 8. Chronological split strategy

Boundaries minimize deviation from requested [0.7, 0.15, 0.15] cumulative source-row fractions among whole-trip boundaries on different UTC dates with at least 90.5 seconds separation. The embargo covers lookback+horizon+tolerance. Trip interval overlaps or unavailable defensible boundaries stop preparation; no random fallback exists. Splits are chosen before feature filtering, without targets, so retained proportions need not equal 70/15/15.

| split | trips | source_rows | quality_excluded_rows | cross_split_repeat_exclusions | feature_rows | temperature_sequences | source_recorded_days | retained_recorded_days | start_utc | end_utc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | 142 | 1629218 | 88655 | 0 | 1540563 | 35632 | 76 | 73 | 2020-11-12 13:01:08.257560+00:00 | 2022-03-10 18:05:02.007252+00:00 |
| validation | 34 | 351422 | 261 | 0 | 351161 | 6753 | 19 | 19 | 2022-03-15 13:11:13.006783+00:00 | 2022-04-27 17:41:58.251000+00:00 |
| test | 51 | 341465 | 182887 | 0 | 158578 | 2809 | 26 | 13 | 2022-04-28 13:21:37.250000+00:00 | 2022-08-03 17:19:57.501000+00:00 |

All original raw rows receive exactly one whole-trip split, including quality-excluded rows. Row ledger eligibility determines later exports. The cross-split repeat screen rounds the six-feature vectors using the configured decimal resolutions, hashes them, and withholds matching states from later splits while retaining audit records. It does not remove repeated measurements within a split. This prevents exact/rounded-vector contamination under that explicit definition; hash collisions could conservatively overexclude. A rounding grid is not a complete near-neighbor search, and matching real operating states can be legitimate. Same-vehicle dependence and near-neighbors outside the screen remain limitations.

No trip, timestamp interval or input/target window crosses splits. Neighboring windows can overlap within one split; future metrics must aggregate by trip/time block and must not treat windows as independent vehicles. Temporal separation and screening do not prove population independence.

## 9. Feature-selection decisions

Ordered input vector: **Speed, Torque, Motor_Temp, HV_Bat_Voltage, Pack_1_C_Temp, SOC**. All are documented measurement channels with units in the workbook. One pack temperature and Speed are retained to reduce pack-channel and RPM redundancy. Torque's negative values are preserved because sign is meaningful; it is not energy consumption.

| column | description | unit | documented_polling | selected | reason |
| --- | --- | --- | --- | --- | --- |
| Speed | Speed (km/h) from the Leaf ECU | km/h | 1s: x | True | Documented unit; usable only under explicit quality exclusions; no claim of physical validation |
| Odometer | Km total | km | 10s: x | False | Aging shortcut and discontinuities; audit only |
| RPM | Motor revolutions per minute | rev/min | 1s: x | False | Redundant with Speed; use Speed in conservative view |
| SOC | State of Charge (SOC) of the HV Battery | % | Unknown | True | Documented unit; usable only under explicit quality exclusions; no claim of physical validation |
| SOH | State of Health is another indication of the battery's ability to hold and release energy and is reported as a percentage. When the battery is new SOH=100% | % | Unknown | False | Slow aging/identity shortcut, not a fault label |
| Torque | Motor Torque. https://www.carwow.co.uk/guides/glossary/what-is-torque (Nm).  Minimum unit step is 0.25 Nm | Nm | 1s: x | True | Documented unit; usable only under explicit quality exclusions; no claim of physical validation |
| Motor_Temp | This field is the drive motor temperature | °C | 10s: x | True | Documented unit; usable only under explicit quality exclusions; no claim of physical validation |
| HV_Bat_Voltage | High Voltage Battery Voltage (in V) | V | Unknown | True | Documented unit; usable only under explicit quality exclusions; no claim of physical validation |
| Brake | Brake pression measured from 0 (not pressed) to 369 (max). Unit?? | Unknown | 1s: x | False | Physical units undocumented; keep in audit only |
| Acc_Pedal | Acceleration pedal pression measured from 0 (not pressed) to 200 (max). Unit?? | Unknown | 1s: x | False | Physical units undocumented; keep in audit only |
| HV_Bat_Current_2 | High Voltage Battery Amperage (positive=from battery (driving), negative when regeneration or charging) | A | Unknown | False | Current polarity unresolved; retain original in audit, do not integrate energy |
| Ambient_C_Temp | Ambient temperature comes from the Leaf's outside temperature sensor and is saved in degrees Fahrenheit. This value is only valid when the Leaf is ON (not ACC mode and not when charging) | Unknown: workbook unit says °C; description says Fahrenheit | 10s: x | False | Celsius/Fahrenheit conflict unresolved |
| Pack_1_C_Temp | HV Battery temperature sensors (Pack_1_C_Temp, Pack_2_C_Temp, Pack_3_C_Temp, Pack_4_C_Temp). On Leaf 2018 40kW, Pack 3 is missing | °C | Unknown | True | Documented unit; usable only under explicit quality exclusions; no claim of physical validation |
| Pack_2_C_Temp | HV Battery temperature sensors (Pack_1_C_Temp, Pack_2_C_Temp, Pack_3_C_Temp, Pack_4_C_Temp). On Leaf 2018 40kW, Pack 3 is missing | °C | Unknown | False | Highly correlated with Pack 1; consistency/sentinel audit only |
| Pack_4_C_Temp | HV Battery temperature sensors (Pack_1_C_Temp, Pack_2_C_Temp, Pack_3_C_Temp, Pack_4_C_Temp). On Leaf 2018 40kW, Pack 3 is missing | °C | Unknown | False | Highly correlated with Pack 1; consistency/sentinel audit only |
| Pack_Avg_C_Temp | Unknown | Unknown | Unknown | False | Derived/redundant; select documented component target instead |
| Horsepower | Derived from battery voltage × current, not a measured mechanical output | Unknown: formula gives 1.341 × kW | Unknown | False | Deterministic power conversion, not independent mechanical output |
| Instant_kW | Battery electrical power from voltage × current / 1000 | kW | 250ms: (kW going into the battery pack) | False | Derived; polarity/energy-accounting unresolved |

All 92 raw columns have a selection decision in [feature_selection.csv](tables/preparation/feature_selection.csv). IDs/timestamps/context remain in the ledger, outside the transform feature order. Each `features_<split>.parquet` has `source_row` solely as a join key; consumers must select `transformer.output_features` rather than treating all numeric file columns as inputs. Raw values are accessible through the ledger. Status/context is not encoded into the default model-input matrix; moving/stationary/unknown is descriptive, not a diagnosis or verified charging state.

## 10. Anomaly detection dataset readiness

**Conditional, successfully exported for controlled telemetry experiments.** Six scaled features, frozen transformation metadata, original-value access, quality flags and chronological assignments are available. There are no anomaly or healthy labels. Training describes the selected recorded telemetry, not a certified healthy reference. Unsupported units/current channels are excluded. Withheld quality/repetition cases remain auditable. Do not call future unusualness scores fault probabilities or production diagnostics.

## 11. Energy prediction dataset readiness

**Blocked; zero energy-label or energy-training files exported.** Current magnitude is documented in A and voltage in V, and raw power equals their product/1000. However, observed current polarity conflicts with documented discharge direction. Charge_Mode lacks documented active-charge codes; regenerative braking and charging cannot be reliably separated. Nominal-energy/SOC/AHr calculations are not independent consumption truth. Odometer discontinuities further undermine energy-per-distance labels. Integrating an internally consistent but semantically uncertain power signal would manufacture an unsupported target. Researcher confirmation and independently verified energy accounting are required first.

## 12. Battery temperature forecasting readiness

**Conditional, successfully exported as compact observed-sequence indices.** Target: logged `Pack_1_C_Temp` at 60.0–60.5 seconds after the anchor, in documented °C. Temperature change is also recorded as target minus the current observed reading. Inputs end at the anchor and cover approximately the preceding 30.0 seconds. Anchors are at least 10.0 seconds apart. Targets are actual observed rows, never interpolated or scaled labels. Pack 1 avoids reliance on a computed mean; component/mean consistency is audited separately.

A window is exported only if its entire interval through the target stays within one segment/trip/split and contains no excluded row. This deliberately conservative future-interval quality filter can bias the dataset toward cleaner, more continuous operation; it is dataset eligibility, not an input feature. No future measurement is included in X. Targets may repeat because the physical reading or polling state stayed constant. This predicts a future logged value, not independently validated future battery thermal state. Unknown refresh/calibration and raw-export provenance keep status conditional.

Training-only feasibility counts for 30/60/120-second horizons are in [training_horizon_feasibility.csv](tables/preparation/training_horizon_feasibility.csv). The configured 60-second horizon was chosen before inspecting test results, as a short prototype interval relative to slower signals. Missing sensor cadence prevents claiming an optimal horizon. Rejected anchors are accounted for by trip in [window_accounting.csv](tables/preparation/window_accounting.csv): `{'anchors_considered': 76473, 'insufficient_history': 20360, 'no_future_match': 6543, 'unsafe_interval': 4376, 'exported': 45194}`. These anchor counts differ from source-row counts.

Consumer rule: retrieve only `source_row` values from `input_start_row` through `anchor_row` inclusive from the corresponding feature file; look up the separate future target from the sequence table. Do not concatenate target columns into input features. Windows use observed, variable-length sequences without resampling. The full contract is [sequence_specification.json](tables/preparation/sequence_specification.json).

## 13. Fitted transformations

Default `robust` scaling uses training median and training interquartile range; zero IQR uses scale 1 and is recorded. No clipping or outlier removal is implied. Optional standard scaling uses training mean and population standard deviation; `none` preserves numeric inputs. The fitted artifact records feature order, medians, centers, scales, fit rows and policy. Parameters are JSON, avoiding unsafe opaque deserialization. No transformations use validation/test rows or future targets. No PCA, target scaling, learned encodings or model fitting occurs. `1540563` training rows contributed to this run's transformation.

## 14. Output dataset sizes and schemas

Artifacts: `ml/artifacts/nissan_leaf_2018/preparation/d7e9e32e1ff2981a` (already Git-ignored). Trackable tables/report remain under `ml/reports/nissan_leaf_2018/`. No large files are added to Git.

| artifact | bytes | rows |
| --- | --- | --- |
| configuration.json | 2321 | metadata |
| features_test.parquet | 1819680 | 158578 |
| features_train.parquet | 17504744 | 1540563 |
| features_validation.parquet | 3862381 | 351161 |
| processed_flagged_rows.parquet | 4142587 | 369507 |
| quality_flag_dictionary.json | 2524 | metadata |
| row_ledger.parquet | 72885353 | 2322105 |
| segments.csv | 836884 | metadata |
| temperature_test.parquet | 97237 | 2809 |
| temperature_train.parquet | 1269799 | 35632 |
| temperature_validation.parquet | 241140 | 6753 |
| training_horizon_feasibility.csv | 67 | metadata |
| transformer.json | 873 | metadata |
| trip_splits.csv | 15519 | metadata |
| window_accounting.csv | 5810 | metadata |

Exact Arrow schemas: [OUTPUT_SCHEMAS.md](tables/preparation/OUTPUT_SCHEMAS.md). The artifact manifest contains byte sizes and SHA-256 hashes. The row ledger includes all raw observations and selected audit/context fields, not a copy of all 92 original columns. Excluded observations are accessed through eligibility flags; no additional full quarantine copy is necessary.

## 15. Remaining blockers

Current polarity, charging/regeneration identity, true energy accounting, ambiguous ambient/pedal units, sentinel interpretation, actual sensor refresh, calibration, raw acquisition processing and single-vehicle generalization remain unresolved. Proposed quality thresholds are review policies with selection bias, not diagnoses. Independently verified fault labels and healthy controls are absent. Sensor freshness cannot be inferred from identical repeated values. No production-readiness claim is supported.

## 16. Validation results

Independent full-output checks: `{'passed': True, 'source_rows_accounted': 2322105, 'temperature_windows_checked': 45194, 'trip_overlap': 0, 'timestamp_window_overlap_between_splits': 0, 'rounded_feature_overlap_between_splits': 0, 'transform_matches_frozen_training_state': True, 'future_feature_leakage_in_window_references': False, 'scope_note': 'Rounding screen does not prove independent telemetry or rule out all near-neighbors.'}`. These check actual row provenance, split exclusivity/embargo, cross-split rounded-feature overlap, frozen-transform application, window segment/quality/horizon constraints and exact source target lookup. Unit and regression test execution results, lint and repeated-run verification are recorded in [PREPARATION_VALIDATION.md](PREPARATION_VALIDATION.md) after execution; this report does not substitute inferred test results.

## 17. Reproduction commands

From repository root, using existing dependencies (pandas, NumPy, PyArrow; no installation required):

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests/test_nissan_leaf_preparation.py
```

Optional configuration: `--config path/to/reviewed.json`. Repeating the first command independently recomputes and compares output hashes. The run will stop on schema/hash drift, unsafe boundaries, empty usable tasks or reproducibility failure, leaving incomplete artifacts for investigation. Only generated intermediate files in that run's private directory are removed. Original downloads and earlier EDA/readiness outputs remain unchanged.

## 18. Recommended next ML experiment

After reviewing the conditional exclusions and sequence contract, evaluate a short-horizon **future logged pack-temperature experiment** against the persistence of the last available temperature, using the frozen chronological splits and reporting results per trip. Separately investigate unusual telemetry using the six-feature view without inventing fault labels. Inspect whether excluded/sentinel periods alter coverage before drawing broader conclusions. Energy prediction should remain blocked until its semantic issues are resolved. No experiment or model has been trained in this phase.
