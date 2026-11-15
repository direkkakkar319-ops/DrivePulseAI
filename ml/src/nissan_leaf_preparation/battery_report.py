"""Generate the separately versioned battery-only preparation report and audit tables."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from .core import FLAGS, save_json
from .report import markdown


def write_report(summary: dict, directory: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    base = root / "ml/reports/nissan_leaf_2018"
    tables = base / "tables/battery_only"
    tables.mkdir(parents=True, exist_ok=True)
    config = summary["config"]
    parent = (
        root / "ml/artifacts/nissan_leaf_2018/preparation" / config["parent_run_id"]
    )
    old = json.loads((parent / "manifest.json").read_text())
    old_trips = pd.read_csv(parent / "trip_splits.csv")
    comparison = []
    for new in summary["splits"]:
        original = next(row for row in old["splits"] if row["split"] == new["split"])
        comparison.append(
            {
                "split": new["split"],
                "original_features": original["feature_rows"],
                "battery_features": new["feature_rows"],
                "original_sequences": original["temperature_sequences"],
                "battery_sequences": new["temperature_sequences"],
                "original_retained_trips": int(
                    (
                        old_trips.split.eq(new["split"])
                        & old_trips.quality_eligible.gt(0)
                    ).sum()
                ),
                "battery_retained_trips": new["retained_trips"],
                "original_dates": original["retained_recorded_days"],
                "battery_dates": new["retained_recorded_days"],
            }
        )
    comparison = pd.DataFrame(comparison)
    comparison.to_csv(tables / "comparison.csv", index=False)
    pd.DataFrame(summary["splits"]).to_csv(tables / "split_summary.csv", index=False)
    blockers = {
        "missing_candidate",
        "nonfinite_candidate",
        "soc_domain",
        "voltage_review",
        "pack_sentinel",
        "physical_temperature",
        "duplicate_timestamp",
    }
    audit = summary["audit"]["raw"]
    flags = pd.DataFrame(
        [
            {
                "flag": name,
                "bit": bit,
                "category": category,
                "blocks_battery_view": name in blockers,
                "rows": audit["flag_counts_overlapping"][name],
                "meaning": meaning,
            }
            for name, (bit, category, meaning) in FLAGS.items()
        ]
    )
    flags.loc[flags.flag.eq("physical_temperature"), "meaning"] = (
        "Pack sensors 1/2/4 below absolute zero; motor temperature does not participate"
    )
    flags.to_csv(tables / "quality_audit.csv", index=False)
    pd.DataFrame(
        [
            {
                "feature": name,
                "missing_rows": audit["missing_counts"][name],
                "missing_pct": audit["missing_counts"][name] / audit["rows"] * 100,
            }
            for name in config["features"]
        ]
    ).to_csv(tables / "missingness.csv", index=False)
    save_json(tables / "summary.json", summary)
    for name in [
        "trip_splits.csv",
        "window_accounting.csv",
        "transformer.json",
        "configuration.json",
        "training_horizon_feasibility.csv",
    ]:
        shutil.copyfile(directory / name, tables / name)
    outputs = pd.DataFrame(
        [
            {
                "file": name,
                "bytes": info["bytes"],
                "rows": info["rows"] if info["rows"] is not None else "metadata",
                "sha256": info["sha256"],
            }
            for name, info in summary["outputs"].items()
        ]
    )
    outputs.to_csv(tables / "artifact_inventory.csv", index=False)
    schemas = "\n\n".join(
        f"## {name}\n\n```text\n{info['schema']}\n```"
        for name, info in summary["outputs"].items()
        if info["schema"]
    )
    (tables / "OUTPUT_SCHEMAS.md").write_text(
        "# Battery-only artifact schemas\n\nPurpose: document feature/metadata separation and temporal index fields.\n\n"
        + schemas
        + "\n"
    )
    selected = pd.read_csv(base / "tables/raw/column_dictionary.csv")
    selected = selected.set_index("column").loc[config["features"]].reset_index()
    selected[["column", "description", "unit", "documented_polling"]].to_csv(
        tables / "features.csv", index=False
    )
    retained_total = sum(row["feature_rows"] for row in summary["splits"])
    target_total = sum(row["temperature_sequences"] for row in summary["splits"])
    report = f"""# Phase 1.1 — Battery-only data preparation

Purpose: preserve a separately versioned, auditable battery feature view without training or evaluating models. Configuration identity: `{config["view"]}`. Run ID: `{summary["run_id"]}`. Status: **prepared for controlled experimentation; scientific claims remain conditional**.

## 1. Purpose and scope

