# Isolation Forest baseline — validation record

Purpose: document executed checks, protocol chronology, implementation files and limitations for experiment **0c777345c64dfeba**.

## Executed verification

- `.venv/bin/python -m pytest ml/tests -q`: **70 passed in 3.83 seconds**, zero failures, zero skips.
- `.venv/bin/ruff check ml/src/nissan_leaf_isolation ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py ml/tests`: **All checks passed**.
- `.venv/bin/ruff format --check ml/src/nissan_leaf_isolation ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py ml/tests/test_nissan_leaf_isolation.py`: **6 files already formatted**.
- Before full output generation: 69 passed, one output-integration check skipped because the report did not yet exist; the completed run has no skips.
- All pinned preparation, original six-feature artifacts/configuration and original source hashes verified before and after each executed stage.
- Same-seed reconstruction: **byte-identical fitted model**; validation probe scores exactly identical across 4,096 rows. This verifies the same baseline, not a competing model.
- score_samples and decision_function relation checked against the scikit-learn API on train/validation probes.
- No test rescoring for reproducibility.
- Independent saved-output inspection: **2,315,964 scores and 558 candidate intervals verified**, using saved scores only. Three deviation-evidence columns exactly match the original scaled inputs. Metadata source rows match preparation. All interval rows satisfy the threshold, have consecutive source IDs, remain in one trip/segment and have positive timestamp steps <=1 second.
- Trip overlap: zero. Chronological split overlap: zero. Inputs contain only current three-feature measurements, with no future fields.
- Frozen protocol creation time precedes the write-once test receipt. No post-test parameter changes.

The new unit tests cover loading/count validation, exact feature order/dimensions, missing/nonfinite rejection, lineage/timestamps, training-only fitting, deterministic internal sampling and model serialization, score direction, explanatory evidence, training-only quantiles/ties, irregular sampling, trip/gap/source-row boundaries, point/short/persistent intervals, repeat-test rejection and preparation immutability. Existing preparation/readiness tests remain passing. Synthetic fixtures test software behavior only; no fault labels were generated or used for evaluation.

## Protocol and scientific findings

All 1,623,891 retained training observations across 139 trips and 74 recorded days were supplied to fit. The estimator's internal max_samples='auto' samples 256 observations per tree; no separate dataset subset was selected. Long-trip weighting and temporal dependence remain.

The model fit took **1.770s** and its file is **2,980,717 bytes**. Development including repeat-fit verification, scoring and candidate diagnostics took **68.061s**. These are measured local timings, not deployment latency benchmarks.

The predeclared 0.5% training-budget threshold is **-0.6676090615628322**, with strict lower-score flagging. It remains provisional. Validation review was recorded in `ml/artifacts/nissan_leaf_2018/isolation_forest/0c777345c64dfeba/DEVELOPMENT_REVIEW.md` before test scoring. The 0.1% training quantile flags no validation rows; 1% flags 2.320792%. Labels and review-capacity evidence do not justify declaring an optimal threshold.

The single frozen exploratory test flags **4.117764%** of rows versus **0.528929%** in validation, with 152 versus 49 persistent intervals. This is a change in score/alert distributions, not a measured fault rate. Five test trips have persistent intervals; a sixth has point/short candidates only.

Example review evidence: training candidates in Trip 64 include low SOC around 13–16%; a test candidate in Trip 231 has logged temperature 55.3°C, SOC 25.80–25.98% and voltage 329.82–340.24 V. These are observed conditions requiring interpretation, not failure diagnoses. Training maximum logged temperature was 43.1°C; validation reached 55°C. Some alerts can reflect state/seasonal coverage shift or sensor behavior.

Test row alert fractions are 5.552268% where drivetrain unavailability is suspected and 2.466215% elsewhere. This is a descriptive, confounded association: availability is audit metadata, not a model feature or fault label. Expert review should inspect both flagged and representative unflagged conditions before changing any future policy.

Temperature predictions, autoencoders, app integration and fault classification were not implemented. No meaningful fault accuracy/F2 or other supervised diagnostic metric exists without verified labels. No commit/push occurred.

## New implementation files

- `ml/src/nissan_leaf_isolation/__init__.py`: package purpose.
- `ml/src/nissan_leaf_isolation/core.py`: input checks, training-only fit, scores/evidence, thresholds and temporal diagnostics.
- `ml/src/nissan_leaf_isolation/pipeline.py`: pinned provenance, immutable development/test stages and explicit settings freeze.
- `ml/src/nissan_leaf_isolation/report.py`: reports, plots and expert-review contexts from saved scores.
- `ml/notebooks/nissan_leaf_2018/config/isolation_forest.json`: versioned experiment policy.
- `ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py`: CLI.
- `ml/tests/test_nissan_leaf_isolation.py`: focused baseline tests.
- `ml/reports/nissan_leaf_2018/ISOLATION_FOREST_BASELINE_REPORT.md`.
- `ml/reports/nissan_leaf_2018/ISOLATION_FOREST_VALIDATION.md`.

