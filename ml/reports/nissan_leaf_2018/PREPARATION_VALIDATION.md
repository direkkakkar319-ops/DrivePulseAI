# Phase 1 preparation validation and file index

Purpose: record actual execution results, remaining coverage risks and all Phase 1 files.

## Execution results

- Full preparation completed for run `d7e9e32e1ff2981a`.
- Independently repeated the complete preparation. Result: **Independent rerun matched every output checksum**. All 15 generated artifact checksums and the manifest content matched. The duplicate temporary run was removed by the pipeline.
- All four original acquisition-manifest source checksums matched before and after each successful run, including both CSVs and the workbook. No original source file was modified.
- Full-output validation accounted for **2,322,105 source rows** and **45,194 temperature windows**.
- Cross-split trip overlap: **0**. Timestamp/window overlap between splits: **0**. Rounded-feature overlap under the configured screen: **0**.
- Saved transformer statistics matched a fresh training-only recomputation. Every exported transformed feature matched application of the saved artifact.
- `pytest ml/tests -q`: **30 passed in 1.13s**. Includes seven existing readiness tests and 23 preparation test cases, with no final failures or skips.
- Ruff check: **All checks passed!** Ruff format check: **7 files already formatted**.
- Synthetic fixtures are used only for code tests, never as exported training records or fault labels.

During implementation, tests exposed numeric-dtype-dependent hashing and the full-output validator exposed column reordering after JSON serialization. Both were fixed; regression checks now normalize numeric hash inputs and test transformer JSON round-trips. The unsuccessful private staging directory from that development run was removed after successful full-run reproduction. No unsuccessful run is marked complete.

## Important coverage limitation

The raw test split contains 341,465 rows, but 182,887 (53.5595%) are withheld by the negative-speed review policy. This leaves 158,578 feature rows. **25 of its 51 source trips have no retained feature rows**, and retained dates cover **13 of 26 recorded test dates**. The training split loses 5.4416% of rows (4 entirely excluded trips); validation loses 0.0743% (no entirely excluded trips).

This is selection bias requiring investigation, not evidence of 182,887 faulty observations. Do not silently loosen the policy or claim evaluation represents the complete test period. All withheld rows and original values remain in the ledger. Anomaly and temperature outputs remain conditional. Energy prediction remains blocked.

Quality categories: “Valid” operationally means no configured row-level flags (`quality_flags == 0`), not physically verified or healthy. Flags distinguish Missing, Suspicious, Invalid based on verified rules, and Unresolved; flags can overlap. Globally uncertain current and ambient semantics exclude those channels regardless of a row's flag value.

## Reproduction commands

