"""Pure quality, temporal, split, transformation and window primitives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

APPROVED = {"Speed", "Torque", "Motor_Temp", "HV_Bat_Voltage", "Pack_1_C_Temp", "SOC"}
PACKS = ["Pack_1_C_Temp", "Pack_2_C_Temp", "Pack_4_C_Temp"]
FLAGS = {
    "missing_candidate": (1, "Missing", "Candidate NaN; no silent fill"),
    "nonfinite_candidate": (
        2,
        "Invalid based on verified rules",
        "Infinite measurement cannot be a finite physical reading",
    ),
    "soc_domain": (
        4,
        "Invalid based on verified rules",
        "SOC outside documented percentage domain [0,100]; may encode unavailable state, not a fault",
    ),
    "speed_negative": (
        8,
        "Suspicious",
        "Negative speed magnitude/unavailable code unresolved",
    ),
    "voltage_review": (
        16,
        "Suspicious",
        "Nonpositive or above review threshold; not a fault",
    ),
    "pack_sentinel": (
        32,
        "Unresolved",
        "Pack reading near -1 may be unavailable or real; no conversion",
    ),
    "physical_temperature": (
        64,
        "Invalid based on verified rules",
        "Temperature below absolute zero in documented Celsius channel",
    ),
    "tire_zero_or_negative": (
        128,
        "Suspicious",
        "Pressure code needs interpretation; excluded feature",
    ),
    "odometer_decrease": (256, "Suspicious", "Decrease within trip; not corrected"),
    "odometer_jump": (512, "Suspicious", "Large short-interval jump; not corrected"),
    "soh_zero": (
        1024,
        "Unresolved",
        "Reported zero health not treated as battery failure",
    ),
    "power_formula": (
        2048,
        "Suspicious",
        "Stored power differs from V*I/1000; no replacement",
    ),
    "temperature_formula": (
        4096,
        "Suspicious",
        "Stored mean differs from components; no replacement",
    ),
    "duplicate_timestamp": (
        8192,
        "Invalid based on verified rules",
        "Ambiguous ordering for sequence use, not an invalid sensor reading",
    ),
    "long_gap": (16384, "Suspicious", "Start of new continuity segment"),
    "soh_missing": (32768, "Missing", "SOH NaN retained; not a selected input"),
    "irregular_interval": (
        65536,
        "Unresolved",
        "Row interval outside 0.2–0.3s descriptive band; no resampling",
    ),
}
AUDIT_COLUMNS = sorted(
    APPROVED
    | set(PACKS)
    | {
        "index",
        "Trip",
        "Timestamp",
        "RPM",
        "Odometer",
        "SOH",
        "HV_Bat_Current_2",
        "Instant_kW",
        "Pack_Avg_C_Temp",
        "TP_FR",
        "TP_FL",
        "TP_RR",
        "TP_RL",
        "Brake",
        "Acc_Pedal",
        "Ambient_C_Temp",
        "ECO",
        "ePedal",
    }
)


def digest(path: Path) -> str:
    """Stream source/output fingerprints without loading full files."""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_config(config: dict) -> None:
    features = config["features"]
    if config.get("view") == "battery_only_v1":
        if features != ["HV_Bat_Voltage", "Pack_1_C_Temp", "SOC"]:
            raise ValueError(
                "Battery-only feature order must contain exactly the three reviewed measurements"
            )
        if config.get("split_policy") != "reuse_parent_membership":
            raise ValueError("Battery view requires frozen parent trip assignments")
        if config["missing_policy"] != "exclude":
            raise ValueError(
                "Battery v1 exports three inputs and does not impute measurements"
            )
    if (
        not features
        or len(features) != len(set(features))
        or not set(features) <= APPROVED
    ):
        raise ValueError("Only reviewed, unique measurement features are permitted")
    if config["source_version"] != "raw":
        raise ValueError(
            "Raw-only preparation: alternate exports need separate provenance review"
        )
    if config["missing_policy"] not in {"exclude", "training_median"}:
        raise ValueError("Unsupported missing policy")
    if config["scaling"] not in {"robust", "standard", "none"}:
        raise ValueError("Unsupported scaling")
    fractions = config["split_fractions"]
    if len(fractions) != 3 or min(fractions) <= 0 or not np.isclose(sum(fractions), 1):
        raise ValueError("Three positive split fractions summing to one required")
    t = config["temperature"]
    if t["target"] != "Pack_1_C_Temp" or t["target"] not in features:
        raise ValueError("Only documented pack-1 target has been reviewed")
    if (
        min(
            config["gap_seconds"],
            t["horizon_seconds"],
            t["lookback_seconds"],
            t["stride_seconds"],
        )
        <= 0
    ):
        raise ValueError("Positive temporal parameters required")
    if (
        config["split_embargo_seconds"]
        < t["lookback_seconds"] + t["horizon_seconds"] + t["tolerance_seconds"]
    ):
        raise ValueError("Embargo is shorter than full window span")
    if set(config["duplicate_round_decimals"]) != set(features):
        raise ValueError("Duplicate screen must cover exactly the selected features")


def validate_schema(actual: list[str], expected: list[str]) -> None:
    if actual != expected or len(set(actual)) != len(actual):
        raise ValueError(
            "Source schema mismatch; review source release before preparation"
        )


def parse_time(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if (
        numeric.isna().any()
        or not np.isfinite(numeric).all()
        or not numeric.eq(np.floor(numeric)).all()
    ):
        raise ValueError("Invalid microsecond timestamp; source must be reviewed")
    result = pd.to_datetime(numeric, unit="us", utc=True, errors="coerce")
    if result.isna().any():
        raise ValueError("Timestamp outside parseable range")
    return result


def audit_trip(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Preserve all source rows, attach overlapping flags and task-specific eligibility."""
    frame = frame.copy().reset_index(drop=True)
    if frame.Trip.isna().any() or frame.Trip.nunique() != 1:
        raise ValueError("Audit requires one nonmissing trip")
    parse_time(frame.Timestamp)
    dt = frame.Timestamp.diff() / 1e6
    if dt.lt(0).any():
        raise ValueError(
            "Source time reversal; not silently sorted across ambiguous boundaries"
        )
    x = frame[config["features"]]
    duplicate = frame.Timestamp.duplicated(keep=False)
    sentinel = (
        frame[PACKS]
        .apply(lambda col: col.between(*config["temperature_sentinel_band"]))
        .any(axis=1)
    )
    conditions = {
        "missing_candidate": x.isna().any(axis=1),
        "nonfinite_candidate": np.isinf(x).any(axis=1),
        "soc_domain": frame.SOC.lt(0) | frame.SOC.gt(100),
        "speed_negative": frame.Speed.lt(0),
        "voltage_review": frame.HV_Bat_Voltage.le(0)
        | frame.HV_Bat_Voltage.gt(config["voltage_review_max"]),
        "pack_sentinel": sentinel,
        "physical_temperature": frame[
            PACKS + ([] if config.get("view") == "battery_only_v1" else ["Motor_Temp"])
        ]
        .lt(-273.15)
        .any(axis=1),
        "tire_zero_or_negative": frame[["TP_FR", "TP_FL", "TP_RR", "TP_RL"]]
        .le(0)
        .any(axis=1),
        "odometer_decrease": frame.Odometer.diff().lt(0),
        "odometer_jump": frame.Odometer.diff().gt(config["odometer_jump_km"])
        & dt.between(0, config["odometer_jump_interval_seconds"], inclusive="right"),
        "soh_zero": frame.SOH.eq(0),
        "soh_missing": frame.SOH.isna(),
        "duplicate_timestamp": duplicate,
        "long_gap": dt.gt(config["gap_seconds"]),
        "irregular_interval": dt.notna()
        & ~dt.between(*config["typical_interval_band_seconds"]),
    }
    for name, observed, expected in [
        (
            "power_formula",
            frame.Instant_kW,
            frame.HV_Bat_Voltage * frame.HV_Bat_Current_2 / 1000,
        ),
        (
            "temperature_formula",
            frame.Pack_Avg_C_Temp,
            frame[PACKS].mean(axis=1, skipna=False),
        ),
    ]:
        finite = np.isfinite(observed) & np.isfinite(expected)
        conditions[name] = finite & ~np.isclose(
            observed, expected, atol=config["formula_atol"], rtol=config["formula_rtol"]
        )
    mask = np.zeros(len(frame), dtype=np.uint32)
    for name, condition in conditions.items():
        mask |= np.where(condition, FLAGS[name][0], 0).astype(np.uint32)
    frame["quality_flags"] = mask
    # Other nonselected-column flags remain visible but do not remove usable inputs.
    blockers = [
        "nonfinite_candidate",
        "soc_domain",
        "speed_negative",
        "voltage_review",
        "pack_sentinel",
        "physical_temperature",
        "duplicate_timestamp",
    ]
    if config["missing_policy"] == "exclude":
        blockers.append("missing_candidate")
    if config.get("view") == "battery_only_v1":
        blockers.remove("speed_negative")
    block_mask = sum(FLAGS[name][0] for name in blockers)
    frame["quality_eligible"] = (mask & block_mask) == 0
    if config.get("view") == "battery_only_v1":
        frame["battery_blocking_flags"] = mask & block_mask
        frame["drivetrain_unavailable_suspected"] = (
            frame.Speed.eq(-1)
            | (frame.RPM.eq(-1) & frame.Torque.eq(-1))
            | frame[["Speed", "RPM", "Torque", "Motor_Temp"]].isna().any(axis=1)
        )
    breaks = (
        dt.isna()
        | dt.gt(config["gap_seconds"])
        | dt.le(0)
        | duplicate
        | duplicate.shift(fill_value=False)
    )
    frame["segment_in_trip"] = breaks.cumsum().astype("int32") - 1
    frame["operating_context"] = np.select(
        [frame.Speed.gt(0), frame.Speed.eq(0)],
        ["moving", "stationary"],
        default="unknown",
    )
    return frame


