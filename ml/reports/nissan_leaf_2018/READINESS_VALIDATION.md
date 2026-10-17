# ML readiness validation and output index

Purpose: record executed verification and every file added or modified for the readiness assessment.

## Executed checks

- Targeted analysis completed for both source files; all acquisition-manifest file hashes and byte sizes matched. No source file was written.
- Full row counts and exact schemas matched existing EDA; scanned-column missing counts also matched.
- Formula checks reproduced the previous EDA results; the additional raw remaining-energy formula matched all 2,322,105 rows.
- `pytest`: **7 passed in 0.52s**. Tests cover inventory completeness, schema handling, timestamp order, trip boundaries, missing accounting, derived consistency, and report/manifest consistency.
- Ruff check: **All checks passed!** New Python files were formatted with Ruff.
- Visually inspected the processed SOH figure. Two figures and all tables were generated from real data.
- No final test or lint failures remain. During development, CSV mixed-type round-trip comparison needed normalization in the test; testing an in-progress output manifest also failed. Final checks ran after analysis completed.
- No models, artificial records/labels, source cleaning, final splits, commits or pushes.

## Commands executed

```bash
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/readiness.py
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python -m pytest ml/tests/test_nissan_leaf_readiness.py -q
.venv/bin/ruff check ml/notebooks/nissan_leaf_2018/scripts/readiness.py ml/notebooks/nissan_leaf_2018/scripts/readiness_report.py ml/tests/test_nissan_leaf_readiness.py
```

Run analysis to completion before running artifact-consistency tests. The original downloads and prior EDA outputs must be present. No new installation was required.

## Complete file index

All paths below are repository-relative. Only README.md modifies an existing file; all other entries are new.

| Path | Purpose |
| --- | --- |
| [ml/notebooks/nissan_leaf_2018/scripts/readiness.py](../../notebooks/nissan_leaf_2018/scripts/readiness.py) | Verify sources and run targeted descriptive readiness analyses. |
| [ml/notebooks/nissan_leaf_2018/scripts/readiness_report.py](../../notebooks/nissan_leaf_2018/scripts/readiness_report.py) | Render the complete evidence-linked readiness report. |
| [ml/tests/test_nissan_leaf_readiness.py](../../tests/test_nissan_leaf_readiness.py) | Seven small-fixture/helper and artifact-consistency tests. |
| [ml/reports/nissan_leaf_2018/ML_READINESS_REPORT.md](ML_READINESS_REPORT.md) | Full 15-section assessment and complete feature dictionary. |
| [ml/reports/nissan_leaf_2018/readiness_manifest.json](readiness_manifest.json) | Source, code, reused-table and generated-output checksums. |
| [ml/reports/nissan_leaf_2018/READINESS_VALIDATION.md](READINESS_VALIDATION.md) | Executed checks and complete new/modified-file index. |
| [ml/reports/nissan_leaf_2018/README.md](README.md) | Modified existing guide: assessment links and reproduction commands. |
| [ml/reports/nissan_leaf_2018/tables/readiness/adjacent_similarity.csv](tables/readiness/adjacent_similarity.csv) | Same-trip short-gap equality and lag-one correlations. |
| [ml/reports/nissan_leaf_2018/tables/readiness/feature_inventory.csv](tables/readiness/feature_inventory.csv) | Every raw/processed column with eligibility and leakage caveats. |
| [ml/reports/nissan_leaf_2018/tables/readiness/processed_daily_soh.csv](tables/readiness/processed_daily_soh.csv) | Per-recorded-day medians and row counts; no gap filling. |
| [ml/reports/nissan_leaf_2018/tables/readiness/processed_soh_changes.csv](tables/readiness/processed_soh_changes.csv) | Every observed adjacent SOH transition and trip-boundary flag. |
| [ml/reports/nissan_leaf_2018/tables/readiness/processed_soh_values.csv](tables/readiness/processed_soh_values.csv) | All reported SOH values and counts, including missingness. |
| [ml/reports/nissan_leaf_2018/tables/readiness/processed_trip_soh.csv](tables/readiness/processed_trip_soh.csv) | Per-trip descriptive medians, sizes and SOH ranges/cardinalities. |
| [ml/reports/nissan_leaf_2018/tables/readiness/raw_daily_soh.csv](tables/readiness/raw_daily_soh.csv) | Per-recorded-day medians and row counts; no gap filling. |
| [ml/reports/nissan_leaf_2018/tables/readiness/raw_soh_changes.csv](tables/readiness/raw_soh_changes.csv) | Every observed adjacent SOH transition and trip-boundary flag. |
| [ml/reports/nissan_leaf_2018/tables/readiness/raw_soh_values.csv](tables/readiness/raw_soh_values.csv) | All reported SOH values and counts, including missingness. |
| [ml/reports/nissan_leaf_2018/tables/readiness/raw_trip_soh.csv](tables/readiness/raw_trip_soh.csv) | Per-trip descriptive medians, sizes and SOH ranges/cardinalities. |
| [ml/reports/nissan_leaf_2018/tables/readiness/readiness_metrics.json](tables/readiness/readiness_metrics.json) | Exact counts, SOH statistics, time checks and formula audits. |
| [ml/reports/nissan_leaf_2018/tables/readiness/selected_missing_checks.csv](tables/readiness/selected_missing_checks.csv) | Independent missing accounting for scanned columns. |
| [ml/reports/nissan_leaf_2018/tables/readiness/soh_associations.csv](tables/readiness/soh_associations.csv) | Pearson/Spearman associations by rows, trips, days, differences and month. |
| [ml/reports/nissan_leaf_2018/tables/readiness/task_readiness.csv](tables/readiness/task_readiness.csv) | Four-task readiness, intended outputs and validation requirements. |
| [ml/reports/nissan_leaf_2018/figures/readiness/processed_soh_shortcuts.png](figures/readiness/processed_soh_shortcuts.png) | Daily SOH trajectory and mileage/temperature/voltage scatter panels. |
| [ml/reports/nissan_leaf_2018/figures/readiness/raw_soh_shortcuts.png](figures/readiness/raw_soh_shortcuts.png) | Daily SOH trajectory and mileage/temperature/voltage scatter panels. |

## Limits of completion

This is a completed assessment of the available evidence, not resolution of every source ambiguity. Current polarity, questionable units/readings, preprocessing provenance, exact SOH update mechanism and missing outcome histories remain unresolved and are explicitly recorded in the report. Physical health, diagnostic accuracy, maintenance usefulness and transfer to other vehicles were not validated. No inaccessible supplementary publication was newly fetched or assumed to have been read.
