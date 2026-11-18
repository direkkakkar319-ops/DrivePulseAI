"""Audit every source row without cleaning: bounded CSV chunks and disk-backed arrays."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from acquire import BASE, DATA, FILES, sha256, source_path
from dictionary import definitions, role

CHUNK = 75000
SELECTED = [
    "Speed",
    "RPM",
    "SOC",
    "SOH",
    "Torque",
    "Motor_Temp",
    "HV_Bat_Voltage",
    "HV_Bat_Current_2",
    "Ambient_C_Temp",
    "Pack_1_C_Temp",
    "Pack_2_C_Temp",
    "Pack_4_C_Temp",
    "Pack_Avg_C_Temp",
    "Odometer",
    "kWh_Remaining",
    "Horsepower",
    "Instant_kW",
    "Acc_Pedal",
    "Brake",
]


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False) + "\n")


def table(
    path: Path, rows: list[dict], columns: list[str] | None = None
) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    frame.to_csv(path, index=False)
    return frame


def utc(value: float) -> str:
    return str(pd.to_datetime(value, unit="us", utc=True, errors="coerce"))


def longest_runs(
    mask: np.ndarray, timestamps: np.ndarray, trip: np.ndarray
) -> tuple[dict, list[dict]]:
    # A missing run cannot cross a trip, time reversal or >1s discontinuity.
    boundary = np.r_[
        True,
        (trip[1:] != trip[:-1])
        | (np.diff(timestamps) <= 0)
        | (np.diff(timestamps) > 1e6),
    ]
    starts = np.flatnonzero(mask & (np.r_[True, ~mask[:-1]] | boundary))
    ends = np.flatnonzero(mask & (np.r_[~mask[1:], True] | np.r_[boundary[1:], True]))
    assert len(starts) == len(ends)
    runs = [
        {
            "start_row": int(a),
            "end_row": int(b),
            "rows": int(b - a + 1),
            "observed_span_seconds": float((timestamps[b] - timestamps[a]) / 1e6),
            "trip": float(trip[a]),
        }
        for a, b in zip(starts, ends, strict=True)
    ]
    return {
        "missing_runs": len(runs),
        "longest_missing_run_rows": max((r["rows"] for r in runs), default=0),
        "longest_missing_span_seconds": max(
            (r["observed_span_seconds"] for r in runs), default=0
        ),
    }, runs


def verify_hash_duplicates(hashes: np.ndarray, values: np.ndarray) -> int:
    """Use hashes only to find candidates; confirm numeric row equality including NaNs."""
    order = np.argsort(hashes, kind="stable")
    adjacent = hashes[order[1:]] == hashes[order[:-1]]
    repeated = 0
    for left, right in zip(order[:-1][adjacent], order[1:][adjacent], strict=True):
        if np.array_equal(values[:, left], values[:, right], equal_nan=True):
            repeated += 1
        else:
            raise RuntimeError(
                "Hash collision detected; exact duplicate audit needs alternate grouping"
            )
    return repeated


def analyze(version: str, path: Path, doc: dict, work: Path) -> dict:
    print(f"{version}: inspecting CSV and allocating disk-backed arrays", flush=True)
    out = BASE / "tables" / version
    out.mkdir(parents=True, exist_ok=True)
    fig = BASE / "figures" / version
    fig.mkdir(parents=True, exist_ok=True)
    with path.open(newline="") as f:
        header = next(csv.reader(f))
    # Files are checked for per-record width below; newline count is allocation only.
    with path.open("rb") as f:
        lines = sum(
            block.count(b"\n") for block in iter(lambda: f.read(8 * 1024 * 1024), b"")
        )
        f.seek(-1, 2)
        final_newline = f.read(1) == b"\n"
    n = lines - 1 + (not final_newline)
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    numeric = [c for c in columns if c not in {"DateTime", "Timestamp_Object"}]
    values = np.memmap(
        work / f"{version}.bin", dtype="float64", mode="w+", shape=(len(numeric), n)
    )
    hashes = np.memmap(work / f"{version}.hash", dtype="uint64", mode="w+", shape=(n,))
    repeats = np.memmap(
        work / f"{version}.measurehash", dtype="uint64", mode="w+", shape=(n,)
    )
    timestamp_aux = {
        c: np.memmap(
            work / f"{version}.{c}.bin", dtype="float64", mode="w+", shape=(n,)
        )
        for c in columns
        if c in {"DateTime", "Timestamp_Object"}
    }
    dtypes = defaultdict(set)
    invalid = Counter()
    memory = 0
    offset = 0
    patterns = Counter()
    measurements = [
        c
        for c in numeric
        if role(c) in {"numeric_measurement_or_undocumented", "categorical_status"}
    ]
    for chunk in pd.read_csv(path, chunksize=CHUNK):
        end = offset + len(chunk)
        if chunk.columns.tolist() != columns:
            raise ValueError("Schema changed between chunks")
        memory += int(chunk.memory_usage(index=False, deep=True).sum())
        for c in columns:
            dtypes[c].add(str(chunk[c].dtype))
        numbers = chunk[numeric].apply(pd.to_numeric, errors="coerce")
        for c in numeric:
            invalid[c] += int((chunk[c].notna() & numbers[c].isna()).sum())
        values[:, offset:end] = numbers.to_numpy(dtype=float).T
        # Hash typed values consistently across chunks; date text retained in full-row hash.
        canonical = chunk.copy()
        canonical[numeric] = numbers.astype(float)
        hashes[offset:end] = pd.util.hash_pandas_object(
            canonical, index=False
        ).to_numpy()
        repeats[offset:end] = pd.util.hash_pandas_object(
            numbers[measurements].astype(float), index=False
        ).to_numpy()
        for c, a in timestamp_aux.items():
            fmt = "%d-%m-%Y %H:%M:%S.%f" if c == "DateTime" else "mixed"
            dt = pd.to_datetime(chunk[c], format=fmt, utc=True, errors="coerce")
            if c == "DateTime" and dt.isna().any():
                fallback = pd.to_datetime(
                    chunk[c], format="%d-%m-%Y %H:%M:%S", utc=True, errors="coerce"
                )
                dt = dt.fillna(fallback)
            a[offset:end] = np.where(
                dt.notna(), dt.astype("int64").to_numpy() // 1000, np.nan
            )
            invalid[c] += int((chunk[c].notna() & dt.isna()).sum())
        masks = chunk.isna().to_numpy()
        unique, counts = np.unique(
            np.packbits(masks, axis=1), axis=0, return_counts=True
        )
        for bits, count in zip(unique, counts, strict=True):
            patterns[bytes(bits)] += int(count)
        offset = end
    if offset != n:
        raise ValueError(
            "Record/newline count differs; multiline CSV requires another allocator"
        )
    x = {c: values[i] for i, c in enumerate(numeric)}
    ts = x["Timestamp"]
    trips = x["Trip"]
    diff = np.diff(ts) / 1e6
    within = trips[1:] == trips[:-1]
    # Native timestamp conversion must be consistent with Unix microsecond interpretation.
    dt = pd.to_datetime(ts, unit="us", utc=True, errors="coerce")
    time_errors = int(pd.isna(dt).sum())
    parsed_time_ranges = {
        c: {
            "invalid_or_missing": int(np.isnan(a).sum()),
            "unique_parsed_instants": int(pd.Series(a).nunique()),
            "max_abs_difference_from_epoch_seconds": float(
                np.nanmax(np.abs(a - ts)) / 1e6
            ),
        }
        for c, a in timestamp_aux.items()
    }
    # Confirm full-row hash candidates by rereading their complete parsed CSV rows.
    duplicate_candidates = np.flatnonzero(
        pd.Series(hashes).duplicated(keep=False).to_numpy()
    )
    exact_duplicates = 0
    if len(duplicate_candidates):
        candidate_set = set(duplicate_candidates.tolist())
        seen = set()
        position = 0
        for chunk in pd.read_csv(
            path, chunksize=CHUNK, dtype=str, keep_default_na=False
        ):
            for i in sorted(
                candidate_set.intersection(range(position, position + len(chunk)))
            ):
                row = tuple(chunk.iloc[i - position])
                exact_duplicates += row in seen
                seen.add(row)
            position += len(chunk)
    measurement_duplicates = verify_hash_duplicates(
        repeats, values[[numeric.index(c) for c in measurements]]
    )
    summary_rows = []
    dictionary = []
    missing = []
    runs_all = []
    findings = []
    frequency = []
    checks = []

    def finding(severity: str, column: str, rule: str, count: int, note: str) -> None:
        findings.append(
            {
                "severity": severity,
                "column": column,
                "rule": rule,
                "count": int(count),
                "interpretation": note,
            }
        )

    duplicate_names = [c for c, count in Counter(header).items() if count > 1]
    if duplicate_names:
        finding(
            "definite_schema_issue",
            "header",
            "duplicate_names",
            len(duplicate_names),
            repr(duplicate_names),
        )
    if "" in header:
        finding(
            "definite_schema_issue",
            "header",
            "empty_column_name",
            header.count(""),
            "Pandas supplies an Unnamed alias; original header is preserved in dictionary",
        )
    for i, c in enumerate(columns):
        if c not in x:
            # Audit original timestamp text values exactly, separately to bound memory.
            s = pd.read_csv(path, usecols=[c])[c]
        else:
            s = pd.Series(x[c], copy=False)
        null = s.isna().to_numpy()
        freq = s.value_counts(dropna=True)
        unique = len(freq)
        count = int(s.notna().sum())
        run_summary, runs = longest_runs(null, ts, trips)
        for r in runs:
            runs_all.append(dict(column=c, **r))
        missing.append(
            {
                "column": c,
                "missing_count": int(null.sum()),
                "missing_pct": float(null.mean() * 100),
                **run_summary,
            }
        )
        topfraction = float(freq.iloc[0] / count) if count else None
        for value, k in freq.head(10).items():
            frequency.append(
                {
                    "column": c,
                    "value": value,
                    "count": int(k),
                    "pct_nonmissing": float(k / count * 100),
                }
            )
        definition = doc.get(c, {})
        dictionary.append(
            {
                "column": c,
                "original_header": header[i],
                "dtype": ";".join(sorted(dtypes[c])),
                "role": role(c),
                "description": definition.get("description", "Unknown"),
                "unit": definition.get("unit", "Unknown"),
                "documentation": definition.get("provenance", "Unknown"),
                "documented_polling": definition.get("sampling", "Unknown"),
                "missing_pct": float(null.mean() * 100),
                "unique_values": unique,
                "constant_nonmissing": unique == 1,
                "near_constant_99pct": topfraction is not None and topfraction >= 0.99,
                "most_common_fraction_nonmissing": topfraction,
            }
        )
        if invalid[c]:
            finding(
                "definite_parse_issue",
                c,
                "invalid_numeric_or_datetime",
                invalid[c],
                "Conversion failed; source unchanged",
            )
        if c in x:
            nonfinite = int((~np.isfinite(s.to_numpy()) & ~null).sum())
            if nonfinite:
                finding(
                    "definite_numeric_issue",
                    c,
                    "infinite_value",
                    nonfinite,
                    "Infinity is not a finite measurement",
                )
            finite = s[np.isfinite(s)]
            q = finite.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
            iqr = q.get(0.75, np.nan) - q.get(0.25, np.nan)
            lo = q.get(0.25, np.nan) - 1.5 * iqr
            hi = q.get(0.75, np.nan) + 1.5 * iqr
            suitable = role(c) in {
                "numeric_measurement_or_undocumented",
                "derived_numeric",
            }
            outliers = (
                int(((finite < lo) | (finite > hi)).sum())
                if suitable and len(finite)
                else 0
            )
            summary_rows.append(
                {
                    "column": c,
                    "role": role(c),
                    "count": count,
                    "finite_count": len(finite),
                    "mean": finite.mean(),
                    "median": finite.median(),
                    "std_ddof1": finite.std(),
                    "variance_ddof1": finite.var(),
                    "min": finite.min(),
                    "p01": q.get(0.01),
                    "p05": q.get(0.05),
                    "q25": q.get(0.25),
                    "q75": q.get(0.75),
                    "p95": q.get(0.95),
                    "p99": q.get(0.99),
                    "max": finite.max(),
                    "unique_values": unique,
                    "skewness": finite.skew() if unique > 2 else np.nan,
                    "iqr_low": lo if suitable else np.nan,
                    "iqr_high": hi if suitable else np.nan,
                    "iqr_outlier_count": outliers if suitable else np.nan,
                    "iqr_zero": bool(iqr == 0),
                    "nonfinite_nonmissing": nonfinite,
                }
            )
            if suitable and outliers:
                finding(
                    "statistical_observation",
                    c,
                    "1.5_IQR_fences",
                    outliers,
                    "Not evidence of error/fault; zero IQR can flag every departure from the modal value",
                )
            if c in ["SOC", "SOH"]:
                bad = int(((s < 0) | (s > 100)).sum())
                if bad:
                    finding(
                        "requires_investigation",
                        c,
                        "outside_0_100_percent",
                        bad,
                        "Outside documented percentage scale; not a verified fault",
                    )
            if c in [
                "Speed",
                "Odometer",
                "HV_Bat_Voltage",
                "TP_FR",
                "TP_FL",
                "TP_RR",
                "TP_RL",
            ]:
                negative = int((s < 0).sum())
                zero = int((s == 0).sum())
                if negative:
                    finding(
                        "requires_investigation",
                        c,
                        "negative_nonnegative_quantity",
                        negative,
                        "Possible invalid/unavailable-value code; no automatic replacement",
                    )
                if (c.startswith("TP_") or c == "HV_Bat_Voltage") and zero:
                    finding(
                        "requires_investigation",
                        c,
                        "zero_pressure_or_voltage",
                        zero,
                        "Possible unavailable-value code; context needed",
                    )
            if c in {"Power_SW", "AC", "RearHeater", "ECO", "ePedal"}:
                bad = int((s.notna() & ~s.isin([0, 1])).sum())
                if bad:
                    finding(
                        "requires_investigation",
                        c,
                        "outside_documented_binary_codes",
                        bad,
                        "Retained; may be an undocumented unavailable code",
                    )
            if c == "Ambient_C_Temp":
                finding(
                    "documentation_conflict",
                    c,
                    "unit_conflict",
                    len(s),
                    "Workbook unit is Celsius but prose says Fahrenheit; no conversion applied",
                )
            if c == "Pack_3_C_Temp" and null.all():
                finding(
                    "documented_unavailable",
                    c,
                    "all_missing",
                    len(s),
                    "Workbook states pack 3 sensor absent on this Leaf variant",
                )
            if c in {"Brake", "Acc_Pedal"}:
                finding(
                    "documentation_uncertainty",
                    c,
                    "unknown_units",
                    len(s),
                    "Workbook explicitly questions units; do not call this percent",
                )
        if null.all():
            finding(
                "data_availability",
                c,
                "all_missing",
                len(s),
                "No observed values; preserved",
            )
        if unique == 1:
            finding(
                "data_availability",
                c,
                "constant",
                len(s),
                "No within-file variation; may be legitimate status",
            )
        del s, freq
    dictionary_df = table(out / "column_dictionary.csv", dictionary)
    table(out / "summary_statistics.csv", summary_rows)
    missing_df = table(out / "missing_values.csv", missing)
    table(
        out / "missing_runs.csv",
        runs_all,
        ["column", "start_row", "end_row", "rows", "observed_span_seconds", "trip"],
    )
    table(out / "top_value_frequencies.csv", frequency)
    pattern_rows = []
    for bits, count in patterns.most_common():
        mask = np.unpackbits(np.frombuffer(bits, dtype=np.uint8))[
            : len(columns)
        ].astype(bool)
        pattern_rows.append(
            {
                "missing_columns": "|".join(np.array(columns)[mask]),
                "rows": count,
                "pct": count / n * 100,
            }
        )
    table(out / "missing_patterns.csv", pattern_rows)
    duplicates = {
        "exact_full_rows": exact_duplicates,
        "duplicate_timestamp_rows": int(pd.Series(ts).duplicated().sum()),
        "duplicate_trip_timestamp_rows": int(
            pd.DataFrame({"trip": trips, "timestamp": ts}).duplicated().sum()
        ),
        "duplicate_measurement_rows_excluding_ids_times_derived": measurement_duplicates,
        "measurement_columns": measurements,
    }
    save_json(out / "duplicate_analysis.json", duplicates)
    table(
        out / "duplicate_analysis.csv",
        [{"check": k, "count": v} for k, v in duplicates.items() if isinstance(v, int)],
    )
    if duplicates["duplicate_timestamp_rows"]:
        finding(
            "requires_investigation",
            "Timestamp",
            "duplicate_timestamps",
            duplicates["duplicate_timestamp_rows"],
            "Do not delete; inspect trip overlap and repeated acquisition",
        )
    gap_rows = []
    for idx in np.flatnonzero((diff > 1) | (diff <= 0) | ~within):
        gap_rows.append(
            {
                "row_before": int(idx),
                "row_after": int(idx + 1),
                "trip_before": float(trips[idx]),
                "trip_after": float(trips[idx + 1]),
                "seconds": float(diff[idx]),
                "same_trip": bool(within[idx]),
                "reason": "reversal_or_repeat"
                if diff[idx] <= 0
                else "gap_over_1s"
                if diff[idx] > 1
                else "trip_boundary",
            }
        )
    table(
        out / "timestamp_boundaries.csv",
        gap_rows,
        [
            "row_before",
            "row_after",
            "trip_before",
            "trip_after",
            "seconds",
            "same_trip",
            "reason",
        ],
    )
    sample_dt = diff[within & (diff > 0)]
    time = {
        "earliest_utc_interpretation": utc(np.nanmin(ts)),
        "latest_utc_interpretation": utc(np.nanmax(ts)),
        "span_days": float((np.nanmax(ts) - np.nanmin(ts)) / 86400e6),
        "invalid_epoch_timestamps": time_errors,
        "timestamp_unit": "Unix microseconds inferred from magnitude and checked against raw date columns",
        "global_reversals": int((diff < 0).sum()),
        "within_trip_reversals": int(((diff < 0) & within).sum()),
        "within_trip_zero_deltas": int(((diff == 0) & within).sum()),
        "within_trip_gaps_over_1s": int(((diff > 1) & within).sum()),
        "global_gaps_over_1s": int((diff > 1).sum()),
        "within_trip_positive_interval_quantiles_seconds": {
            str(q): float(np.quantile(sample_dt, q))
            for q in [0, 0.01, 0.5, 0.95, 0.99, 1]
        },
        "within_trip_observed_contiguous_seconds_max_gap_1s": float(
            diff[within & (diff > 0) & (diff <= 1)].sum()
        ),
        "other_timestamp_columns": parsed_time_ranges,
    }
    save_json(out / "time_summary.json", time)
    session_rows = []
    signatures = defaultdict(list)
    for trip in np.unique(trips):
        loc = np.flatnonzero(trips == trip)
        t = ts[loc]
        dt_trip = np.diff(t) / 1e6
        signature = hashlib.sha256(
            np.asarray(repeats[loc], dtype="uint64").tobytes()
        ).hexdigest()
        signatures[signature].append(float(trip))
        row = {
            "trip": float(trip),
            "rows": len(loc),
            "first_source_row": int(loc[0]),
            "last_source_row": int(loc[-1]),
            "contiguous_blocks": int(1 + np.sum(np.diff(loc) > 1)),
            "earliest_us": float(t.min()),
            "latest_us": float(t.max()),
            "start_utc": utc(t.min()),
            "end_utc": utc(t.max()),
            "span_seconds": float((t.max() - t.min()) / 1e6),
            "reversals": int((dt_trip < 0).sum()),
            "gaps_over_1s": int((dt_trip > 1).sum()),
            "measurement_sequence_sha256_screen": signature,
        }
        for c in [
            "SOC",
            "SOH",
            "Odometer",
            "Speed",
            "HV_Bat_Current_2",
            "Pack_Avg_C_Temp",
        ]:
            a = x[c][loc]
            row[c + "_first"] = float(a[0])
            row[c + "_last"] = float(a[-1])
            row[c + "_min"] = float(np.nanmin(a))
            row[c + "_max"] = float(np.nanmax(a))
        if "Driver_ID" in x:
            row["driver_ids"] = "|".join(str(v) for v in np.unique(x["Driver_ID"][loc]))
        if "Charge_Mode" in x:
            row["charge_modes"] = "|".join(
                str(v) for v in np.unique(x["Charge_Mode"][loc])
            )
        session_rows.append(row)
    sessions = table(out / "sessions.csv", session_rows)
    overlap = []
    ordered = sessions.sort_values("earliest_us")
    previous = []
    for r in ordered.to_dict("records"):
        previous = [p for p in previous if p["latest_us"] >= r["earliest_us"]]
        for p in previous:
            overlap.append(
                {
                    "trip_a": p["trip"],
                    "trip_b": r["trip"],
                    "overlap_seconds": (
                        min(p["latest_us"], r["latest_us"]) - r["earliest_us"]
                    )
                    / 1e6,
                }
            )
        previous.append(r)
    table(
        out / "overlapping_sessions.csv",
        overlap,
        ["trip_a", "trip_b", "overlap_seconds"],
    )
    duplicate_sessions = [
        {
            "trips": "|".join(map(str, v)),
            "sequence_hash": k,
            "status": "potential duplicate sequence; hash screen only",
        }
        for k, v in signatures.items()
        if len(v) > 1
    ]
    table(
        out / "possible_duplicate_sessions.csv",
        duplicate_sessions,
        ["trips", "sequence_hash", "status"],
    )
    changes = []
    for c in measurements:
        a = x[c]
        changed = (
            within
            & np.isfinite(a[1:])
            & np.isfinite(a[:-1])
            & (a[1:] != a[:-1])
            & (diff > 0)
            & (diff <= 1)
        )
        observed = (
            within & np.isfinite(a[1:]) & np.isfinite(a[:-1]) & (diff > 0) & (diff <= 1)
        )
        changes.append(
            {
                "column": c,
                "eligible_adjacent_pairs": int(observed.sum()),
                "changed_pairs": int(changed.sum()),
                "unchanged_pct": float(
                    (observed.sum() - changed.sum()) / observed.sum() * 100
                )
                if observed.any()
                else np.nan,
                "interpretation": "Value change frequency is not polling frequency; physical constancy and sample holding both possible",
            }
        )
    table(out / "measurement_updates.csv", changes)
    corr_cols = [c for c in SELECTED if c in x and np.nanstd(x[c]) > 0]
    corr_data = pd.DataFrame({c: x[c] for c in corr_cols})
    corr = corr_data.corr(method="pearson")
    corr.to_csv(out / "correlation_pearson.csv")
    pairs = []
    for aidx, a in enumerate(corr_cols):
        for b in corr_cols[aidx + 1 :]:
            r = corr.loc[a, b]
            if abs(r) >= 0.8:
                pairs.append(
                    {
                        "column_a": a,
                        "column_b": b,
                        "pearson_r": float(r),
                        "pairwise_observations": int(
                            (np.isfinite(x[a]) & np.isfinite(x[b])).sum()
                        ),
                    }
                )
    table(
        out / "strong_correlations.csv",
        sorted(pairs, key=lambda r: -abs(r["pearson_r"])),
        ["column_a", "column_b", "pearson_r", "pairwise_observations"],
    )
    del corr_data
    formula_rows = []
    for name, observed, expected in [
        (
            "Instant_kW_from_VI",
            x["Instant_kW"],
            x["HV_Bat_Voltage"] * x["HV_Bat_Current_2"] / 1000,
        ),
        ("Horsepower_from_Instant_kW", x["Horsepower"], x["Instant_kW"] * 1.341),
        (
            "Pack_Avg_from_1_2_4",
            x["Pack_Avg_C_Temp"],
            (x["Pack_1_C_Temp"] + x["Pack_2_C_Temp"] + x["Pack_4_C_Temp"]) / 3,
        ),
    ]:
        mask = np.isfinite(observed) & np.isfinite(expected)
        error = np.abs(observed[mask] - expected[mask])
        formula_rows.append(
            {
                "relationship": name,
                "compared_rows": int(mask.sum()),
                "max_abs_error": float(error.max()),
                "mean_abs_error": float(error.mean()),
                "rows_close_atol_1e-8_rtol_1e-8": int(
                    np.isclose(
                        observed[mask], expected[mask], atol=1e-8, rtol=1e-8
                    ).sum()
                ),
            }
        )
    table(out / "derived_relationship_checks.csv", formula_rows)
    if time["within_trip_gaps_over_1s"]:
        finding(
            "requires_investigation",
            "Timestamp",
            "within_trip_gap_over_1s",
            time["within_trip_gaps_over_1s"],
            "Heuristic four nominal row intervals; not proof packets were lost",
        )
    if time["global_reversals"]:
        finding(
            "requires_investigation",
            "Timestamp",
            "global_time_reversal",
            time["global_reversals"],
            "Preserved ordering; distinguish session order from within-session disorder",
        )
    checks = [
        {
            "check": "CSV_readability_and_chunk_schema",
            "status": "pass",
            "details": f"{n} rows read; {len(columns)} columns",
        },
        {
            "check": "header_names",
            "status": "review" if duplicate_names or "" in header else "pass",
            "details": f"Duplicate names={duplicate_names}; blank names={header.count('')}",
        },
        {
            "check": "numeric_and_date_parse",
            "status": "pass"
            if sum(invalid.values()) == 0 and time_errors == 0
            else "fail",
            "details": json.dumps(dict(invalid)),
        },
        {
            "check": "analysis_fields_present",
            "status": "pass",
            "details": "Timestamp and Trip present; these are observed analysis dependencies, not a publisher-required schema",
        },
        {
            "check": "published_required_fields",
            "status": "not_defined",
            "details": "Workbook is a parameter catalogue, not a mandatory CSV schema",
        },
        {
            "check": "unit_consistency",
            "status": "review",
            "details": "Ambient temperature unit conflict; pedal/brake units unknown",
        },
        {
            "check": "duplicate_sessions",
            "status": "review" if duplicate_sessions else "pass_screen",
            "details": f"{len(duplicate_sessions)} identical sequence-hash groups; cannot prove all sessions independent",
        },
    ]
    odometer_delta = np.diff(x["Odometer"])
    drops = within & (odometer_delta < 0)
    jumps = within & (diff > 0) & (diff <= 1) & (odometer_delta > 1)
    for rule, mask, explanation in [
        (
            "odometer_decrease_within_trip",
            drops,
            "Cumulative distance moves backwards within a trip; reset, decoding or recording error requires investigation",
        ),
        (
            "odometer_jump_over_1km_within_1s",
            jumps,
            "Change inconsistent with ordinary road motion; retained for review",
        ),
    ]:
        if mask.any():
            finding(
                "requires_investigation", "Odometer", rule, int(mask.sum()), explanation
            )
    event_rows = [
        {
            "row_before": int(i),
            "row_after": int(i + 1),
            "trip": float(trips[i]),
            "delta_km": float(odometer_delta[i]),
            "elapsed_seconds": float(diff[i]),
        }
        for i in np.flatnonzero(drops | jumps)
    ]
    table(
        out / "odometer_discontinuities.csv",
        event_rows,
        ["row_before", "row_after", "trip", "delta_km", "elapsed_seconds"],
    )
    voltage_screen = (x["HV_Bat_Voltage"] == 0) | (x["HV_Bat_Voltage"] > 500)
    table(
        out / "voltage_review_rows.csv",
        [
            {
                "source_row": int(i),
                "timestamp_us": float(ts[i]),
                "trip": float(trips[i]),
                "voltage": float(x["HV_Bat_Voltage"][i]),
                "SOC": float(x["SOC"][i]),
                "speed": float(x["Speed"][i]),
            }
            for i in np.flatnonzero(voltage_screen)
        ],
        ["source_row", "timestamp_us", "trip", "voltage", "SOC", "speed"],
    )
    if (x["HV_Bat_Voltage"] > 500).any():
        finding(
            "requires_investigation",
            "HV_Bat_Voltage",
            "voltage_over_500V_review_screen",
            int((x["HV_Bat_Voltage"] > 500).sum()),
            "Exploratory threshold for nominal-360V documentation; not a manufacturer limit or fault label",
        )
    table(out / "integrity_checks.csv", checks)
    table(out / "data_quality_findings.csv", findings)
    distribution_cols = [
        c
        for c in numeric
        if role(c) in {"numeric_measurement_or_undocumented", "derived_numeric"}
    ]
    for page in range(0, len(distribution_cols), 16):
        page_cols = distribution_cols[page : page + 16]
        f, axes = plt.subplots(4, 4, figsize=(17, 12))
        for ax, c in zip(axes.flat, page_cols):
            a = x[c]
            ax.hist(a[np.isfinite(a)], bins=60)
            ax.set_title(c)
            ax.set_ylabel("Rows")
        for ax in list(axes.flat)[len(page_cols) :]:
            ax.set_visible(False)
        f.tight_layout()
        f.savefig(fig / f"all_numeric_distributions_{page // 16 + 1}.png", dpi=120)
        plt.close(f)
    # Directly documented charging codes; negative HV current alone is ambiguous.
    if "Charge_Mode" in x:
        charge = pd.DataFrame(
            {
                "Charge_Mode": x["Charge_Mode"],
                "Speed": x["Speed"],
                "current": x["HV_Bat_Current_2"],
                "SOC": x["SOC"],
                "OBC_Out_Pwr": x["OBC_Out_Pwr"],
            }
        )
        charge.groupby("Charge_Mode", dropna=False).agg(
            rows=("SOC", "size"),
            speed_min=("Speed", "min"),
            speed_max=("Speed", "max"),
            current_min=("current", "min"),
            current_max=("current", "max"),
            SOC_min=("SOC", "min"),
            SOC_max=("SOC", "max"),
            OBC_min=("OBC_Out_Pwr", "min"),
            OBC_max=("OBC_Out_Pwr", "max"),
        ).to_csv(out / "charging_modes.csv")
        del charge
    sign_rows = []
    for name, mask in [
        ("negative_current_moving", (x["HV_Bat_Current_2"] < 0) & (x["Speed"] > 0)),
        (
            "negative_current_stationary",
            (x["HV_Bat_Current_2"] < 0) & (x["Speed"] == 0),
        ),
        ("positive_current", x["HV_Bat_Current_2"] > 0),
        ("zero_current", x["HV_Bat_Current_2"] == 0),
    ]:
        sign_rows.append(
            {
                "condition": name,
                "rows": int(mask.sum()),
                "interpretation": "Current sign per workbook; regeneration/charging cannot be distinguished from sign alone",
            }
        )
    table(out / "current_sign_context.csv", sign_rows)
    # Distribution plots use every finite value; boxplots use a deterministic evenly spaced subset.
    plot_cols = [c for c in SELECTED if c in x]
    fig_hist, axs = plt.subplots(
        int(np.ceil(len(plot_cols) / 4)),
        4,
        figsize=(17, 3 * int(np.ceil(len(plot_cols) / 4))),
    )
    for ax, c in zip(axs.flat, plot_cols):
        a = x[c]
        ax.hist(a[np.isfinite(a)], bins=60)
        ax.set_title(c)
        ax.set_ylabel("Rows")
    for ax in list(axs.flat)[len(plot_cols) :]:
        ax.set_visible(False)
    fig_hist.tight_layout()
    fig_hist.savefig(fig / "distributions.png", dpi=130)
    plt.close(fig_hist)
    f, axs = plt.subplots(
        int(np.ceil(len(plot_cols) / 4)),
        4,
        figsize=(17, 3 * int(np.ceil(len(plot_cols) / 4))),
    )
    for ax, c in zip(axs.flat, plot_cols):
        a = x[c][:: max(1, n // 50000)]
        ax.boxplot(a[np.isfinite(a)], showfliers=True)
        ax.set_title(c)
    for ax in list(axs.flat)[len(plot_cols) :]:
        ax.set_visible(False)
    f.suptitle("Evenly spaced source-order sample, up to ~50,000 values per column")
    f.tight_layout()
    f.savefig(fig / "boxplots_sampled.png", dpi=130)
    plt.close(f)
    f, ax = plt.subplots(figsize=(12, max(5, len(columns) * 0.18)))
    ax.barh(missing_df.column, missing_df.missing_pct)
    ax.set_xlabel("Missing cells (%)")
    f.tight_layout()
    f.savefig(fig / "missing_values.png", dpi=120)
    plt.close(f)
    f, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(corr)), corr.columns, rotation=90)
    ax.set_yticks(range(len(corr)), corr.columns)
    f.colorbar(im, ax=ax)
    ax.set_title("Pearson correlations: selected telemetry; pairwise complete rows")
    f.tight_layout()
    f.savefig(fig / "correlation_heatmap.png", dpi=130)
    plt.close(f)
    chosen = sessions.sort_values("rows", ascending=False).iloc[0]["trip"]
    loc = np.flatnonzero(trips == chosen)
    loc = loc[:: max(1, len(loc) // 6000)]
    f, axs = plt.subplots(5, 1, figsize=(14, 12), sharex=True)
    for ax, c in zip(
        axs,
        ["Speed", "SOC", "HV_Bat_Voltage", "HV_Bat_Current_2", "Pack_Avg_C_Temp"],
        strict=True,
    ):
        # scatter avoids visually bridging discontinuities.
        ax.scatter((ts[loc] - ts[loc[0]]) / 1e6, x[c][loc], s=2)
        ax.set_ylabel(c)
    axs[-1].set_xlabel("Seconds from first source row in selected trip")
    f.suptitle(f"Trip {chosen}: source-order subsample, no interpolation")
    f.tight_layout()
    f.savefig(fig / "telemetry_timeseries.png", dpi=130)
    plt.close(f)
    f, axs = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    starts = pd.to_datetime(sessions.earliest_us, unit="us", utc=True)
    axs[0].scatter(starts, sessions.SOH_first, s=8)
    axs[0].set_ylabel("SOH at first trip row (%)")
    axs[1].scatter(starts, sessions.Odometer_first, s=8)
    axs[1].set_ylabel("Odometer at first trip row (km)")
    f.tight_layout()
    f.savefig(fig / "soh_odometer_history.png", dpi=130)
    plt.close(f)
    fig_dt, ax = plt.subplots(figsize=(9, 4))
    ax.hist(sample_dt[sample_dt <= 1], bins=100)
    ax.set_xlabel("Positive within-trip row interval <=1 s")
    ax.set_ylabel("Count")
    fig_dt.tight_layout()
    fig_dt.savefig(fig / "sampling_intervals.png", dpi=130)
    plt.close(fig_dt)
    summary = {
        "version": version,
        "filename": path.name,
        "file_bytes": path.stat().st_size,
        "compression": "none",
        "uncompressed_bytes": path.stat().st_size,
        "rows": n,
        "columns": len(columns),
        "exact_original_header": header,
        "pandas_columns": columns,
        "numeric_storage_columns": len(numeric),
        "text_storage_columns": len(columns) - len(numeric),
        "semantic_roles": dict(Counter(role(c) for c in columns)),
        "label_columns": [],
        "vehicle_identifier_columns": [],
        "trip_ids": len(sessions),
        "driver_ids": int(pd.Series(x["Driver_ID"]).nunique())
        if "Driver_ID" in x
        else None,
        "estimated_pandas_data_memory_bytes": memory,
        "numeric_disk_backed_bytes": values.nbytes,
        "all_missing_columns": dictionary_df.loc[
            dictionary_df.missing_pct == 100, "column"
        ].tolist(),
        "constant_columns": dictionary_df.loc[
            dictionary_df.constant_nonmissing, "column"
        ].tolist(),
        "near_constant_99pct_columns": dictionary_df.loc[
            dictionary_df.near_constant_99pct, "column"
        ].tolist(),
        "total_missing_cells": int(missing_df.missing_count.sum()),
        "duplicates": duplicates,
        "time": time,
        "potential_duplicate_session_groups": len(duplicate_sessions),
        "overlapping_session_pairs": len(overlap),
        "sha256": sha256(path),
    }
    save_json(out / "overview.json", summary)
    # Small compared with the telemetry: retain the arrays only in temporary analysis storage.
    print(f"{version}: complete {n:,} rows x {len(columns)} columns", flush=True)
    gc.collect()
    return {
        "summary": summary,
        "values": values,
        "numeric": numeric,
        "x": x,
        "dictionary": dictionary_df,
    }


def compare(raw: dict, processed: dict) -> None:
    out = BASE / "tables"
    r, p = raw["x"], processed["x"]
    rows = []
    shared = sorted(set(r) & set(p))
    for c in shared:
        rows.append(
            {
                "column": c,
                "raw_missing_pct": float(np.isnan(r[c]).mean() * 100),
                "processed_missing_pct": float(np.isnan(p[c]).mean() * 100),
                "raw_min": float(np.nanmin(r[c]))
                if np.isfinite(r[c]).any()
                else np.nan,
                "processed_min": float(np.nanmin(p[c]))
                if np.isfinite(p[c]).any()
                else np.nan,
                "raw_max": float(np.nanmax(r[c]))
                if np.isfinite(r[c]).any()
                else np.nan,
                "processed_max": float(np.nanmax(p[c]))
                if np.isfinite(p[c]).any()
                else np.nan,
                "raw_mean": float(np.nanmean(r[c]))
                if np.isfinite(r[c]).any()
                else np.nan,
                "processed_mean": float(np.nanmean(p[c]))
                if np.isfinite(p[c]).any()
                else np.nan,
            }
        )
    table(out / "raw_processed_distributions.csv", rows)
    if len(np.unique(r["index"])) != len(r["index"]) or len(
        np.unique(p["index"])
    ) != len(p["index"]):
        raise ValueError("index is not unique; cannot use as one-to-one comparison key")
    keys, ri, pi = np.intersect1d(r["index"], p["index"], return_indices=True)
    time_keys, rti, pti = np.intersect1d(
        r["Timestamp"], p["Timestamp"], return_indices=True
    )
    save_json(
        out / "raw_processed_timestamp_alignment.json",
        {
            "matched_timestamp_rows": len(time_keys),
            "raw_only_timestamps": len(r["Timestamp"]) - len(time_keys),
            "processed_only_timestamps": len(p["Timestamp"]) - len(time_keys),
            "matching_index_on_shared_timestamp": int(
                (r["index"][rti] == p["index"][pti]).sum()
            ),
            "processed_missing_from_raw_trip_ids": np.unique(
                p["Trip"][~np.isin(p["Timestamp"], r["Timestamp"])]
            ).tolist(),
            "note": "Presence is compared exactly at microsecond resolution, without nearest-time matching.",
        },
    )
    matched = []
    for c in shared:
        a, b = r[c][ri], p[c][pi]
        finite = np.isfinite(a) & np.isfinite(b)
        changed = finite & ~np.isclose(a, b, rtol=1e-9, atol=1e-9)
        matched.append(
            {
                "column": c,
                "matched_rows": len(keys),
                "both_finite": int(finite.sum()),
                "numerically_changed_rtol_atol_1e-9": int(changed.sum()),
                "raw_missing_processed_present": int(
                    (np.isnan(a) & np.isfinite(b)).sum()
                ),
                "raw_present_processed_missing": int(
                    (np.isfinite(a) & np.isnan(b)).sum()
                ),
                "raw_minus1_processed_zero": int(((a == -1) & (b == 0)).sum()),
                "max_abs_change_finite": float(np.max(np.abs(a[finite] - b[finite])))
                if finite.any()
                else np.nan,
            }
        )
    table(out / "raw_processed_matched_values.csv", matched)
    kept = np.zeros(len(r["index"]), bool)
    kept[ri] = True
    removed = []
    for c in [
        "Speed",
        "SOC",
        "SOH",
        "HV_Bat_Voltage",
        "HV_Bat_Current_2",
        "Charge_Mode",
    ]:
        if c in r:
            for label, mask in [("retained_index", kept), ("not_in_processed", ~kept)]:
                a = pd.Series(r[c][mask])
                removed.append(
                    {
                        "column": c,
                        "group": label,
                        "rows": len(a),
                        "missing": int(a.isna().sum()),
                        "min": a.min(),
                        "median": a.median(),
                        "max": a.max(),
                    }
                )
    table(out / "retained_vs_removed_raw_rows.csv", removed)
    save_json(
        out / "raw_processed_comparison.json",
        {
            "matched_unique_index_rows": len(keys),
            "raw_only_index_rows": int((~kept).sum()),
            "processed_only_index_rows": int(len(p["index"]) - len(keys)),
            "same_timestamp_at_matched_index": int(
                (r["Timestamp"][ri] == p["Timestamp"][pi]).sum()
            ),
            "raw_only_columns": sorted(
                set(raw["summary"]["pandas_columns"])
                - set(processed["summary"]["pandas_columns"])
            ),
            "processed_only_columns": sorted(
                set(processed["summary"]["pandas_columns"])
                - set(raw["summary"]["pandas_columns"])
            ),
            "interpretation": "index alignment is empirically checked against timestamps; transformations observed, not preprocessing reproduced",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", choices=["both", "processed", "raw"], default="both"
    )
    args = parser.parse_args()
    manifest = json.loads((BASE / "metadata/download_manifest.json").read_text())
    for entry in manifest["files"]:
        if (
            entry["path"] in FILES
            and sha256(source_path(entry["path"])) != entry["sha256"]
        ):
            raise ValueError("Source checksum mismatch")
    doc = definitions(BASE)
    selected = ["processed", "raw"] if args.version == "both" else [args.version]
    with tempfile.TemporaryDirectory(prefix="leaf-eda-") as temp:
        result = {}
        for version in selected:
            filename = (
                "Dataset_Preprocessed.csv"
                if version == "processed"
                else "Dataset_NissanLeaf-2021_2022.csv"
            )
            result[version] = analyze(
                version, DATA / version / filename, doc, Path(temp)
            )
        if len(result) == 2:
            compare(result["raw"], result["processed"])
    save_json(
        BASE / "run_manifest.json",
        {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "matplotlib": matplotlib.__version__,
            "versions_analyzed": selected,
            "source_manifest_sha256": sha256(BASE / "metadata/download_manifest.json"),
            "scripts_sha256": {
                p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))
            },
            "method": "All rows for numerical statistics, missingness, correlations and checks. Boxplots/time plots explicitly subsampled; no imputation/removal. Numeric arrays are temporary disk-backed float64; read CSV in 75,000-row chunks.",
        },
    )
    print("EDA finished; original files unchanged.", flush=True)


if __name__ == "__main__":
    main()
