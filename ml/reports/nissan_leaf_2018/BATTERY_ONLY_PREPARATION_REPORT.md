# Phase 1.1 — Battery-only data preparation

Purpose: preserve a separately versioned, auditable battery feature view without training or evaluating models. Configuration identity: `battery_only_v1`. Run ID: `1d6fc5b045ee25d0`. Status: **prepared for controlled experimentation; scientific claims remain conditional**.

## 1. Purpose and scope

An unavailable drivetrain channel should not automatically remove a usable battery observation. This view uses exactly three battery measurements for later battery-pattern and logged-temperature experiments. It does not infer vehicle faults, certify healthy telemetry or claim production readiness. All 2,322,105 raw rows remain auditable; 2,315,964 are exported as model-input rows and 48,862 safe forecasting examples are indexed.

## 2. Source and provenance

Preparation reads the unchanged raw CSV `data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv`. Its schema and 2,322,105 rows are verified against the prior EDA. All four acquisition sources, including both CSVs, workbook and archived webpage, are hash-verified before and after execution. The processed CSV is not pooled, borrowed for replacement values, or used as an independent evaluation source. Existing processed audit findings are referenced from [DATA_PREPARATION_REPORT.md](DATA_PREPARATION_REPORT.md).

Source URLs, usage-rights uncertainty and original checksums remain in [download_manifest.json](metadata/download_manifest.json). Battery units were checked in the original workbook using the existing extractor. This run fingerprints configuration bytes, parsed policy, package code, library versions and the frozen parent's artifacts. It stores originals' expected checksums in its own manifest, not by changing their manifests.

## 3. Negative-speed evidence

[NEGATIVE_SPEED_REVIEW.md](NEGATIVE_SPEED_REVIEW.md) found 266,235 raw Speed=-1 readings. In the test period, 182,885 of 182,887 negative-speed rows also have RPM=-1 and Torque=-1. This suggests acquisition unavailability, not a verified convention or fault diagnosis. These original values remain untouched in the new row ledger. `drivetrain_unavailable_suspected` flags negative-one speed, joint RPM/Torque=-1, or missing drivetrain measurements for audit only; false means the screen did not trigger, not proven availability. It never enters X or controls battery eligibility.

## 4. Exact feature order

| column | unit | documented_polling |
| --- | --- | --- |
| HV_Bat_Voltage | V | Unknown |
| Pack_1_C_Temp | °C | Unknown |
| SOC | % | Unknown |

Every `features_<split>.parquet` contains **only these three columns**, in this order, as transformed float32 values. No source row ID, timestamp, split, quality flag, availability indicator, target or drivetrain field appears in the feature matrix. No categorical encoding, PCA or inferred energy field is added.

## 5. Battery-specific quality rules

Only selected battery-channel missingness/nonfinite values, SOC outside [0,100], nonpositive or >500.0 V readings, pack-temperature sentinel review cases, impossible battery temperatures and duplicate timestamps block this view. The voltage ceiling is an exploratory screen, not a manufacturer failure limit. Pack values in [-1.01, -0.99] °C are unresolved possible sentinels, not established invalid physical temperatures; the existing conservative review across battery sensors 1/2/4 is retained. Peer temperatures do not become model inputs. Motor temperature cannot block a battery row, including missing, negative or impossible motor readings.

No missing battery values or targets are imputed. No sign conversion, clipping, IQR-outlier deletion, interpolation or fabricated values are applied. Negative speed remains negative in metadata. Other original quality observations remain flags. `quality_eligible` is task-specific; `battery_blocking_flags` records overlapping exclusion reasons and `cross_split_repeat` separately records duplicate-screen exclusion. No flag is a confirmed fault label.

## 6. Comparison with the original preparation

| split | original_features | battery_features | original_sequences | battery_sequences | original_retained_trips | battery_retained_trips | original_dates | battery_dates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | 1540563 | 1623891 | 35632 | 37753 | 138 | 139 | 73 | 74 |
| validation | 351161 | 351087 | 6753 | 6595 | 34 | 34 | 19 | 19 |
| test | 158578 | 340986 | 2809 | 4514 | 26 | 50 | 13 | 25 |

