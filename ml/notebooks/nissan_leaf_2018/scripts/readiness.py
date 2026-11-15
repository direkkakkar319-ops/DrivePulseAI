"""Audit ML readiness without altering telemetry, fitting models, or creating splits."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from acquire import BASE, DATA, ROOT, sha256, source_path

TABLES = BASE / "tables/readiness"
FIGURES = BASE / "figures/readiness"
SELECTED = [
    "Timestamp",
    "Trip",
    "SOH",
    "SOC",
    "Odometer",
    "Pack_Avg_C_Temp",
    "HV_Bat_Voltage",
    "HV_Bat_Current_2",
    "Speed",
    "Instant_kW",
    "Horsepower",
    "Pack_1_C_Temp",
    "Pack_2_C_Temp",
    "Pack_4_C_Temp",
]
TARGETS = {
    "SOH",
    "SOC",
    "Pack_1_C_Temp",
    "Pack_2_C_Temp",
    "Pack_4_C_Temp",
    "Pack_Avg_C_Temp",
    "Motor_Temp",
    "HV_Bat_Voltage",
    "HV_Bat_Current_2",
    "Speed",
}


def check_schema(actual: list[str], expected: list[str]) -> None:
    """Fail on reordered, missing, additional or duplicate pandas column names."""
    if actual != expected or len(actual) != len(set(actual)):
        raise ValueError("Schema differs from validated EDA schema")


def temporal_checks(frame: pd.DataFrame) -> dict:
    """Count source-order boundaries and gaps; never repair or sort source rows."""
    dt = frame.Timestamp.diff() / 1e6
    same = frame.Trip.eq(frame.Trip.shift())
    starts = ~same
    blocks = frame.loc[starts, "Trip"].value_counts()
    return {
        "rows": len(frame),
        "trip_ids": int(frame.Trip.nunique()),
        "timestamp_missing": int(frame.Timestamp.isna().sum()),
        "timestamp_parse_failures": int(
            pd.to_datetime(frame.Timestamp, unit="us", utc=True, errors="coerce")
            .isna()
            .sum()
        ),
        "global_reversals": int(dt.lt(0).sum()),
        "duplicate_adjacent_times": int(dt.eq(0).sum()),
        "trip_blocks": int(starts.sum()),
        "reused_noncontiguous_trip_ids": int(blocks.gt(1).sum()),
        "within_trip_reversals": int((same & dt.lt(0)).sum()),
        **{
            f"within_trip_gaps_gt_{s}s": int((same & dt.gt(s)).sum())
            for s in (1, 5, 60)
        },
        "median_within_trip_positive_interval_s": float(dt[same & dt.gt(0)].median()),
    }


def missing_accounting(frame: pd.DataFrame) -> pd.DataFrame:
    """Preserve the distinction between missing and nonfinite numeric values."""
    return pd.DataFrame(
        {"missing": frame.isna().sum(), "missing_pct": frame.isna().mean() * 100}
    )


def derived_checks(frame: pd.DataFrame) -> list[dict]:
    """Evaluate documented relationships using the same tolerance as existing EDA."""
    pairs = {
        "Instant_kW_from_VI": (
            frame.Instant_kW,
            frame.HV_Bat_Voltage * frame.HV_Bat_Current_2 / 1000,
        ),
        "Horsepower_from_Instant_kW": (frame.Horsepower, frame.Instant_kW * 1.341),
        "Pack_Avg_from_1_2_4": (
            frame.Pack_Avg_C_Temp,
            frame[["Pack_1_C_Temp", "Pack_2_C_Temp", "Pack_4_C_Temp"]].mean(
                axis=1, skipna=False
            ),
        ),
    }
    results = []
    for name, (observed, expected) in pairs.items():
        valid = np.isfinite(observed) & np.isfinite(expected)
        close = np.isclose(observed[valid], expected[valid], atol=1e-8, rtol=1e-8)
        results.append(
            {
                "relationship": name,
                "compared_rows": int(valid.sum()),
                "mismatches": int((~close).sum()),
                "max_abs_error": float((observed[valid] - expected[valid]).abs().max()),
            }
        )
    return results


def inventory() -> pd.DataFrame:
    """Use the existing complete dictionary, adding task-dependent eligibility notes."""
    pieces = []
    for version in ("raw", "processed"):
        dictionary = pd.read_csv(
            BASE / f"tables/{version}/column_dictionary.csv", keep_default_na=False
        )
        for row in dictionary.to_dict("records"):
            col, role = row["column"], row["role"]
            exclusion = (
                role in {"timestamp", "identifier_or_export_index"}
                or row["missing_pct"] == 100
                or row["constant_nonmissing"] is True
            )
            redundancy = []
            if col in {
                "Horsepower",
                "Instant_kW",
                "HV_Bat_Voltage",
                "HV_Bat_Current_2",
            }:
                redundancy.append(
                    "Power=voltage*current/1000; horsepower=1.341*power; processed exceptions"
                )
            if col in {"Speed", "RPM"}:
                redundancy.append("Strong Speed/RPM correlation")
            if col.startswith("Pack_") and "Temp" in col:
                redundancy.append(
                    "Pack mean derived from components 1/2/4; highly correlated"
                )
            if col in {"SOC", "AHr", "Hx", "GIDs", "kWh_Remaining", "SOH", "Odometer"}:
                redundancy.append(
                    "Battery state/capacity proxies or shared aging trajectory; inspect task dependencies"
                )
            leakage = "Exclude contemporaneous target and future information for any prediction task"
            if role in {"identifier_or_export_index", "timestamp"} or col == "Odometer":
                leakage = "Recording identity/time/aging shortcut; use for grouping/context, not unrestricted health evidence"
            if role == "derived_numeric":
                leakage += "; audit formula and accumulation direction before use"
            if col in {"SOH", "AHr", "Hx", "GIDs", "kWh_Remaining"}:
                leakage += (
                    "; possible direct SOH/capacity proxy; SOH cannot predict itself"
                )
            concerns = []
            if row["description"] == "Unknown" or row["unit"] == "Unknown":
                concerns.append("Incomplete documentation")
            if row["missing_pct"] > 0:
                concerns.append("Missing observations")
            if row["near_constant_99pct"] is True:
                concerns.append("At least 99% same nonmissing value")
            if col.startswith("TP_"):
                concerns.append("Zero pressure may mean unavailable; verify")
            if col in {
                "HV_Bat_Current_1",
                "HV_Bat_Current_2",
                "Ambient_C_Temp",
                "Odometer",
                "HV_Bat_Voltage",
                "Instant_kW",
                "Pack_Avg_C_Temp",
            }:
                concerns.append("See EDA quality, polarity, units or formula findings")
            if role == "derived_numeric":
                concerns.append(
                    "Formula, provenance and causal availability require review"
                )
            pieces.append(
                {
                    **row,
                    "source_dataset": version,
                    "measurement_class": role.replace(
                        "numeric_measurement_or_undocumented",
                        "measured_or_undocumented",
                    ),
                    "potential_input": "excluded_from_initial_input_pool"
                    if exclusion
                    else "conditional_candidate",
                    "potential_target": "recorded SOH, not measured failure/capacity ground truth"
                    if col == "SOH"
                    else (
                        "future telemetry only; horizon must be defined"
                        if col in TARGETS
                        else "not_proposed"
                    ),
                    "possible_target_leakage": leakage,
                    "redundancy": "; ".join(redundancy)
                    or "Not established; see EDA correlations",
                    "requires_investigation": "; ".join(concerns)
                    or "Task availability and operating-state validation",
                }
            )
    return pd.DataFrame(pieces)


def associations(frame: pd.DataFrame, version: str, level: str) -> list[dict]:
    """Descriptive associations only; no iid significance claims or regression fitting."""
    rows = []
    for column in [
        "Odometer",
        "Timestamp",
        "SOC",
        "Pack_Avg_C_Temp",
        "HV_Bat_Voltage",
        "HV_Bat_Current_2",
    ] + [c for c in ("AHr", "Hx", "GIDs") if c in frame]:
        pair = frame[["SOH", column]].replace([np.inf, -np.inf], np.nan).dropna()
        for method in ("pearson", "spearman"):
            value = (
                pair.SOH.corr(pair[column], method=method)
                if pair.SOH.nunique() > 1 and pair[column].nunique() > 1
                else np.nan
            )
            rows.append(
                {
                    "version": version,
                    "level": level,
                    "variable": column,
                    "method": method,
                    "paired_count": len(pair),
                    "correlation": value,
                }
            )
    return rows


def analyze(frame: pd.DataFrame, version: str) -> tuple[dict, list[dict], list[dict]]:
    """Describe reported SOH and sensitivity to aggregation, without cleaning records."""
    temporal = temporal_checks(frame)
    delta = frame.SOH.diff()
    same = frame.Trip.eq(frame.Trip.shift())
    valid_pairs = frame.SOH.notna() & frame.SOH.shift().notna()
    within = same & valid_pairs
    groups = frame.groupby("Trip", sort=False)
    trip = groups[SELECTED].median().drop(columns="Trip", errors="ignore")
    trip["rows"] = groups.size()
    trip["soh_unique"] = groups.SOH.nunique()
    trip["soh_min"] = groups.SOH.min()
    trip["soh_max"] = groups.SOH.max()
    trip = trip.sort_values("Timestamp")
    dates = pd.to_datetime(frame.Timestamp, unit="us", utc=True).dt.floor("D")
    daily = frame.groupby(dates)[[c for c in SELECTED if c != "Trip"]].median()
    daily["rows"] = frame.groupby(dates).size()
    trip.to_csv(TABLES / f"{version}_trip_soh.csv")
    daily.to_csv(TABLES / f"{version}_daily_soh.csv")
    values = (
        frame.SOH.value_counts(dropna=False)
        .sort_index()
        .rename_axis("SOH")
        .reset_index(name="rows")
    )
    values.to_csv(TABLES / f"{version}_soh_values.csv", index=False)
    changes = frame.loc[
        valid_pairs & delta.ne(0), ["Timestamp", "Trip", "SOH", "Odometer"]
    ].copy()
    changes["soh_change"] = delta[changes.index]
    changes["within_same_trip"] = same[changes.index]
    changes.to_csv(TABLES / f"{version}_soh_changes.csv", index=False)
    finite_soh = frame.SOH[np.isfinite(frame.SOH)]
    metrics = {
        **temporal,
        "columns": len(
            pd.read_csv(
                DATA
                / (
                    "raw/Dataset_NissanLeaf-2021_2022.csv"
                    if version == "raw"
                    else "processed/Dataset_Preprocessed.csv"
                ),
                nrows=0,
            ).columns
        ),
        "soh_min": float(finite_soh.min()),
        "soh_max": float(finite_soh.max()),
        "soh_unique": int(frame.SOH.nunique()),
        "soh_missing": int(frame.SOH.isna().sum()),
        "soh_zero": int(frame.SOH.eq(0).sum()),
        "soh_outside_0_100": int(((frame.SOH < 0) | (frame.SOH > 100)).sum()),
        "soh_first": float(frame.SOH.iloc[0]),
        "soh_last": float(frame.SOH.iloc[-1]),
        "soh_on_0_01_grid_fraction": float(
            np.isclose(
                finite_soh * 100, np.round(finite_soh * 100), atol=1e-7, rtol=0
            ).mean()
        ),
        "soh_increases_all_adjacent": int((valid_pairs & delta.gt(1e-9)).sum()),
        "soh_decreases_all_adjacent": int((valid_pairs & delta.lt(-1e-9)).sum()),
        "soh_increases_within_trip": int((within & delta.gt(1e-9)).sum()),
        "soh_decreases_within_trip": int((within & delta.lt(-1e-9)).sum()),
        "soh_equal_within_trip_pct": float(delta[within].eq(0).mean() * 100),
        "trips_with_soh_changes": int(trip.soh_unique.gt(1).sum()),
        "recorded_days": len(daily),
        "daily_median_soh_increases": int(daily.SOH.diff().gt(1e-9).sum()),
        "daily_odometer_time_pearson": float(daily.Odometer.corr(daily.Timestamp)),
        "row_odometer_time_pearson": float(frame.Odometer.corr(frame.Timestamp)),
        "start_utc": str(pd.to_datetime(frame.Timestamp.iloc[0], unit="us", utc=True)),
        "end_utc": str(pd.to_datetime(frame.Timestamp.iloc[-1], unit="us", utc=True)),
        "derived_checks": derived_checks(frame),
    }
    if version == "raw":
        expected_energy = frame.SOC * frame.AHr * 0.0036
        valid = np.isfinite(expected_energy) & np.isfinite(frame.kWh_Remaining)
        metrics["remaining_energy_formula"] = {
            "compared_rows": int(valid.sum()),
            "mismatches_atol_rtol_1e_8": int(
                (
                    ~np.isclose(
                        frame.loc[valid, "kWh_Remaining"],
                        expected_energy[valid],
                        atol=1e-8,
                        rtol=1e-8,
                    )
                ).sum()
            ),
        }
    corr = []
    for level, subset in [
        ("telemetry_rows", frame),
        ("trip_medians", trip),
        ("recorded_day_medians", daily),
        ("successive_recorded_day_differences", daily.diff()),
    ]:
        corr.extend(associations(subset, version, level))
    # Within-month comparisons reveal sensitivity to common long-term trend; small groups remain visible.
    for month, subset in daily.groupby(daily.index.strftime("%Y-%m")):
        corr.extend(associations(subset, version, "within_month_daily_" + month))
    adjacency = []
    for col in SELECTED[2:]:
        previous = frame[col].shift()
        eligible = (
            same
            & frame[col].notna()
            & previous.notna()
            & frame.Timestamp.diff().between(1, 1e6)
        )
        adjacency.append(
            {
                "version": version,
                "column": col,
                "pairs_same_trip_gap_le_1s": int(eligible.sum()),
                "equal_pct": float(
                    frame.loc[eligible, col].eq(previous[eligible]).mean() * 100
                ),
                "lag_one_pearson": float(
                    frame.loc[eligible, col].corr(previous[eligible])
                ),
            }
        )
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes[0, 0].plot(daily.index, daily.SOH, ".-")
    axes[0, 0].set(
        xlabel="Recorded day (UTC; gaps connect recordings)", ylabel="Reported SOH (%)"
    )
    for ax, col in zip(
        axes.flat[1:], ["Odometer", "Pack_Avg_C_Temp", "HV_Bat_Voltage"]
    ):
        scatter = ax.scatter(
            daily[col], daily.SOH, c=np.arange(len(daily)), s=16, cmap="viridis"
        )
        ax.set(xlabel=f"Daily median {col}", ylabel="Daily median SOH (%)")
        fig.colorbar(scatter, ax=ax, label="Recorded-day order")
    fig.suptitle(f"{version}: descriptive medians; one vehicle, no fitted model")
    fig.tight_layout()
    fig.savefig(FIGURES / f"{version}_soh_shortcuts.png", dpi=150)
    plt.close(fig)
    return metrics, corr, adjacency


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((BASE / "metadata/download_manifest.json").read_text())
    verified = []
    for item in manifest["files"]:
        path = source_path(item["path"])
        digest = sha256(path)
        if digest != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Source changed: {path}")
        verified.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )
    inv = inventory()
    inv.to_csv(TABLES / "feature_inventory.csv", index=False)
    metrics, corr, adjacent, missing = {}, [], [], []
    for version, filename in [
        ("processed", "Dataset_Preprocessed.csv"),
        ("raw", "Dataset_NissanLeaf-2021_2022.csv"),
    ]:
        print(f"Reading selected columns: {version}", flush=True)
        path = DATA / version / filename
        overview = json.loads((BASE / f"tables/{version}/overview.json").read_text())
        check_schema(
            list(pd.read_csv(path, nrows=0).columns), overview["pandas_columns"]
        )
        frame = pd.read_csv(
            path,
            usecols=SELECTED
            + (["AHr", "Hx", "GIDs", "kWh_Remaining"] if version == "raw" else []),
        )
        if len(frame) != overview["rows"]:
            raise ValueError("Row count differs from validated EDA")
        metrics[version], rows, adj = analyze(frame, version)
        corr.extend(rows)
        adjacent.extend(adj)
        counts = missing_accounting(frame).reset_index(names="column")
        existing_missing = pd.read_csv(
            BASE / f"tables/{version}/missing_values.csv"
        ).set_index("column")
        for row in counts.itertuples():
            if row.missing != existing_missing.loc[row.column, "missing_count"]:
                raise ValueError(f"Missing count differs for {version}/{row.column}")
        counts["version"] = version
        missing.append(counts)
        del frame
    pd.DataFrame(corr).to_csv(TABLES / "soh_associations.csv", index=False)
    pd.DataFrame(adjacent).to_csv(TABLES / "adjacent_similarity.csv", index=False)
    pd.concat(missing).to_csv(TABLES / "selected_missing_checks.csv", index=False)
    sessions = {v: pd.read_csv(BASE / f"tables/{v}/sessions.csv") for v in metrics}
    metrics["trip_overlap"] = {
        "shared_ids": len(set(sessions["raw"].trip) & set(sessions["processed"].trip)),
        "raw_only_ids": len(
            set(sessions["raw"].trip) - set(sessions["processed"].trip)
        ),
        "processed_only_ids": len(
            set(sessions["processed"].trip) - set(sessions["raw"].trip)
        ),
    }
    metrics["inventory"] = {
        v: {
            "entries": len(g),
            "conditional_input_columns": int(
                g.potential_input.eq("conditional_candidate").sum()
            ),
            "potential_target_columns": int(
                g.potential_target.ne("not_proposed").sum()
            ),
        }
        for v, g in inv.groupby("source_dataset")
    }
    (TABLES / "readiness_metrics.json").write_text(
        json.dumps(metrics, indent=2, allow_nan=False) + "\n"
    )
    from readiness_report import write_report

    write_report(metrics, inv)
    outputs = sorted(
        [*TABLES.glob("*"), *FIGURES.glob("*"), BASE / "ML_READINESS_REPORT.md"]
    )
    reused = sorted(
        [
            p
            for p in (BASE / "tables").rglob("*")
            if p.is_file() and TABLES not in p.parents
        ]
    )
    provenance = {
        "source_files_verified": verified,
        "analysis_scope": "All rows, selected columns; complete schemas and inventories from hash-verified EDA. No training or cleaning.",
        "versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "scripts": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in Path(__file__).parent.glob("readiness*.py")
        },
        "reused_eda_table_hashes": {
            str(p.relative_to(ROOT)): sha256(p) for p in reused
        },
        "outputs": {str(p.relative_to(ROOT)): sha256(p) for p in outputs},
    }
    (BASE / "readiness_manifest.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
