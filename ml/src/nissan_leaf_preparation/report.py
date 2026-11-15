"""Render preparation decisions, measured accounting, schemas and reproducibility notes."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from .core import FLAGS, save_json


def markdown(frame: pd.DataFrame) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "/").replace("\n", " ")

    return "\n".join(
        [
            "| " + " | ".join(map(cell, frame.columns)) + " |",
            "| " + " | ".join(["---"] * len(frame.columns)) + " |",
            *[
                "| " + " | ".join(map(cell, row)) + " |"
                for row in frame.itertuples(index=False, name=None)
            ],
        ]
    )


def write_report(summary: dict, directory: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    base = root / "ml/reports/nissan_leaf_2018"
    tables = base / "tables/preparation"
    tables.mkdir(parents=True, exist_ok=True)
    c = summary["config"]
    audit = summary["audit"]
    flags = pd.DataFrame(
        [
            {
                "flag": name,
                "bit": bit,
                "category": category,
                "meaning": meaning,
                "raw_rows": audit["raw"]["flag_counts_overlapping"][name],
                "processed_rows": audit["processed"]["flag_counts_overlapping"][name],
            }
            for name, (bit, category, meaning) in FLAGS.items()
        ]
    )
    flags.to_csv(tables / "quality_audit.csv", index=False)
    missing = pd.DataFrame(
        [
            {
                "version": version,
                "column": name,
                "missing_rows": count,
                "missing_pct": count / a["rows"] * 100,
                "selected_input": name in c["features"],
            }
            for version, a in audit.items()
            for name, count in a["missing_counts"].items()
        ]
    )
    missing.to_csv(tables / "missingness.csv", index=False)
    inventory = pd.read_csv(base / "tables/readiness/feature_inventory.csv")
    selection = inventory[inventory.source_dataset.eq("raw")][
        ["column", "description", "unit", "documented_polling"]
    ].copy()
    reasons = {
        "RPM": "Redundant with Speed; use Speed in conservative view",
        "HV_Bat_Current_2": "Current polarity unresolved; retain original in audit, do not integrate energy",
        "HV_Bat_Current_1": "Current polarity unresolved",
        "Ambient_C_Temp": "Celsius/Fahrenheit conflict unresolved",
        "Brake": "Physical units undocumented; keep in audit only",
        "Acc_Pedal": "Physical units undocumented; keep in audit only",
        "SOH": "Slow aging/identity shortcut, not a fault label",
        "Odometer": "Aging shortcut and discontinuities; audit only",
        "Instant_kW": "Derived; polarity/energy-accounting unresolved",
        "Horsepower": "Deterministic power conversion, not independent mechanical output",
        "Pack_Avg_C_Temp": "Derived/redundant; select documented component target instead",
        "Pack_2_C_Temp": "Highly correlated with Pack 1; consistency/sentinel audit only",
        "Pack_4_C_Temp": "Highly correlated with Pack 1; consistency/sentinel audit only",
        "Trip": "Grouping key, never an input",
        "Timestamp": "Temporal key, never scaled as a measurement",
        "index": "Original exported ID, audit only",
    }
    selection["selected"] = selection.column.isin(c["features"])
    selection["reason"] = selection.column.map(reasons).fillna(
        "Not selected: outside conservative documented measurement scope; see readiness inventory"
    )
    selection.loc[selection.selected, "reason"] = (
        "Documented unit; usable only under explicit quality exclusions; no claim of physical validation"
    )
    selection.to_csv(tables / "feature_selection.csv", index=False)
    for name in [
        "trip_splits.csv",
        "segments.csv",
        "window_accounting.csv",
        "training_horizon_feasibility.csv",
    ]:
        shutil.copyfile(directory / name, tables / name)
    pd.DataFrame(summary["splits"]).to_csv(tables / "split_summary.csv", index=False)
    save_json(tables / "preparation_summary.json", summary)
    save_json(tables / "transformer.json", summary["transformer"])
    save_json(
        tables / "sequence_specification.json",
        {
            **c["temperature"],
            "input_features": c["features"],
            "inputs": "All observed eligible rows from input_start_row through anchor_row inclusive; never include target_row in input",
            "target": "Actual future recorded Pack_1_C_Temp at [horizon,horizon+tolerance], Celsius; not imputed",
            "raw_lookup": "row_ledger.parquet indexed by source_row",
            "scaled_lookup": "features_<split>.parquet keyed by source_row; only transformer.output_features are model inputs",
            "within_split_overlap": "Permitted; evaluation must account for dependent windows",
            "across_split_overlap": "Forbidden and checked",
            "sampling": "Variable-length observed sequences; no regular grid or interpolation",
            "sensor_refresh": "Unknown; forecast is a logged reading, not guaranteed fresh sensor truth",
        },
    )
    output_table = pd.DataFrame(
        [
            {
                "artifact": name,
                "bytes": info["bytes"],
                "rows": info["rows"] if info["rows"] is not None else "metadata",
            }
            for name, info in summary["outputs"].items()
        ]
    )
    output_table.to_csv(tables / "output_inventory.csv", index=False)
    for info in summary["outputs"].values():
        if info["schema"]:
            break
    schema_text = "\n\n".join(
        f"### {name}\n\n```text\n{info['schema']}\n```"
        for name, info in summary["outputs"].items()
        if info["schema"]
    )
    (tables / "OUTPUT_SCHEMAS.md").write_text(
        "# Prepared artifact schemas\n\nPurpose: exact Arrow schemas; identifiers are join keys, never ordinary model inputs.\n\n"
        + schema_text
        + "\n"
    )
    feature_names = ", ".join(c["features"])
    split_table = markdown(pd.DataFrame(summary["splits"]))
    audit_rows = markdown(
        pd.DataFrame(
            [
                {
                    "version": v,
                    **{
                        k: a[k]
                        for k in [
                            "rows",
                            "flagged_rows_any_flag",
                            "no_row_flags",
                            "quality_eligible_rows",
                            "quality_excluded_rows",
                        ]
                    },
                }
                for v, a in audit.items()
            ]
        )
    )
    report = f"""# Nissan Leaf Phase 1 — Data preparation report