The original run `d7e9e32e1ff2981a` and original six-feature JSON configuration are not written or deleted. All 16 original artifact files, including the manifest, are checked before and after each run. The new feature view has a separate configuration, hashed artifact directory and report. Existing chunked trip reading, temporal checks, scaling, Parquet writer, sequence indexing and full-output validation are reused; the original split algorithm is not called for this view.

## 7. Train/validation/test row accounting

| split | trips | retained_trips | source_rows | quality_excluded_rows | cross_split_repeat_exclusions | feature_rows | temperature_sequences | source_recorded_days | retained_recorded_days | start_utc | end_utc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | 142 | 139 | 1629218 | 5327 | 0 | 1623891 | 37753 | 76 | 74 | 2020-11-12 13:01:08.257560+00:00 | 2022-03-10 18:05:02.007252+00:00 |
| validation | 34 | 34 | 351422 | 261 | 74 | 351087 | 6595 | 19 | 19 | 2022-03-15 13:11:13.006783+00:00 | 2022-04-27 17:41:58.251000+00:00 |
| test | 51 | 50 | 341465 | 390 | 89 | 340986 | 4514 | 26 | 25 | 2022-04-28 13:21:37.250000+00:00 | 2022-08-03 17:19:57.501000+00:00 |

Source rows = quality exclusions + duplicate-screen exclusions + exported rows for each split. No source rows are deleted. Within-split repeated measurements are preserved. All 5,978 quality-excluded rows remain in `row_ledger.parquet`; additional duplicate exclusions are flagged there as well. The narrower view makes no statement that all recovered observations are physically valid or healthy.

## 8. Trip coverage and frozen membership

Membership is copied from the original 142/34/51 trip assignments. The pipeline checks exact trip identities, source row counts and timestamp ranges against the frozen parent before accepting membership. Unsafe changes stop execution rather than recomputing boundaries. `frozen_parent_trip_splits.csv` is a byte-identical copy of the original; `trip_splits.csv` records the same membership with this view's quality counts. Retained-trip counts are shown above; source and retained trips are distinct quantities.

## 9. Recording-day coverage

Dates are calculated from actual UTC-represented observations, not inferred dates in recording gaps. Source and retained day counts are shown above and in [split_summary.csv](tables/battery_only/split_summary.csv). One vehicle and unequal historical coverage still limit transfer. The test data influenced the missing-channel investigation; the holdout is now explored even though no model scores have been used. Freeze this policy before further experimentation, and obtain fresh independently held-out data for confirmatory claims.

## 10. Temperature forecasting sequences

Input history: 30.0 seconds with 0.5s boundary tolerance. Anchor spacing: at least 10.0 seconds. Target: actual logged Pack_1_C_Temp at 60.0–60.5 seconds after the anchor. Source row cadence is not sensor refresh cadence; the workbook does not establish exact pack refresh timing.

Compact `temperature_<split>.parquet` files contain input start/anchor source IDs, target source ID, corresponding timestamps, Trip/segment/split and the unchanged future temperature. Targets remain outside the three-column feature matrix. Use `metadata_<split>.parquet` to map source IDs to feature-row positions; fetch only IDs from input_start_row through anchor_row inclusive. Never append target values or future feature rows to X. Targets and temperature changes are not scaled or imputed. Windows have variable observed row counts; no dense repeated arrays or synthetic samples are created.

A window cannot cross a trip, split or >1.0s gap, and its interval through the target must contain only eligible rows. This future-interval quality screen is selection for dataset validity, not a future input; it can bias coverage toward cleaner intervals. Windows may overlap within a split, so later evaluation must account for temporal dependence. `{'anchors_considered': 76473, 'insufficient_history': 20360, 'no_future_match': 6543, 'unsafe_interval': 708, 'exported': 48862}`.

## 11. Exclusion reasons and audit metadata