An unavailable drivetrain channel should not automatically remove a usable battery observation. This view uses exactly three battery measurements for later battery-pattern and logged-temperature experiments. It does not infer vehicle faults, certify healthy telemetry or claim production readiness. All {audit["rows"]:,} raw rows remain auditable; {retained_total:,} are exported as model-input rows and {target_total:,} safe forecasting examples are indexed.

## 2. Source and provenance

Preparation reads the unchanged raw CSV `data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv`. Its schema and {audit["rows"]:,} rows are verified against the prior EDA. All four acquisition sources, including both CSVs, workbook and archived webpage, are hash-verified before and after execution. The processed CSV is not pooled, borrowed for replacement values, or used as an independent evaluation source. Existing processed audit findings are referenced from [DATA_PREPARATION_REPORT.md](DATA_PREPARATION_REPORT.md).

Source URLs, usage-rights uncertainty and original checksums remain in [download_manifest.json](metadata/download_manifest.json). Battery units were checked in the original workbook using the existing extractor. This run fingerprints configuration bytes, parsed policy, package code, library versions and the frozen parent's artifacts. It stores originals' expected checksums in its own manifest, not by changing their manifests.

## 3. Negative-speed evidence

[NEGATIVE_SPEED_REVIEW.md](NEGATIVE_SPEED_REVIEW.md) found 266,235 raw Speed=-1 readings. In the test period, 182,885 of 182,887 negative-speed rows also have RPM=-1 and Torque=-1. This suggests acquisition unavailability, not a verified convention or fault diagnosis. These original values remain untouched in the new row ledger. `drivetrain_unavailable_suspected` flags negative-one speed, joint RPM/Torque=-1, or missing drivetrain measurements for audit only; false means the screen did not trigger, not proven availability. It never enters X or controls battery eligibility.

## 4. Exact feature order

{markdown(selected[["column", "unit", "documented_polling"]])}

Every `features_<split>.parquet` contains **only these three columns**, in this order, as transformed float32 values. No source row ID, timestamp, split, quality flag, availability indicator, target or drivetrain field appears in the feature matrix. No categorical encoding, PCA or inferred energy field is added.

## 5. Battery-specific quality rules

Only selected battery-channel missingness/nonfinite values, SOC outside [0,100], nonpositive or >{config["voltage_review_max"]} V readings, pack-temperature sentinel review cases, impossible battery temperatures and duplicate timestamps block this view. The voltage ceiling is an exploratory screen, not a manufacturer failure limit. Pack values in {config["temperature_sentinel_band"]} °C are unresolved possible sentinels, not established invalid physical temperatures; the existing conservative review across battery sensors 1/2/4 is retained. Peer temperatures do not become model inputs. Motor temperature cannot block a battery row, including missing, negative or impossible motor readings.

No missing battery values or targets are imputed. No sign conversion, clipping, IQR-outlier deletion, interpolation or fabricated values are applied. Negative speed remains negative in metadata. Other original quality observations remain flags. `quality_eligible` is task-specific; `battery_blocking_flags` records overlapping exclusion reasons and `cross_split_repeat` separately records duplicate-screen exclusion. No flag is a confirmed fault label.

## 6. Comparison with the original preparation

{markdown(comparison)}

The original run `{config["parent_run_id"]}` and original six-feature JSON configuration are not written or deleted. All {summary["original_artifacts_verified"]} original artifact files, including the manifest, are checked before and after each run. The new feature view has a separate configuration, hashed artifact directory and report. Existing chunked trip reading, temporal checks, scaling, Parquet writer, sequence indexing and full-output validation are reused; the original split algorithm is not called for this view.

## 7. Train/validation/test row accounting

{markdown(pd.DataFrame(summary["splits"]))}

Source rows = quality exclusions + duplicate-screen exclusions + exported rows for each split. No source rows are deleted. Within-split repeated measurements are preserved. All {audit["quality_excluded_rows"]:,} quality-excluded rows remain in `row_ledger.parquet`; additional duplicate exclusions are flagged there as well. The narrower view makes no statement that all recovered observations are physically valid or healthy.

## 8. Trip coverage and frozen membership

Membership is copied from the original 142/34/51 trip assignments. The pipeline checks exact trip identities, source row counts and timestamp ranges against the frozen parent before accepting membership. Unsafe changes stop execution rather than recomputing boundaries. `frozen_parent_trip_splits.csv` is a byte-identical copy of the original; `trip_splits.csv` records the same membership with this view's quality counts. Retained-trip counts are shown above; source and retained trips are distinct quantities.

## 9. Recording-day coverage

