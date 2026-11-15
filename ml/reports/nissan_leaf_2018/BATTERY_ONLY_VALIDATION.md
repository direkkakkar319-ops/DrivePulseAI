# Battery-only preparation validation

Purpose: record executed verification for Phase 1.1, without training or evaluating models.

## Completed run

- Configuration: `ml/notebooks/nissan_leaf_2018/config/battery_only.json`.
- New run: `1d6fc5b045ee25d0`.
- Artifacts: `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/`.
- Immutable parent: `d7e9e32e1ff2981a`.
- Source: 2,322,105 raw rows, with all rows retained in the audit ledger.
- Exported feature rows: 2,315,964.
- Quality-excluded rows: 5,978; additional cross-split rounded-vector exclusions: 163.
- Temperature indices checked: 48,862.
- Reference row and sequence count differences: zero for every split.
- Source memberships remain 142/34/51 trips; retained trips are 139/34/50.
- Three model columns only, in order: HV_Bat_Voltage, Pack_1_C_Temp, SOC.

## Tests and static checks

Executed after the complete artifact export:

- `.venv/bin/python -m pytest ml/tests -q`: **52 passed**, zero failed, zero skipped (1.41 seconds).
- `.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests`: **All checks passed**.
- `.venv/bin/ruff format --check ml/src/nissan_leaf_preparation ml/tests/test_nissan_leaf_battery.py`: **8 files already formatted**.

Before the full export, the artifact integration test appropriately skipped because outputs did not exist; the completed run above has no skips. Tests cover the exact feature set/order, negative/missing/nonfinite drivetrain independence, battery quality rules, immutable membership rejection, missing/nonfinite accounting, frozen training transformations, safe sequence ordering/gaps/trips, optimized duplicate lookup equivalence, original artifact immutability and rejection of tampered parent artifacts. Existing schema, temporal, split, transformation and window tests remain passing. Small synthetic fixtures test code behavior only; no synthetic training records or labels were exported.

## Full-output validation

The pipeline independently recalculated preprocessing statistics from retained training observations and compared every transformed feature value. It verified metadata alignment, all source row IDs, unchanged trip membership, timestamp embargoes, rounded-vector separation, all target values and all sequence references.

- Trip overlap: **0**.
- Cross-split timestamp/window overlap: **0**.
- Rounded feature-vector overlap after screening: **0**.
- Future features in input references: **none**; input endpoints precede target timestamps.
- No sequence crosses an unsafe segment; segments split at trips, duplicate timestamps and gaps above 1 second.
- Raw/preprocessed mixing: **none**.
- Transformer fit scope: **1,623,891 training rows only**.
- Original source hashes: verified before and after execution.
- Original artifacts: all 15 outputs plus parent manifest verified before and after execution.
- Original six-feature configuration: pinned SHA-256 verified before and after execution.
- Frozen parent membership file: preserved byte-for-byte.

These checks establish implementation invariants, not independent physical accuracy or statistical independence. Within-split windows can overlap. Rounding is not exhaustive near-neighbor screening. The holdout has been examined during data-quality investigation, so fresh data are needed for confirmatory claims.

## Independent rerun

**Passed.** A second complete raw-data scan and preparation run produced the same run ID `1d6fc5b045ee25d0`, manifest contents and all **18 output SHA-256 checksums**. The rerun verified existing artifacts before discarding only its own temporary computation directory. No existing run was overwritten.

Manifest SHA-256: `55d15a5ab13a762bc5cacabcb4ea621fed1e8530a9d7319330e0d81513aeab80`.

Both executions verified all source hashes, every original artifact and the original configuration before and after computation. Logs reported `Independent rerun matched every output checksum`. No stale cached artifact was used as a substitute for the rerun.

## Created files

- `ml/notebooks/nissan_leaf_2018/config/battery_only.json`.
- `ml/src/nissan_leaf_preparation/battery.py`.
- `ml/src/nissan_leaf_preparation/battery_report.py`.
- `ml/tests/test_nissan_leaf_battery.py`.
- `ml/reports/nissan_leaf_2018/BATTERY_ONLY_PREPARATION_REPORT.md`.
- `ml/reports/nissan_leaf_2018/BATTERY_ONLY_VALIDATION.md`.
- Trackable outputs under `ml/reports/nissan_leaf_2018/tables/battery_only/`:
  - `OUTPUT_SCHEMAS.md`.
  - `artifact_inventory.csv`.
  - `comparison.csv`.
  - `configuration.json`.
  - `features.csv`.
  - `missingness.csv`.
  - `quality_audit.csv`.
  - `split_summary.csv`.
  - `summary.json`.
  - `training_horizon_feasibility.csv`.
  - `transformer.json`.
  - `trip_splits.csv`.
  - `window_accounting.csv`.

Generated artifact files (Git-ignored):

- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/configuration.json`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/features_test.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/features_train.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/features_validation.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/frozen_parent_trip_splits.csv`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/manifest.json`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/metadata_test.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/metadata_train.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/metadata_validation.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/quality_flag_dictionary.json`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/row_ledger.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/segments.csv`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/temperature_test.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/temperature_train.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/temperature_validation.parquet`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/training_horizon_feasibility.csv`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/transformer.json`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/trip_splits.csv`.
- `ml/artifacts/nissan_leaf_2018/preparation/1d6fc5b045ee25d0/window_accounting.csv`.

## Modified existing files

- `ml/src/nissan_leaf_preparation/core.py`: battery-specific eligibility/configuration validation; original six-feature policy remains the default.
- `ml/src/nissan_leaf_preparation/pipeline.py`: frozen membership, separate artifact identity, battery metadata export, efficient equivalent duplicate screening and parent-integrity checks.
- `ml/src/nissan_leaf_preparation/validation.py`: frozen membership and three-column/companion validation.
- `ml/reports/nissan_leaf_2018/README.md`: battery-only report and reproduction links.

The original configuration, completed six-feature artifacts, source CSVs and unrelated application code were not modified. Prior uncommitted readiness/preparation work was preserved. No commit or push was performed.

## Reproduce

From the repository root:

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py --config ml/notebooks/nissan_leaf_2018/config/battery_only.json
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py --config ml/notebooks/nissan_leaf_2018/config/battery_only.json
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests
.venv/bin/ruff format --check ml/src/nissan_leaf_preparation ml/tests/test_nissan_leaf_battery.py
```

Original downloads, workbook, EDA outputs, negative-speed reference table and frozen parent artifacts must be available. Repeated invocation recalculates rather than returning a cached success. Artifact output hashes and schemas are in [artifact_inventory.csv](tables/battery_only/artifact_inventory.csv), [OUTPUT_SCHEMAS.md](tables/battery_only/OUTPUT_SCHEMAS.md) and [summary.json](tables/battery_only/summary.json).