| flag | bit | category | blocks_battery_view | rows | meaning |
| --- | --- | --- | --- | --- | --- |
| missing_candidate | 1 | Missing | True | 0 | Candidate NaN; no silent fill |
| nonfinite_candidate | 2 | Invalid based on verified rules | True | 0 | Infinite measurement cannot be a finite physical reading |
| soc_domain | 4 | Invalid based on verified rules | True | 2040 | SOC outside documented percentage domain [0,100]; may encode unavailable state, not a fault |
| speed_negative | 8 | Suspicious | False | 266235 | Negative speed magnitude/unavailable code unresolved |
| voltage_review | 16 | Suspicious | True | 2141 | Nonpositive or above review threshold; not a fault |
| pack_sentinel | 32 | Unresolved | True | 3850 | Pack reading near -1 may be unavailable or real; no conversion |
| physical_temperature | 64 | Invalid based on verified rules | True | 0 | Pack sensors 1/2/4 below absolute zero; motor temperature does not participate |
| tire_zero_or_negative | 128 | Suspicious | False | 457168 | Pressure code needs interpretation; excluded feature |
| odometer_decrease | 256 | Suspicious | False | 202 | Decrease within trip; not corrected |
| odometer_jump | 512 | Suspicious | False | 190 | Large short-interval jump; not corrected |
| soh_zero | 1024 | Unresolved | False | 2853 | Reported zero health not treated as battery failure |
| power_formula | 2048 | Suspicious | False | 0 | Stored power differs from V*I/1000; no replacement |
| temperature_formula | 4096 | Suspicious | False | 0 | Stored mean differs from components; no replacement |
| duplicate_timestamp | 8192 | Invalid based on verified rules | True | 0 | Ambiguous ordering for sequence use, not an invalid sensor reading |
| long_gap | 16384 | Suspicious | False | 15825 | Start of new continuity segment |
| soh_missing | 32768 | Missing | False | 2247 | SOH NaN retained; not a selected input |
| irregular_interval | 65536 | Unresolved | False | 187435 | Row interval outside 0.2–0.3s descriptive band; no resampling |

Counts overlap. Only rows whose blocking bits are nonzero are quality-excluded. The all-row ledger contains original selected/context values and audit flags; excluded records are inspectable without a redundant quarantine copy. Companion metadata is aligned one-to-one, in order, with each feature matrix and contains source row, exported index, original timestamp, Trip, split, segment, flags, quality status and source path. `no_configured_row_flags` is not a healthy label; `retained_with_review_flags` can include unavailable drivetrain telemetry.

## 12. Duplicate screening

Screening uses the same configured rounding resolutions applied to this view's three columns. Later-split states matching any earlier-split quality-eligible state are withheld; this is rerun on the actual selected feature set. The battery-only exact uint64 membership lookup is optimized, but semantically equivalent to the existing set-based lookup. Hash collisions could conservatively overexclude; rounding is not an exhaustive near-neighbor search or proof of independence. With fewer dimensions, additional coincident battery states are expected and need not be faults.

Observed split exclusions: `{'train': 0, 'validation': 74, 'test': 89}`. Comparison with independently investigated reference counts: `[{'split': 'train', 'feature_rows_difference': 0, 'temperature_sequences_difference': 0}, {'split': 'validation', 'feature_rows_difference': 0, 'temperature_sequences_difference': 0}, {'split': 'test', 'feature_rows_difference': 0, 'temperature_sequences_difference': 0}]`. Zero differences mean reproduced counts, not hardcoded counts. Differences, if any, must be reviewed rather than adjusted to reach the reference.

## 13. Training-only preprocessing

Configured scaling: `robust`. Robust default fits training medians and interquartile ranges; zero ranges use 1 and are recorded. Exactly 1,623,891 retained training observations contribute. Validation/test inputs receive those frozen statistics with no refit. Standard or no scaling remain configurable; this three-input release intentionally disallows imputation/indicator expansion. Fitted feature order, centers, scales and fit scope are exported as JSON. Serialization/reload preserves order. Independent output validation recomputes the training statistics and checks every transformed output against the frozen artifact.