Dates are calculated from actual UTC-represented observations, not inferred dates in recording gaps. Source and retained day counts are shown above and in [split_summary.csv](tables/battery_only/split_summary.csv). One vehicle and unequal historical coverage still limit transfer. The test data influenced the missing-channel investigation; the holdout is now explored even though no model scores have been used. Freeze this policy before further experimentation, and obtain fresh independently held-out data for confirmatory claims.

## 10. Temperature forecasting sequences

Input history: {config["temperature"]["lookback_seconds"]} seconds with {config["temperature"]["tolerance_seconds"]}s boundary tolerance. Anchor spacing: at least {config["temperature"]["stride_seconds"]} seconds. Target: actual logged Pack_1_C_Temp at {config["temperature"]["horizon_seconds"]}–{config["temperature"]["horizon_seconds"] + config["temperature"]["tolerance_seconds"]} seconds after the anchor. Source row cadence is not sensor refresh cadence; the workbook does not establish exact pack refresh timing.

Compact `temperature_<split>.parquet` files contain input start/anchor source IDs, target source ID, corresponding timestamps, Trip/segment/split and the unchanged future temperature. Targets remain outside the three-column feature matrix. Use `metadata_<split>.parquet` to map source IDs to feature-row positions; fetch only IDs from input_start_row through anchor_row inclusive. Never append target values or future feature rows to X. Targets and temperature changes are not scaled or imputed. Windows have variable observed row counts; no dense repeated arrays or synthetic samples are created.

A window cannot cross a trip, split or >{config["gap_seconds"]}s gap, and its interval through the target must contain only eligible rows. This future-interval quality screen is selection for dataset validity, not a future input; it can bias coverage toward cleaner intervals. Windows may overlap within a split, so later evaluation must account for temporal dependence. `{summary["window_accounting"]}`.

## 11. Exclusion reasons and audit metadata

{markdown(flags)}

Counts overlap. Only rows whose blocking bits are nonzero are quality-excluded. The all-row ledger contains original selected/context values and audit flags; excluded records are inspectable without a redundant quarantine copy. Companion metadata is aligned one-to-one, in order, with each feature matrix and contains source row, exported index, original timestamp, Trip, split, segment, flags, quality status and source path. `no_configured_row_flags` is not a healthy label; `retained_with_review_flags` can include unavailable drivetrain telemetry.

## 12. Duplicate screening

Screening uses the same configured rounding resolutions applied to this view's three columns. Later-split states matching any earlier-split quality-eligible state are withheld; this is rerun on the actual selected feature set. The battery-only exact uint64 membership lookup is optimized, but semantically equivalent to the existing set-based lookup. Hash collisions could conservatively overexclude; rounding is not an exhaustive near-neighbor search or proof of independence. With fewer dimensions, additional coincident battery states are expected and need not be faults.

Observed split exclusions: `{summary["cross_split_repeat_screen"]}`. Comparison with independently investigated reference counts: `{summary["reference_comparison"]}`. Zero differences mean reproduced counts, not hardcoded counts. Differences, if any, must be reviewed rather than adjusted to reach the reference.

## 13. Training-only preprocessing

Configured scaling: `{config["scaling"]}`. Robust default fits training medians and interquartile ranges; zero ranges use 1 and are recorded. Exactly {summary["transformer"]["fit_rows"]:,} retained training observations contribute. Validation/test inputs receive those frozen statistics with no refit. Standard or no scaling remain configurable; this three-input release intentionally disallows imputation/indicator expansion. Fitted feature order, centers, scales and fit scope are exported as JSON. Serialization/reload preserves order. Independent output validation recomputes the training statistics and checks every transformed output against the frozen artifact.

## 14. Leakage validation

`{summary["validation"]}`

Full-data checks cover original split membership, companion alignment, source lineage, training-only preprocessing, no rounded-feature overlap between splits, window horizons, safe segments and exact observed targets. The chronological embargo remains {config["split_embargo_seconds"]} seconds minimum. No raw/preprocessed mixing occurs. Computational leakage controls do not establish independent vehicles or erase policy selection after test-data inspection.

## 15. Artifact paths and checksums

New artifact directory: `{summary["artifact_directory"]}`. Original: `{old["artifact_directory"]}`. Large Parquet files stay under the existing Git-ignore rule. Manifest contains input/code/config/parent hashes and exact output sizes, hashes and schemas. [artifact_inventory.csv](tables/battery_only/artifact_inventory.csv) lists every output SHA-256; [OUTPUT_SCHEMAS.md](tables/battery_only/OUTPUT_SCHEMAS.md) records exact schemas. [summary.json](tables/battery_only/summary.json) is the trackable manifest copy. Models, fault labels and energy targets are not artifacts.

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
"""
    (base / "BATTERY_ONLY_PREPARATION_REPORT.md").write_text(report)