Modified existing file: `ml/reports/nissan_leaf_2018/README.md` (new report/reproduction links). No existing preparation implementation, configuration or artifacts were changed in Phase 2.

## Output index

Model/data artifacts are Git-ignored. Every file and checksum is listed in [artifact_inventory.csv](tables/isolation_forest/0c777345c64dfeba/artifact_inventory.csv).

### ml/artifacts/nissan_leaf_2018/isolation_forest/0c777345c64dfeba

- `DEVELOPMENT_REVIEW.md` (1,745 bytes).
- `dates_test.csv` (2,154 bytes).
- `dates_train.csv` (6,177 bytes).
- `dates_validation.csv` (1,647 bytes).
- `development.json` (13,689 bytes).
- `fit_feature_distributions_scaled.csv` (712 bytes).
- `fit_rows.parquet` (17,375,726 bytes).
- `frozen_protocol.json` (10,330 bytes).
- `intervals_test.parquet` (30,909 bytes).
- `intervals_train.parquet` (18,514 bytes).
- `intervals_validation.parquet` (17,027 bytes).
- `model.joblib` (2,980,717 bytes).
- `quality_test.csv` (2,203 bytes).
- `quality_train.csv` (2,283 bytes).
- `quality_validation.csv` (2,095 bytes).
- `scores_test.parquet` (10,156,902 bytes).
- `scores_train.parquet` (39,269,186 bytes).
- `scores_validation.parquet` (10,344,800 bytes).
- `test_evaluation.json` (1,485 bytes).
- `test_started.json` (145 bytes).
- `threshold_candidates.csv` (2,946 bytes).
- `trips_test.csv` (3,863 bytes).
- `trips_train.csv` (10,598 bytes).
- `trips_validation.csv` (2,627 bytes).

### ml/reports/nissan_leaf_2018/tables/isolation_forest/0c777345c64dfeba

- `artifact_inventory.csv` (3,753 bytes).
- `context_test_1.parquet` (18,206 bytes).
- `context_test_2.parquet` (16,521 bytes).
- `context_test_3.parquet` (24,279 bytes).
- `context_test_4.parquet` (31,218 bytes).
- `context_test_5.parquet` (20,180 bytes).
- `context_train_1.parquet` (41,912 bytes).
- `context_train_2.parquet` (36,221 bytes).
- `context_train_3.parquet` (28,570 bytes).
- `context_train_4.parquet` (49,662 bytes).
- `context_train_5.parquet` (41,680 bytes).
- `context_validation_1.parquet` (18,531 bytes).
- `context_validation_2.parquet` (22,146 bytes).
- `context_validation_3.parquet` (18,472 bytes).
- `context_validation_4.parquet` (18,927 bytes).
- `context_validation_5.parquet` (19,605 bytes).
- `dates_test.csv` (2,154 bytes).
- `dates_train.csv` (6,177 bytes).
- `dates_validation.csv` (1,647 bytes).
- `experiment_summary.json` (15,746 bytes).
- `expert_review_candidates.csv` (5,089 bytes).
- `feature_distributions_original_units.csv` (1,229 bytes).
- `fit_feature_distributions_scaled.csv` (712 bytes).
- `quality_test.csv` (2,203 bytes).
- `quality_train.csv` (2,283 bytes).
- `quality_validation.csv` (2,095 bytes).
- `score_stability.csv` (770 bytes).
- `split_metrics.csv` (582 bytes).
- `threshold_candidates.csv` (2,897 bytes).
- `trips_test.csv` (3,863 bytes).
- `trips_train.csv` (10,598 bytes).
- `trips_validation.csv` (2,627 bytes).

### ml/reports/nissan_leaf_2018/figures/isolation_forest/0c777345c64dfeba

- `context_test.png` (78,664 bytes).
- `context_train.png` (104,518 bytes).
- `context_validation.png` (77,373 bytes).
- `dates_test.png` (93,662 bytes).
- `dates_train.png` (78,787 bytes).
- `dates_validation.png` (70,859 bytes).
- `score_distributions.png` (40,011 bytes).
- `trips_test.png` (58,807 bytes).
- `trips_train.png` (53,482 bytes).
- `trips_validation.png` (55,529 bytes).

## Reproduction protocol

Run from the repository root with the existing environment and pinned preparation artifacts:

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage develop
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage test
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage report
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_isolation ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py ml/tests
```

The stage commands reproduce in a clean workspace; they deliberately refuse to overwrite this completed experiment or score test again. Same-seed reconstruction is performed within development. Review development diagnostics and the frozen protocol before test execution. Reporting reads saved score files only. The manifest records dependencies/code/input fingerprints; runtime and execution timestamps can vary.

The test period was previously inspected during preparation. No code invariant can restore a pristine holdout; obtain new temporal/vehicle data for confirmatory validation.