## 14. Leakage validation

`{'passed': True, 'source_rows_accounted': 2322105, 'temperature_windows_checked': 48862, 'trip_overlap': 0, 'timestamp_window_overlap_between_splits': 0, 'rounded_feature_overlap_between_splits': 0, 'transform_matches_frozen_training_state': True, 'future_feature_leakage_in_window_references': False, 'scope_note': 'Rounding screen does not prove independent telemetry or rule out all near-neighbors.'}`

Full-data checks cover original split membership, companion alignment, source lineage, training-only preprocessing, no rounded-feature overlap between splits, window horizons, safe segments and exact observed targets. The chronological embargo remains 90.5 seconds minimum. No raw/preprocessed mixing occurs. Computational leakage controls do not establish independent vehicles or erase policy selection after test-data inspection.

## 15. Artifact paths and checksums

New artifact directory: `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0`. Original: `ml/artifacts/nissan_leaf_2018/preparation/d7e9e32e1ff2981a`. Large Parquet files stay under the existing Git-ignore rule. Manifest contains input/code/config/parent hashes and exact output sizes, hashes and schemas. [artifact_inventory.csv](tables/battery_only/artifact_inventory.csv) lists every output SHA-256; [OUTPUT_SCHEMAS.md](tables/battery_only/OUTPUT_SCHEMAS.md) records exact schemas. [summary.json](tables/battery_only/summary.json) is the trackable manifest copy. Models, fault labels and energy targets are not artifacts.

## 16. Remaining limitations and validation records

There are no verified battery fault labels, independent healthy controls or maintenance outcomes. An unsupervised detector can identify uncommon recorded battery patterns but cannot establish confirmed fault detection or diagnostic accuracy. Apparent anomalies may be state variation or measurement issues. Current polarity, calibration, sensor refresh and original logger processing remain uncertain. SOC/voltage are correlated. Repeated pack readings may be genuine or stale; future logged-temperature prediction remains conditional and is not independently validated thermal ground truth. Sentinel/duplicate exclusions can remove legitimate observations. This is not production-ready data validation.

Executed tests, Ruff, parent/source checksum verification and independent rerun results are recorded in [BATTERY_ONLY_VALIDATION.md](BATTERY_ONLY_VALIDATION.md). Passing code/data-integrity tests does not certify physical measurements.

## 17. Reproduction commands

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py --config ml/notebooks/nissan_leaf_2018/config/battery_only.json
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/tests/test_nissan_leaf_battery.py
```

Repeat the first command for an independent complete rerun; every generated artifact checksum and manifest must match. A new configuration/code fingerprint creates a different directory. Existing completed runs are verified and never overwritten. No model training/evaluation, dependency installation, commits or pushes occur in this phase.

## 18. Recommended next experiment — not implemented

Use a small, fixed-seed Isolation Forest as a lightweight battery-pattern baseline. Its score ranks unusual observations rather than identifying confirmed faults; see the [official scikit-learn outlier-detection documentation](https://scikit-learn.org/stable/modules/outlier_detection.html#isolation-forest). Fit only training data, optionally with a prespecified cap per trip so long recordings do not dominate. Do not infer a true fault rate from an assumed contamination setting.

Before touching test scores, freeze the experiment and review budget using training/validation only. Examine score stability across seeds and dates, alerts per recording hour/trip, persistence of alerts, and raw voltage/SOC/temperature context for high-ranked and randomly sampled intervals. Stratify review by suspected drivetrain availability and battery quality flags. Without expert-adjudicated outcomes, do not report fault precision, recall, F1, ROC-AUC or false-positive rate. An alert budget is not a known fault prevalence. For a later temperature experiment, compare against persistence of the last logged temperature and report errors by trip/horizon; none of these baselines or metrics has been implemented or evaluated here. Seek fresh vehicle/time holdouts for confirmation.