Purpose: document reproducible, conditional experimental datasets without training models or changing source telemetry. Run ID: `{summary["run_id"]}`. Raw data, preprocessing artifacts and prepared outputs are distinct.

## 1. Source datasets and provenance

Primary input: `data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv` (2,322,105 rows, 92 columns). Comparison audit only: `data/nissan_leaf_2018/processed/Dataset_Preprocessed.csv` (1,918,299 rows, 32 columns). Both source hashes, workbook and archived source page are verified against [download_manifest.json](metadata/download_manifest.json). Source bytes are never written. Dataset published by Macao Polytechnic University, [official source](https://ubilab.mpu.edu.mo/data.html).

Existing [EDA](EDA_REPORT.md), [readiness assessment](ML_READINESS_REPORT.md), workbook dictionary and readiness inventory informed the policy. The workbook was read using the existing extraction utility before implementation. Raw is chosen because processed fields show unexplained changes and derived-formula disagreements. Raw also includes publisher-derived columns, which are not selected. No claim is made that all publisher processing is known or causal.

Both releases overlap in 1,886,696 exact timestamps. They are never pooled or used as independent train/test sources. No new download or physical ground truth was obtained. Licensing uncertainty remains.

## 2. Preparation architecture

`ml/src/nissan_leaf_preparation/` contains reusable quality, temporal, split, transformation, window, export and independent validation functions. `ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py` is the CLI. JSON configuration lives at `ml/notebooks/nissan_leaf_2018/config/preparation.json`.

CSV scans read {c["chunk_rows"]:,} rows per chunk and carry one incomplete trip. Audit Parquet writes one trip per row group. Exact robust statistics load only retained training input columns; independent output validation reads a selected-column ledger, not the full 92-column source. No dense sliding-window tensors are duplicated: sequence indices reference existing feature rows. Output source/config/code/library fingerprints determine the run ID. Re-execution builds a separate temporary result and requires identical output hashes before reusing an existing run directory; incomplete runs are not published as complete.

## 3. Quality audit findings

{audit_rows}

Flags overlap; do not sum their counts as unique rows. `no_row_flags` means no configured row-level issue found, **not verified healthy**. Global unresolved current/ambient semantics apply even to rows without flags, so those channels are excluded from inputs altogether. Processed eligibility counts are audit-only hypothetical policy counts; no processed feature matrix is exported.

{markdown(flags)}

## 4. Cleaning policies

No numerical source corrections, outlier clipping, recomputation of stored fields or silent row deletion occur. All raw rows survive in `row_ledger.parquet` with original values, source row offsets, exported index, Trip, Timestamp, segment, split, flags and eligibility. Any raw row excluded from features remains inspectable there. Processed flagged rows are indexed separately against their unchanged CSV.

Selected-feature missing/infinite values, invalid SOC-domain values, negative speed, voltage review cases, narrow pack sentinel-band cases, impossible temperatures and duplicate timestamps are excluded under the configured policy. Flags on unselected tire pressure, odometer, SOH and derived fields remain contextual and do not independently remove usable feature rows. Retaining flagged data is intentional; flags are not fault labels. No statistical IQR outlier rule removes observations.

## 5. Missing-value handling

Every scanned candidate/context column has counts in [missingness.csv](tables/preparation/missingness.csv). Default policy: `{c["missing_policy"]}`. No forward fill, interpolation, temporal averaging or invented target values is used. The optional `training_median` policy fits medians only on eligible training rows and exports one missingness indicator per feature; the original missing measurements remain missing in the ledger. Imputed inputs would be computational substitutes, never newly measured observations. No median target imputation is implemented.

The actual run used no imputation. Raw SOH missingness is flagged independently despite SOH being excluded as an input. There is no blanket -1 replacement: negative torque may be valid; -1 in documented status codes can mean off.

## 6. Invalid and suspicious measurement policies

Verified-rule invalidity is limited to unrepresentable/nonfinite selected values, SOC outside its documented percentage domain, temperatures below absolute zero, or duplicate temporal keys unsuitable for sequence use. Invalid signal-domain values can still encode missingness rather than hardware faults.

Voltage threshold {c["voltage_review_max"]} V is an exploratory review screen, not a manufacturer limit. Nonpositive voltage and negative speed are suspicious/unresolved codes, not automatically confirmed sensor defects. Pack values in {c["temperature_sentinel_band"]} °C are conservatively withheld as unresolved possible sentinel values; genuine readings in this band may also be excluded. This selection bias must be reviewed. Motor -40°C is not excluded merely because it is an extreme. Tire zeros, odometer decreases/jumps and raw zero SOH are flagged without correction. Power and mean-temperature formulas are audited with configured atol/rtol {c["formula_atol"]}/{c["formula_rtol"]}; formula consistency alone does not verify sensor truth.

No current sign flip, ambient temperature conversion, speculative pedal units or energy integration is performed.

## 7. Temporal segmentation

Microsecond epoch timestamps are parsed as UTC; original integers are preserved. Missing/unparseable timestamps, source time reversals or reused noncontiguous Trip IDs stop the pipeline for review rather than silently merging or sorting ambiguous journeys. Existing source rows are already ordered. Duplicate timestamps are flagged/excluded and break segments on both sides.

A new segment begins at every trip boundary and every gap >{c["gap_seconds"]} second. Justification: observed median interval 0.25s and p99 about 0.75s. The configurable {c["typical_interval_band_seconds"]}s band is a descriptive irregularity flag only. Neither row cadence nor value-change frequency establishes sensor refresh frequency. Workbook channels have differing polling intervals, and pack update cadence is unknown. No interpolation across gaps occurs. Every segment's rows and duration are saved in [segments.csv](tables/preparation/segments.csv).

## 8. Chronological split strategy

Boundaries minimize deviation from requested {c["split_fractions"]} cumulative source-row fractions among whole-trip boundaries on different UTC dates with at least {c["split_embargo_seconds"]} seconds separation. The embargo covers lookback+horizon+tolerance. Trip interval overlaps or unavailable defensible boundaries stop preparation; no random fallback exists. Splits are chosen before feature filtering, without targets, so retained proportions need not equal 70/15/15.

{split_table}

All original raw rows receive exactly one whole-trip split, including quality-excluded rows. Row ledger eligibility determines later exports. The cross-split repeat screen rounds the six-feature vectors using the configured decimal resolutions, hashes them, and withholds matching states from later splits while retaining audit records. It does not remove repeated measurements within a split. This prevents exact/rounded-vector contamination under that explicit definition; hash collisions could conservatively overexclude. A rounding grid is not a complete near-neighbor search, and matching real operating states can be legitimate. Same-vehicle dependence and near-neighbors outside the screen remain limitations.

No trip, timestamp interval or input/target window crosses splits. Neighboring windows can overlap within one split; future metrics must aggregate by trip/time block and must not treat windows as independent vehicles. Temporal separation and screening do not prove population independence.

## 9. Feature-selection decisions

Ordered input vector: **{feature_names}**. All are documented measurement channels with units in the workbook. One pack temperature and Speed are retained to reduce pack-channel and RPM redundancy. Torque's negative values are preserved because sign is meaningful; it is not energy consumption.

{markdown(selection[selection.selected | selection.column.isin(["RPM", "HV_Bat_Current_2", "Ambient_C_Temp", "Brake", "Acc_Pedal", "SOH", "Odometer", "Instant_kW", "Horsepower", "Pack_Avg_C_Temp", "Pack_2_C_Temp", "Pack_4_C_Temp"])])}

All 92 raw columns have a selection decision in [feature_selection.csv](tables/preparation/feature_selection.csv). IDs/timestamps/context remain in the ledger, outside the transform feature order. Each `features_<split>.parquet` has `source_row` solely as a join key; consumers must select `transformer.output_features` rather than treating all numeric file columns as inputs. Raw values are accessible through the ledger. Status/context is not encoded into the default model-input matrix; moving/stationary/unknown is descriptive, not a diagnosis or verified charging state.

## 10. Anomaly detection dataset readiness

**Conditional, successfully exported for controlled telemetry experiments.** Six scaled features, frozen transformation metadata, original-value access, quality flags and chronological assignments are available. There are no anomaly or healthy labels. Training describes the selected recorded telemetry, not a certified healthy reference. Unsupported units/current channels are excluded. Withheld quality/repetition cases remain auditable. Do not call future unusualness scores fault probabilities or production diagnostics.

## 11. Energy prediction dataset readiness

**Blocked; zero energy-label or energy-training files exported.** Current magnitude is documented in A and voltage in V, and raw power equals their product/1000. However, observed current polarity conflicts with documented discharge direction. Charge_Mode lacks documented active-charge codes; regenerative braking and charging cannot be reliably separated. Nominal-energy/SOC/AHr calculations are not independent consumption truth. Odometer discontinuities further undermine energy-per-distance labels. Integrating an internally consistent but semantically uncertain power signal would manufacture an unsupported target. Researcher confirmation and independently verified energy accounting are required first.

## 12. Battery temperature forecasting readiness

**Conditional, successfully exported as compact observed-sequence indices.** Target: logged `Pack_1_C_Temp` at {c["temperature"]["horizon_seconds"]}–{c["temperature"]["horizon_seconds"] + c["temperature"]["tolerance_seconds"]} seconds after the anchor, in documented °C. Temperature change is also recorded as target minus the current observed reading. Inputs end at the anchor and cover approximately the preceding {c["temperature"]["lookback_seconds"]} seconds. Anchors are at least {c["temperature"]["stride_seconds"]} seconds apart. Targets are actual observed rows, never interpolated or scaled labels. Pack 1 avoids reliance on a computed mean; component/mean consistency is audited separately.

A window is exported only if its entire interval through the target stays within one segment/trip/split and contains no excluded row. This deliberately conservative future-interval quality filter can bias the dataset toward cleaner, more continuous operation; it is dataset eligibility, not an input feature. No future measurement is included in X. Targets may repeat because the physical reading or polling state stayed constant. This predicts a future logged value, not independently validated future battery thermal state. Unknown refresh/calibration and raw-export provenance keep status conditional.

Training-only feasibility counts for 30/60/120-second horizons are in [training_horizon_feasibility.csv](tables/preparation/training_horizon_feasibility.csv). The configured 60-second horizon was chosen before inspecting test results, as a short prototype interval relative to slower signals. Missing sensor cadence prevents claiming an optimal horizon. Rejected anchors are accounted for by trip in [window_accounting.csv](tables/preparation/window_accounting.csv): `{summary["window_accounting"]}`. These anchor counts differ from source-row counts.

Consumer rule: retrieve only `source_row` values from `input_start_row` through `anchor_row` inclusive from the corresponding feature file; look up the separate future target from the sequence table. Do not concatenate target columns into input features. Windows use observed, variable-length sequences without resampling. The full contract is [sequence_specification.json](tables/preparation/sequence_specification.json).

## 13. Fitted transformations

Default `{c["scaling"]}` scaling uses training median and training interquartile range; zero IQR uses scale 1 and is recorded. No clipping or outlier removal is implied. Optional standard scaling uses training mean and population standard deviation; `none` preserves numeric inputs. The fitted artifact records feature order, medians, centers, scales, fit rows and policy. Parameters are JSON, avoiding unsafe opaque deserialization. No transformations use validation/test rows or future targets. No PCA, target scaling, learned encodings or model fitting occurs. `{summary["transformer"]["fit_rows"]}` training rows contributed to this run's transformation.

## 14. Output dataset sizes and schemas

Artifacts: `{summary["artifact_directory"]}` (already Git-ignored). Trackable tables/report remain under `ml/reports/nissan_leaf_2018/`. No large files are added to Git.

{markdown(output_table)}

Exact Arrow schemas: [OUTPUT_SCHEMAS.md](tables/preparation/OUTPUT_SCHEMAS.md). The artifact manifest contains byte sizes and SHA-256 hashes. The row ledger includes all raw observations and selected audit/context fields, not a copy of all 92 original columns. Excluded observations are accessed through eligibility flags; no additional full quarantine copy is necessary.

## 15. Remaining blockers

Current polarity, charging/regeneration identity, true energy accounting, ambiguous ambient/pedal units, sentinel interpretation, actual sensor refresh, calibration, raw acquisition processing and single-vehicle generalization remain unresolved. Proposed quality thresholds are review policies with selection bias, not diagnoses. Independently verified fault labels and healthy controls are absent. Sensor freshness cannot be inferred from identical repeated values. No production-readiness claim is supported.

## 16. Validation results

Independent full-output checks: `{summary["validation"]}`. These check actual row provenance, split exclusivity/embargo, cross-split rounded-feature overlap, frozen-transform application, window segment/quality/horizon constraints and exact source target lookup. Unit and regression test execution results, lint and repeated-run verification are recorded in [PREPARATION_VALIDATION.md](PREPARATION_VALIDATION.md) after execution; this report does not substitute inferred test results.

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
"""
    (base / "DATA_PREPARATION_REPORT.md").write_text(report)
