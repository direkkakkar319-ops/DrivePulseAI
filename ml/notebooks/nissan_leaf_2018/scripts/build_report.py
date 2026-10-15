"""Build the complete nine-section EDA report from measured tables and source notes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from acquire import BASE, DATA, ROOT, sha256


def read(relative: str) -> dict:
    return json.loads((BASE / relative).read_text())


def md(frame: pd.DataFrame) -> str:
    def cell(value: object) -> str:
        if pd.isna(value):
            return "Unknown"
        if isinstance(value, float):
            return f"{value:.8g}"
        return str(value).replace("|", " / ").replace("\n", " ")

    return (
        "\n".join(
            [
                "| " + " | ".join(map(str, frame.columns)) + " |",
                "| " + " | ".join(["---"] * len(frame.columns)) + " |",
            ]
            + [
                "| " + " | ".join(cell(v) for v in row) + " |"
                for row in frame.itertuples(index=False, name=None)
            ]
        )
        + "\n"
    )


def main() -> None:
    p = read("tables/processed/overview.json")
    r = read("tables/raw/overview.json")
    comparison = read("tables/raw_processed_comparison.json")
    alignment = read("tables/raw_processed_timestamp_alignment.json")
    manifest = read("metadata/download_manifest.json")
    validation = read("validation_results.json")
    assert validation["all_passed"]
    lines = [
        "# 2018 Nissan Leaf — complete acquisition, validation and EDA report\n",
        "**Status: completed on both downloaded CSVs. No model training, feature selection, imputation, deletion or source-file modification was performed.**\n",
        "Open this file in VS Code and press **Ctrl+Shift+V** to view the tables and plots. The 2018 designation is the vehicle model year, not the year of all recordings.\n",
        "## 1 — Dataset overview\n",
        "Source: [UbiLab, Macao Polytechnic University](https://ubilab.mpu.edu.mo/data.html), MPU–UCLA Joint Research Center in Ubiquitous Computing. Both telemetry files and the parameter workbook were downloaded successfully from their official URLs. The preserved source page and workbook are the primary documentation. The official collection description refers to one Nissan Leaf; the CSVs have no VIN or other documented vehicle identifier allowing independent fleet verification.\n",
        "The website advertises a broader 4.5-million-sample collection covering November 2020–December 2021. The downloaded files have different row counts and extend into 2022; measured file contents take precedence over that description. No semantic release version is given. The telemetry HTTP Last-Modified dates are 2 April 2023; SHA-256 fingerprints below identify this snapshot.\n",
        "**License:** no explicit dataset license was found in the source page or workbook. Research citation is requested; unrestricted reuse or redistribution is not established. See [sources and rights](metadata/SOURCES.md).\n",
    ]
    files = pd.DataFrame(
        [
            {k: e.get(k, "Unknown") for k in ["filename", "url", "bytes", "sha256"]}
            for e in manifest["files"]
            if "filename" in e
        ]
    )
    lines.append(md(files))
    lines.append(
        "The CSVs are uncompressed: downloaded and uncompressed sizes are identical. The workbook is a 28,139-byte XLSX ZIP container with 192,845 bytes of uncompressed members. Source-file checksums are local integrity fingerprints, not independently published publisher checksums.\n"
    )
    lines.append(
        "**Access limitation:** the optional monitoring-paper PDF returned HTTP 403 at both institutional direct URLs. No PDF was saved. Its institutional landing page was readable; exact failures and browser access instructions are in [access_log.json](metadata/access_log.json). Dataset downloads succeeded using direct curl after browser-fetch/DNS issues.\n"
    )
    lines.append("## 2 — Dataset dimensions\n")
    dims = []
    for a in [p, r]:
        roles = a["semantic_roles"]
        dims.append(
            {
                "Version": a["version"],
                "Rows": a["rows"],
                "Columns": a["columns"],
                "Numeric storage": a["numeric_storage_columns"],
                "Text storage": a["text_storage_columns"],
                "Numeric measurements/derived (semantic)": roles[
                    "numeric_measurement_or_undocumented"
                ]
                + roles["derived_numeric"],
                "Categorical status (numeric-coded)": roles["categorical_status"],
                "Timestamp columns": roles["timestamp"],
                "Identifiers/export indices": roles["identifier_or_export_index"],
                "Fault-label columns": 0,
                "Distinct Trip values": a["trip_ids"],
                "Parsed-data memory bytes": a["estimated_pandas_data_memory_bytes"],
            }
        )
    lines.append(md(pd.DataFrame(dims)))
    lines.append(
        "Storage datatypes and semantic roles are different classifications. For example ECO is stored numerically but is a status code, and Timestamp is an integer time representation. **These are dataset columns, not a selected ML input-feature set.** No features or prediction target were selected. SOH is an observed ECU health indicator, not verified failure ground truth.\n"
    )
    lines.append(
        "Processed identifiers: `index`, `Driver_ID` (7 distinct codes), `Trip`. Raw identifiers/export fields: the blank header (Pandas alias `Unnamed: 0.1`), `Unnamed: 0`, `index`, `id`, `Trip`. Their full definitions and Driver_ID mapping are not supplied. Trip counts mean supplied IDs, not independently verified uninterrupted sessions; within-trip gaps remain. Raw lacks Driver_ID.\n"
    )
    lines.append("## 3 — Complete column dictionary\n")
    lines.append(
        "Every column is listed below. Dtype lists show types inferred across CSV chunks; all numeric analysis uses float64 disk-backed arrays without rewriting source files. Unknown means the workbook does not establish the definition/unit. Aliases and inferred roles are recorded separately in the CSV dictionaries. The raw file has one blank header and no repeated literal header names; the blank is displayed as `<empty header>` below.\n"
    )
    for version in ["processed", "raw"]:
        d = pd.read_csv(
            BASE / f"tables/{version}/column_dictionary.csv", keep_default_na=False
        )
        d.loc[d.original_header.eq(""), "original_header"] = "<empty header>"
        subset = d[
            [
                "original_header",
                "column",
                "dtype",
                "description",
                "unit",
                "missing_pct",
                "unique_values",
            ]
        ].rename(
            columns={
                "original_header": "Original column name",
                "column": "Analysis name",
                "dtype": "Data type",
                "description": "Description",
                "unit": "Unit",
                "missing_pct": "Missing %",
                "unique_values": "Unique values",
            }
        )
        lines.extend([f"### {version.capitalize()} — all columns\n", md(subset)])
    lines.append(
        "`Pack_Avg_C_Temp`, `kWh_Remaining`, `Driver_ID`, `Trip`, accumulated fields and calendar encodings are not fully defined under those exact names in the workbook. The formulas examined below provide evidence for some derived relationships, not complete metadata. Battery-cell extrema names alone do not establish their scale.\n"
    )
    lines.append("## 4 — Data quality\n")
    quality = []
    for a in [p, r]:
        quality.append(
            {
                "Version": a["version"],
                "Missing cells": a["total_missing_cells"],
                "Missing cells %": 100
                * a["total_missing_cells"]
                / (a["rows"] * a["columns"]),
                "All-empty columns": ", ".join(a["all_missing_columns"]) or "None",
                "Constant nonmissing columns": ", ".join(a["constant_columns"])
                or "None",
                "Exact full-row duplicates": a["duplicates"]["exact_full_rows"],
                "Duplicate epoch timestamps": a["duplicates"][
                    "duplicate_timestamp_rows"
                ],
                "Repeated measurement rows": a["duplicates"][
                    "duplicate_measurement_rows_excluding_ids_times_derived"
                ],
            }
        )
    lines.append(md(pd.DataFrame(quality)))
    lines.append(
        "Repeated-measurement counts exclude timestamps, IDs and derived variables and use each version’s own available measurement set; they are **not directly comparable counts over identical columns**. Repeated readings can be normal because sensors are polled at different intervals or the vehicle state stays constant. No duplicates were deleted. Full-row duplicate screening uses hashes, with candidate rows confirmed against original records; numeric measurement candidates are confirmed elementwise including missingness. No identical trip-sequence hashes or overlapping trip time ranges were found. This screen does not prove independence or exclude partly copied sessions.\n"
    )
    lines.append(
        "Near-constant means at least 99% of nonmissing values are identical. Raw near-constant columns (including constants): "
        + ", ".join("`" + c + "`" for c in r["near_constant_99pct_columns"])
        + ". Processed has none under that rule.\n"
    )
    raw_missing = pd.read_csv(BASE / "tables/raw/missing_values.csv")
    lines.extend(
        [
            "### Raw missingness and consecutive runs\n",
            md(raw_missing[raw_missing.missing_count > 0]),
        ]
    )
    lines.append(
        "Missingness uses Pandas CSV NA parsing. Runs are broken at trip changes, timestamp reversals/repeats and gaps >1 second; reported duration is first-to-last observed timestamp, not an inferred period with no packets. `missing_patterns.csv` lists every observed co-missing pattern. The workbook explicitly states Pack 3 is absent on this model variant; not every empty column is a broken sensor.\n"
    )
    for version in ["processed", "raw"]:
        q = pd.read_csv(BASE / f"tables/{version}/data_quality_findings.csv")
        lines.extend(
            [
                f"### {version.capitalize()} observations requiring attention\n",
                md(
                    q[q.severity != "statistical_observation"][
                        ["severity", "column", "rule", "count", "interpretation"]
                    ]
                ),
            ]
        )
    lines.append(
        "Statistical outliers use values outside Q1 − 1.5×IQR or Q3 + 1.5×IQR on all finite rows, per numeric measurement/derived column. They are screening observations, **not invalid-value or fault labels**. With zero IQR every deviation can be flagged; categorical codes, timestamps and IDs are excluded from outlier interpretation. Full counts and fences are in each summary table. Zero/negative pressure, invalid binary codes and odometer discontinuities are investigated separately. No blanket −1 replacement is valid: the workbook defines −1 as “off” for multiple controls, while −1 in speed/pressure is suspicious. No unsupported universal 999 sentinel rule was applied.\n"
    )
    lines.append("![Raw missingness](figures/raw/missing_values.png)\n")
    lines.append("## 5 — Statistical findings\n")
    lines.append(
        "The per-version `summary_statistics.csv` files contain count, finite count, mean, median, sample standard deviation and variance (ddof=1), extrema, quartiles, 1st/5th/95th/99th percentiles, unique counts and skewness where more than two distinct finite values exist. IDs and numeric timestamps are retained for completeness but not treated as physical sensors. No infinite nonmissing values or failed numeric conversions were detected in this run; see integrity tables.\n"
    )
    ps = pd.read_csv(BASE / "tables/processed/summary_statistics.csv")
    lines.extend(
        [
            "### Selected preprocessed measurements\n",
            md(
                ps[
                    ps.column.isin(
                        [
                            "Speed",
                            "RPM",
                            "SOC",
                            "SOH",
                            "Odometer",
                            "HV_Bat_Voltage",
                            "HV_Bat_Current_2",
                            "Pack_Avg_C_Temp",
                            "Ambient_C_Temp",
                        ]
                    )
                ][
                    [
                        "column",
                        "mean",
                        "median",
                        "std_ddof1",
                        "min",
                        "max",
                        "skewness",
                        "iqr_outlier_count",
                    ]
                ]
            ),
        ]
    )
    lines.append(
        "![Preprocessed distributions](figures/processed/distributions.png)\n![Preprocessed box plots](figures/processed/boxplots_sampled.png)\n"
    )
    lines.append(
        "Histograms use all finite observations. Separate `all_numeric_distributions_*.png` pages cover every numeric measurement/derived column, including those not in the overview plot. Boxplots use deterministic evenly spaced source-order samples (about 50,000 values per column) and are labelled as such; the numerical outlier counts remain full-data counts. Repeated/quantized signals, long tails and spikes are visible; none was removed.\n"
    )
    lines.append("### Correlations\n")
    lines.append(
        "Pearson matrices use 19 selected varying telemetry/derived columns and pairwise complete observations over all rows. Export IDs, timestamps, arbitrary accumulated/calendar fields and status codes are not included. Strong pairs mean |r| ≥ 0.8; sample counts are provided. No causal conclusion follows from these associations, and temporal dependence weakens any independent-sample interpretation.\n"
    )
    lines.append(md(pd.read_csv(BASE / "tables/processed/strong_correlations.csv")))
    lines.append(
        "![Preprocessed correlations](figures/processed/correlation_heatmap.png)\n"
    )
    lines.append(
        "Horsepower and Instant_kW are deterministically related. Pack temperatures and their derived average overlap strongly; speed/RPM correlation reflects coupled vehicle motion. SOH/odometer association can reflect shared elapsed use and does not establish the cause of battery degradation.\n"
    )
    lines.append("### Time-series characteristics\n")
    time_rows = []
    for a in [p, r]:
        t = a["time"]
        time_rows.append(
            {
                "Version": a["version"],
                "Earliest (UTC interpretation)": t["earliest_utc_interpretation"],
                "Latest": t["latest_utc_interpretation"],
                "Calendar span days": t["span_days"],
                "Median within-trip positive delta s": t[
                    "within_trip_positive_interval_quantiles_seconds"
                ]["0.5"],
                "Within-trip gaps >1s": t["within_trip_gaps_over_1s"],
                "Largest within-trip positive gap s": t[
                    "within_trip_positive_interval_quantiles_seconds"
                ]["1"],
                "Reversals": t["global_reversals"],
                "Sum of positive within-trip intervals <=1s, hours": t[
                    "within_trip_observed_contiguous_seconds_max_gap_1s"
                ]
                / 3600,
            }
        )
    lines.append(md(pd.DataFrame(time_rows)))
    lines.append(
        "Calendar span is not continuous recording duration. The interval sum is an explicitly bounded coverage proxy, not exact driving time. The smallest positive interval is 2 microseconds in both files, despite a median of 250 ms. Trip boundary and gap records are retained; no sorting, interpolation or resampling was done.\n"
    )
    lines.append(
        "Timestamp is interpreted as Unix microseconds. Raw DateTime uses day-month-year text with fractional seconds; Timestamp_Object uses ISO-like UTC text at second resolution. All parse successfully. DateTime can differ from the microsecond epoch by up to 9 microseconds. Timestamp_Object differs by up to 0.999767 seconds and has only 641,664 distinct instants, so it must not replace the full-resolution Timestamp as a unique row key. Its repeated values reflect coarser precision, not duplicate telemetry rows.\n"
    )
    lines.append(
        "The workbook documents 250 ms battery group polling, 1 s speed/RPM/torque, and 10 s or 100 s for several slower fields. Value-change frequency (`measurement_updates.csv`) cannot prove sensor refresh rate because true values can remain constant.\n"
    )
    lines.append(
        "![Sampling intervals](figures/processed/sampling_intervals.png)\n![Representative trip](figures/processed/telemetry_timeseries.png)\n"
    )
    lines.append("## 6 — Vehicle telemetry findings\n")
    lines.append(
        "Available in both files: speed, motor RPM/torque/temperature, odometer, SOC, SOH, HV voltage/current, three pack temperatures, tire pressures, auxiliary/AC power, brake and accelerator signals, ECO/ePedal status, and derived power/energy/temperature fields. Raw additionally provides AHr, Hx, 12 V battery voltage/current, charge counters/modes, plug state and cabin controls, with varying data quality. Complete ranges, meanings and units are in the dictionary and statistics tables.\n"
    )
    rs = pd.read_csv(BASE / "tables/raw/summary_statistics.csv")
    lines.append(
        md(
            rs[
                rs.column.isin(
                    [
                        "AHr",
                        "Hx",
                        "Bat_12V_Voltage",
                        "Bat_12V_Current",
                        "Quick_Charge",
                        "L1_L2_Charge",
                        "OBC_Out_Pwr",
                        "CellMaxVolt",
                        "CellMinVolt",
                    ]
                )
            ][["column", "count", "min", "median", "max", "unique_values"]]
        )
    )
    lines.append("### Charging and sign conventions\n")
    lines.append(md(pd.read_csv(BASE / "tables/raw/charging_modes.csv")))
    lines.append(
        "Charge_Mode contains only 0 (documented not charging) and −1 (undocumented). There are no documented active-charge codes 1/2/3 in this download. That does not prove charging never occurred: OBC power has inconsistent nonzero values, and unavailable/stale codes are possible. Charge counters describe historical connections, not complete charging-event records. The workbook says HV current is positive for discharge and negative for regeneration/charging, but negative current dominates even among moving rows; polarity/acquisition consistency needs researcher confirmation. Do not identify charging events from current sign alone.\n"
    )
    lines.append(md(pd.read_csv(BASE / "tables/processed/current_sign_context.csv")))
    lines.append("### Derived-field consistency\n")
    for version in ["processed", "raw"]:
        lines.extend(
            [
                f"**{version.capitalize()}**\n",
                md(
                    pd.read_csv(
                        BASE / f"tables/{version}/derived_relationship_checks.csv"
                    )
                ),
            ]
        )
    lines.append(
        "All three tested relationships hold within tolerance in raw. In processed, 30,057 power rows differ from voltage×current/1000 and 1,395 average-temperature rows differ from the mean of pack sensors 1/2/4. Horsepower remains 1.341×Instant_kW. This is consistent with component/derived fields being transformed differently, but the exact preprocessing cause is unverified. “Horsepower” here derives from battery electrical power; it is not independently measured wheel or shaft output.\n"
    )
    lines.append(
        "![SOH and odometer history](figures/processed/soh_odometer_history.png)\n"
    )
    lines.append(
        "The first and last processed trip rows report SOH 96.46% and 92.63% (a 3.83 percentage-point change), with odometer 3,578 to 15,537 km. Odometer anomalies mean rowwise distance differences cannot all be trusted. SOH is a reported battery estimate with repeated/quantized values; the observed trajectory is not a controlled capacity test or maintenance-confirmed degradation record.\n"
    )
    lines.append("## 7 — Labels and limitations\n")
    lines.append(
        "No verified healthy/faulty labels, confirmed failure events, DTC columns, maintenance/repair histories or ground-truth component diagnoses appear in these CSVs or the downloaded dictionary. SOC/SOH and operating states are observations, not fault labels. No task-specific target is designated.\n"
    )
    lines.append(
        "The publisher describes one vehicle and the data supplies 7 driver codes only in processed; these do not imply 7 vehicles. No VIN/battery serial column is present despite such parameters being mentioned in the general workbook. Driver identities, route selection, excluded sessions, logging gaps, release history and exact preprocessing rules are not fully documented. Single-vehicle observational sampling, non-continuous recordings, selected trips and unknown exclusion criteria limit generalization. Statistical outliers cannot establish real faults.\n"
    )
    lines.append("## 8 — Raw versus preprocessed data\n")
    lines.append(
        md(
            pd.DataFrame(
                [
                    {"Comparison": k, "Value": comparison[k]}
                    for k in [
                        "matched_unique_index_rows",
                        "raw_only_index_rows",
                        "processed_only_index_rows",
                        "same_timestamp_at_matched_index",
                    ]
                ]
            )
        )
    )
    lines.append(
        f"Independent exact timestamp matching gives **{alignment['matched_timestamp_rows']:,} shared rows**, **{alignment['raw_only_timestamps']:,} raw-only timestamps**, and **{alignment['processed_only_timestamps']:,} processed-only timestamps**. All shared timestamps have matching indices. The unmatched processed records occur across {len(alignment['processed_missing_from_raw_trip_ids'])} trip IDs. Therefore, the downloaded processed file is **not a strict subset** of the downloaded raw file. This does not prove researchers fabricated records; release differences or unprovided processing inputs remain possible. No nearest-time matching was used.\n"
    )
    lines.append(
        "Raw has 92 columns and 227 Trip values; processed has 32 and 127. Driver_ID is processed-only; 61 raw columns are absent from processed. Raw already contains export indices, trip IDs, derived and accumulated/calendar fields, so “raw” is the publisher’s label, not evidence of an untouched CAN dump.\n"
    )
    matched = pd.read_csv(BASE / "tables/raw_processed_matched_values.csv")
    lines.append(
        md(
            matched[matched["numerically_changed_rtol_atol_1e-9"] > 0][
                [
                    "column",
                    "matched_rows",
                    "numerically_changed_rtol_atol_1e-9",
                    "raw_minus1_processed_zero",
                    "max_abs_change_finite",
                ]
            ]
        )
    )
    lines.append(
        "The comparison uses numeric closeness with absolute and relative tolerances of 1e-9 and reports every shared column in the supporting CSV. Odometer is unchanged on matched rows, so preprocessing did not resolve its observed discontinuities there. Some −1 readings become zero, including tire pressure. Zero missingness partly reflects a reduced column set; it does not establish that every missing field was imputed. Distribution changes also reflect row selection and cannot all be attributed to cleaning. No release-specific executable preprocessing recipe was obtained or reproduced.\n"
    )
    lines.append(
        "Full comparisons: [per-column distributions](tables/raw_processed_distributions.csv), [matching values](tables/raw_processed_matched_values.csv), [retained versus absent raw rows](tables/retained_vs_removed_raw_rows.csv), [timestamp alignment](tables/raw_processed_timestamp_alignment.json).\n"
    )
    lines.append("## 9 — Overall EDA conclusions\n")
    lines.append(
        "**Strengths:** official research provenance, substantial real-world telemetry, useful battery and vehicle channels, a parameter workbook, explicit trip codes, available raw/preprocessed versions, and a long observed SOH/odometer history.\n"
    )
    lines.append(
        "**Most important limitations:** no verified diagnostic labels or maintenance history; one-vehicle scope; coverage/count mismatch with the landing-page description; raw/processed release mismatch; time gaps; missing raw channels; suspicious pressure, voltage and odometer values; uncertain units/current polarity; and derived-field inconsistencies after preprocessing. Absence of missing values in processed does not resolve these concerns.\n"
    )
    lines.append(
        "**Before choosing ML tasks**, obtain the exact preprocessing code and input release, definitions for every undocumented column and driver/trip assignment, confirmed units/current sign and unavailable-value codes, trustworthy charging/maintenance/failure records, intended usage rights, and independent vehicle/session data. No model architecture or algorithm is selected by this report.\n"
    )
    lines.append("### Reproduction and verification\n")
    lines.append(
        "Run from the repository root using the existing virtual environment:\n\n```bash\n.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/acquire.py\nMPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/run_eda.py\n.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/validate.py\n.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/build_report.py\n```\n"
    )
    lines.append(
        "Existing downloads are checked and reused. Source-size changes cause acquisition to stop for review. For already completed `.part` transfers, `acquire.py --finalize-existing` performs size checks, renames complete files and records hashes. Analysis requires roughly several GiB of available RAM and temporary disk space; numeric data is disk-backed and CSV input is chunked. Full CSV structural validation uses an independent strict CSV reader.\n"
    )
    lines.append(
        "All source SHA-256 values were rechecked; every CSV record width and row count, dictionary coverage, missing-cell accounting and trip-row accounting passed. Definite schema issues and observations remain explicitly recorded: validation passing means files/reports are internally readable and consistent, not that every sensor value is physically correct. No source rows were removed or imputed.\n"
    )
    lines.append(
        "See [README](README.md) for the complete file map, software versions and commands. `run_manifest.json`, `validation_results.json`, the source download manifest and generated CSVs provide the audit trail. Large datasets are Git-ignored; scripts, documentation, tables and figures remain trackable. No changes were committed or pushed for this task.\n"
    )
    lines.append(
        "### All output files\n\n[Open the complete output index](OUTPUT_INDEX.md) for direct links to every script, table, figure, metadata file and report.\n"
    )
    dest = BASE / "EDA_REPORT.md"
    dest.write_text("\n".join(lines))
    save = {
        "report": str(dest.relative_to(BASE)),
        "report_sha256": sha256(dest),
        "builder_sha256": sha256(Path(__file__)),
        "validated_inputs": validation,
    }
    (BASE / "report_manifest.json").write_text(json.dumps(save, indent=2) + "\n")
    index_path = BASE / "OUTPUT_INDEX.md"
    entries = []
    for path in sorted(
        [*BASE.rglob("*"), *DATA.rglob("*"), *Path(__file__).parent.rglob("*")]
    ):
        if path.is_file() and path != index_path and "__pycache__" not in path.parts:
            relative = path.relative_to(ROOT)
            entries.append(
                f"- [{relative}]({os.path.relpath(path, BASE)}) — {path.stat().st_size:,} bytes"
            )
    index_path.write_text(
        "# Complete dataset and EDA file index\n\nPurpose: navigate preserved sources and generated analysis outputs. Raw/processed CSVs are local, Git-ignored files.\n\n"
        + "\n".join(entries)
        + "\n"
    )
    print(dest)


if __name__ == "__main__":
    main()