Run from repository root:

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests/test_nissan_leaf_preparation.py
.venv/bin/ruff format --check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests/test_nissan_leaf_preparation.py
```

The second preparation invocation is an independent full-data reproduction check, not a cached success. Existing pandas, NumPy and PyArrow were used; no dependencies were installed. The original files and prior EDA/readiness outputs are required. No models were trained, and no commits or pushes occurred.

## Files created or modified

Only `README.md` was modified; the remaining files below are new for Phase 1. Earlier uncommitted readiness work was preserved.

| File | Purpose |
| --- | --- |
| [ml/src/nissan_leaf_preparation/__init__.py](../../src/nissan_leaf_preparation/__init__.py) | Package purpose and import boundary. |
| [ml/src/nissan_leaf_preparation/core.py](../../src/nissan_leaf_preparation/core.py) | Quality flags, time parsing, chronological split, transforms and safe window references. |
| [ml/src/nissan_leaf_preparation/pipeline.py](../../src/nissan_leaf_preparation/pipeline.py) | Chunked source scans, Parquet export, provenance and reproducibility checks. |
| [ml/src/nissan_leaf_preparation/report.py](../../src/nissan_leaf_preparation/report.py) | Generate the 18-section report and lightweight supporting tables. |
| [ml/src/nissan_leaf_preparation/validation.py](../../src/nissan_leaf_preparation/validation.py) | Independently inspect complete exported datasets for leakage and consistency. |
| [ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py](../../notebooks/nissan_leaf_2018/scripts/prepare_data.py) | Repository CLI entry point. |
| [ml/notebooks/nissan_leaf_2018/config/preparation.json](../../notebooks/nissan_leaf_2018/config/preparation.json) | Reviewed features, policies, thresholds, horizons and transformations. |
| [ml/tests/test_nissan_leaf_preparation.py](../../tests/test_nissan_leaf_preparation.py) | Synthetic code-only safety fixtures and real-output accounting test. |
| [ml/reports/nissan_leaf_2018/DATA_PREPARATION_REPORT.md](DATA_PREPARATION_REPORT.md) | Complete Phase 1 results, policies, limitations and commands. |
| [ml/reports/nissan_leaf_2018/PREPARATION_VALIDATION.md](PREPARATION_VALIDATION.md) | Executed checks, coverage caveats and this file index. |
| [ml/reports/nissan_leaf_2018/README.md](README.md) | Add navigation and reproduction instructions; preserve previous content. |
| [ml/reports/nissan_leaf_2018/tables/preparation/OUTPUT_SCHEMAS.md](tables/preparation/OUTPUT_SCHEMAS.md) | Exact Arrow schemas, including audit-only join keys. |
| [ml/reports/nissan_leaf_2018/tables/preparation/feature_selection.csv](tables/preparation/feature_selection.csv) | All 92 raw columns with input decisions, units and rationale. |
| [ml/reports/nissan_leaf_2018/tables/preparation/missingness.csv](tables/preparation/missingness.csv) | Missing counts for every scanned candidate/context column. |
| [ml/reports/nissan_leaf_2018/tables/preparation/output_inventory.csv](tables/preparation/output_inventory.csv) | Artifact filenames, row counts and sizes. |
| [ml/reports/nissan_leaf_2018/tables/preparation/preparation_summary.json](tables/preparation/preparation_summary.json) | Full provenance, quality, split, transform and artifact manifest. |
| [ml/reports/nissan_leaf_2018/tables/preparation/quality_audit.csv](tables/preparation/quality_audit.csv) | Overlapping rule counts for both source versions. |
| [ml/reports/nissan_leaf_2018/tables/preparation/segments.csv](tables/preparation/segments.csv) | Every safe continuity segment and its observed duration. |
| [ml/reports/nissan_leaf_2018/tables/preparation/sequence_specification.json](tables/preparation/sequence_specification.json) | Explicit input/target lookup contract and freshness caveat. |
| [ml/reports/nissan_leaf_2018/tables/preparation/split_summary.csv](tables/preparation/split_summary.csv) | Exact source/retained/excluded/window counts and date coverage. |
| [ml/reports/nissan_leaf_2018/tables/preparation/training_horizon_feasibility.csv](tables/preparation/training_horizon_feasibility.csv) | Training-only eligibility counts for reviewed horizons. |
| [ml/reports/nissan_leaf_2018/tables/preparation/transformer.json](tables/preparation/transformer.json) | Human-readable copy of fitted training-only preprocessing state. |
| [ml/reports/nissan_leaf_2018/tables/preparation/trip_splits.csv](tables/preparation/trip_splits.csv) | Whole-trip assignment and chronology. |
| [ml/reports/nissan_leaf_2018/tables/preparation/window_accounting.csv](tables/preparation/window_accounting.csv) | Exported/rejected anchor accounting by trip. |

## Generated artifacts (Git-ignored)

Directory: `ml/artifacts/nissan_leaf_2018/preparation/d7e9e32e1ff2981a`. These are generated preparation artifacts, not modifications to original CSVs.

| Artifact | Bytes | Rows |
| --- | ---: | ---: |
| `configuration.json` | 2321 | metadata |
| `features_test.parquet` | 1819680 | 158578 |
| `features_train.parquet` | 17504744 | 1540563 |
| `features_validation.parquet` | 3862381 | 351161 |
| `processed_flagged_rows.parquet` | 4142587 | 369507 |
| `quality_flag_dictionary.json` | 2524 | metadata |
| `row_ledger.parquet` | 72885353 | 2322105 |
| `segments.csv` | 836884 | metadata |
| `temperature_test.parquet` | 97237 | 2809 |
| `temperature_train.parquet` | 1269799 | 35632 |
| `temperature_validation.parquet` | 241140 | 6753 |
| `training_horizon_feasibility.csv` | 67 | metadata |
| `transformer.json` | 873 | metadata |
| `trip_splits.csv` | 15519 | metadata |
| `window_accounting.csv` | 5810 | metadata |

`manifest.json` accompanies these artifacts and records their checksums. Total listed artifact bytes: **102,686,919** (about 103 MB). Energy training/target files were deliberately not generated. No dense repeated-window tensor copy was created.