def chronological_split(trips: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Choose closest row-fraction boundaries among safe whole-trip calendar breaks."""
    trips = trips.sort_values("start_us").reset_index(drop=True).copy()
    if (
        trips.Trip.duplicated().any()
        or (
            trips.start_us.iloc[1:].to_numpy() <= trips.end_us.iloc[:-1].to_numpy()
        ).any()
    ):
        raise ValueError(
            "Reused/overlapping trips prevent a chronological grouped split"
        )
    starts = pd.to_datetime(trips.start_us, unit="us", utc=True).dt.date
    ends = pd.to_datetime(trips.end_us, unit="us", utc=True).dt.date
    gaps = (trips.start_us - trips.end_us.shift()) / 1e6
    candidates = np.flatnonzero(
        (gaps.ge(config["split_embargo_seconds"]) & starts.ne(ends.shift())).to_numpy()
    )
    if len(candidates) < 2:
        raise ValueError("No two defensible chronological split boundaries")
    cumulative = trips.rows.cumsum().to_numpy()
    fractions = cumulative / cumulative[-1]
    desired = np.cumsum(config["split_fractions"])[:2]
    pairs = [(a, b) for a in candidates for b in candidates if a < b]
    a, b = min(
        pairs,
        key=lambda pair: (
            abs(fractions[pair[0] - 1] - desired[0])
            + abs(fractions[pair[1] - 1] - desired[1]),
            pair,
        ),
    )
    trips["split"] = np.where(
        trips.index < a, "train", np.where(trips.index < b, "validation", "test")
    )
    return trips


def fingerprints(frame: pd.DataFrame, config: dict) -> np.ndarray:
    rounded = (
        frame[config["features"]]
        .astype("float64")
        .round(config["duplicate_round_decimals"])
    )
    rounded = rounded.mask(rounded.eq(0), 0.0)
    return pd.util.hash_pandas_object(rounded, index=False).to_numpy()


def fit_transformer(frame: pd.DataFrame, features: list[str], config: dict) -> dict:
    """Require training provenance; no temporal fill or target fitting."""
    if frame.empty or not frame.split.eq("train").all():
        raise ValueError("Transformer fit requires nonempty training-only rows")
    x = frame[features].astype(float)
    if np.isinf(x).any().any():
        raise ValueError("Nonfinite input to transformer")
    medians = x.median()
    if medians.isna().any():
        raise ValueError("All-missing training feature cannot be imputed")
    if config["missing_policy"] == "exclude" and x.isna().any().any():
        raise ValueError("Missing inputs under exclusion policy")
    x = x.fillna(medians)
    if config["scaling"] == "robust":
        center, scale = x.median(), x.quantile(0.75) - x.quantile(0.25)
    elif config["scaling"] == "standard":
        center, scale = x.mean(), x.std(ddof=0)
    else:
        center, scale = x.mean() * 0, x.mean() * 0 + 1
    constant = scale.eq(0)
    scale = scale.mask(constant, 1)
    return {
        "fit_split": "train",
        "fit_rows": len(x),
        "features": features,
        "missing_policy": config["missing_policy"],
        "scaling": config["scaling"],
        "median": medians.to_dict(),
        "center": center.to_dict(),
        "scale": scale.to_dict(),
        "zero_scale_features": list(scale.index[constant]),
        "output_features": features
        + (
            [c + "__missing" for c in features]
            if config["missing_policy"] == "training_median"
            else []
        ),
    }


def transform(frame: pd.DataFrame, state: dict) -> pd.DataFrame:
    x = frame[state["features"]].astype(float)
    if state["missing_policy"] == "exclude" and x.isna().any().any():
        raise ValueError("Missing input under exclusion policy")
    missing = x.isna().astype("float32").add_suffix("__missing")
    result = (
        (x.fillna(state["median"]) - pd.Series(state["center"]))
        / pd.Series(state["scale"])
    ).astype("float32")
    result = result[state["features"]]
    if not np.isfinite(result).all().all():
        raise ValueError("Transformation produced nonfinite values")
    if state["missing_policy"] == "training_median":
        result = pd.concat([result, missing], axis=1)
    return result


WINDOW_COLUMNS = [
    "Trip",
    "segment_id",
    "split",
    "input_start_row",
    "anchor_row",
    "target_row",
    "input_start_us",
    "anchor_us",
    "target_us",
    "input_rows",
    "target_temperature_c",
    "temperature_change_c",
]


def make_windows(frame: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, dict]:
    """Reference actual observed rows; no interpolation or future feature aggregation."""
    output, counts = (
        [],
        {
            "anchors_considered": 0,
            "insufficient_history": 0,
            "no_future_match": 0,
            "unsafe_interval": 0,
            "exported": 0,
        },
    )
    for _, segment in frame.groupby("segment_id", sort=False):
        if segment.Trip.nunique() != 1 or segment.split.nunique() != 1:
            raise ValueError("Segment crosses trip/split boundary")
        times = segment.Timestamp.to_numpy(dtype=np.int64)
        if (np.diff(times) <= 0).any():
            continue
        ids = segment.source_row.to_numpy()
        if (np.diff(ids) != 1).any():
            raise ValueError(
                "Window builder requires full source rows, not an already filtered frame"
            )
        good = segment.export_eligible.to_numpy() & np.isfinite(
            segment[spec["target"]].to_numpy()
        )
        bad_prefix = np.r_[0, np.cumsum(~good)]
        anchor = 0
        while anchor < len(segment):
            counts["anchors_considered"] += 1
            t = times[anchor]
            start = int(np.searchsorted(times, t - spec["lookback_seconds"] * 1e6))
            target = int(np.searchsorted(times, t + spec["horizon_seconds"] * 1e6))
            if (
                t - times[start]
                < (spec["lookback_seconds"] - spec["tolerance_seconds"]) * 1e6
            ):
                counts["insufficient_history"] += 1
            elif (
                target >= len(times)
                or times[target] - t
                > (spec["horizon_seconds"] + spec["tolerance_seconds"]) * 1e6
            ):
                counts["no_future_match"] += 1
            elif bad_prefix[target + 1] - bad_prefix[start] > 0:
                counts["unsafe_interval"] += 1
            else:
                row = segment.iloc[anchor]
                y = float(segment.iloc[target][spec["target"]])
                output.append(
                    [
                        int(row.Trip),
                        int(row.segment_id),
                        row.split,
                        int(ids[start]),
                        int(ids[anchor]),
                        int(ids[target]),
                        int(times[start]),
                        int(t),
                        int(times[target]),
                        anchor - start + 1,
                        y,
                        y - float(row[spec["target"]]),
                    ]
                )
                counts["exported"] += 1
            anchor = int(np.searchsorted(times, t + spec["stride_seconds"] * 1e6))
    return pd.DataFrame(output, columns=WINDOW_COLUMNS), counts


def save_json(path: Path, value: dict | list) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
