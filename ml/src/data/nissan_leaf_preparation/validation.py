"""Independently verify exported row assignments, transforms and window references."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .core import fingerprints, fit_transformer, transform


def validate_outputs(directory: Path, config: dict) -> dict:
    battery = config.get("view") == "battery_only_v1"
    columns = [
        "source_row",
        "Trip",
        "Timestamp",
        "segment_id",
        "split",
        "export_eligible",
        *config["features"],
    ]
    ledger = pd.read_parquet(directory / "row_ledger.parquet", columns=columns)
    if not ledger.source_row.eq(np.arange(len(ledger))).all():
        raise ValueError("Source-row provenance lost")
    if battery:
        parent = (
            pd.read_csv(directory / "frozen_parent_trip_splits.csv")
            .set_index("Trip")
            .split
        )
        if not ledger.split.eq(ledger.Trip.map(parent)).all():
            raise ValueError("Frozen trip membership changed")
    if ledger.groupby("Trip").split.nunique().max() != 1:
        raise ValueError("Trip leakage")
    timestamps = ledger.groupby("split").Timestamp.agg(["min", "max"])
    for left, right in [("train", "validation"), ("validation", "test")]:
        if (
            timestamps.loc[right, "min"] - timestamps.loc[left, "max"]
            < config["split_embargo_seconds"] * 1e6
        ):
            raise ValueError("Temporal embargo violated")
    state = json.loads((directory / "transformer.json").read_text())
    train = ledger[ledger.split.eq("train") & ledger.export_eligible]
    if state["fit_split"] != "train" or state["fit_rows"] != len(train):
        raise ValueError("Transformer scope mismatch")
    expected_state = fit_transformer(train, config["features"], config)
    if state != expected_state:
        raise ValueError(
            "Saved parameters differ from independently refitted training-only statistics"
        )
    earlier = set()
    window_rows = 0
    bad_prefix = np.r_[0, np.cumsum(~ledger.export_eligible.to_numpy())]
    spec = config["temperature"]
    for split in ("train", "validation", "test"):
        rows = ledger[ledger.split.eq(split) & ledger.export_eligible]
        features = pd.read_parquet(directory / f"features_{split}.parquet")
        metadata = (
            pd.read_parquet(directory / f"metadata_{split}.parquet")
            if battery
            else features
        )
        if metadata.source_row.tolist() != rows.source_row.tolist():
            raise ValueError("Feature row assignment mismatch")
        if features.columns.tolist() != (
            [*state["output_features"]]
            if battery
            else ["source_row", *state["output_features"]]
        ):
            raise ValueError("Feature schema mismatch")
        if battery:
            for field in ["Timestamp", "Trip", "split", "segment_id"]:
                if not np.array_equal(metadata[field], rows[field]):
                    raise ValueError(f"Companion metadata alignment failure: {field}")
            if (
                len(features) != len(metadata)
                or not metadata.battery_blocking_flags.eq(0).all()
            ):
                raise ValueError("Battery quality/metadata accounting failure")
        expected = transform(rows, state).to_numpy()
        if not np.array_equal(features[state["output_features"]].to_numpy(), expected):
            raise ValueError("Export differs from frozen training transformer")
        hashes = set(fingerprints(rows, config).tolist())
        if hashes & earlier:
            raise ValueError("Cross-split rounded feature repetition remains")
        earlier.update(hashes)
        windows = pd.read_parquet(directory / f"temperature_{split}.parquet")
        if windows.empty:
            raise ValueError(f"No safe temperature examples in {split}")
        start = windows.input_start_row.to_numpy(dtype=int)
        anchor = windows.anchor_row.to_numpy(dtype=int)
        target = windows.target_row.to_numpy(dtype=int)
        if not ((start <= anchor) & (anchor < target)).all():
            raise ValueError("Window ordering failure")
        for col, loc in [
            ("input_start_us", start),
            ("anchor_us", anchor),
            ("target_us", target),
        ]:
            if not np.array_equal(windows[col], ledger.Timestamp.iloc[loc]):
                raise ValueError("Window timestamps not tied to original observations")
        if not (
            ledger.segment_id.iloc[start].to_numpy()
            == ledger.segment_id.iloc[target].to_numpy()
        ).all():
            raise ValueError("Window crosses a segment boundary")
        if (
            not ledger.split.iloc[target].eq(split).all()
            or not ledger.split.iloc[start].eq(split).all()
        ):
            raise ValueError("Window crosses a split")
        if (bad_prefix[target + 1] - bad_prefix[start]).any():
            raise ValueError("Window contains excluded rows")
        if not np.array_equal(
            windows.target_temperature_c, ledger[spec["target"]].iloc[target]
        ):
            raise ValueError("Target changed or imputed")
        horizons = (windows.target_us - windows.anchor_us) / 1e6
        if not horizons.between(
            spec["horizon_seconds"], spec["horizon_seconds"] + spec["tolerance_seconds"]
        ).all():
            raise ValueError("Target outside configured horizon tolerance")
        window_rows += len(windows)
    return {
        "passed": True,
        "source_rows_accounted": len(ledger),
        "temperature_windows_checked": window_rows,
        "trip_overlap": 0,
        "timestamp_window_overlap_between_splits": 0,
        "rounded_feature_overlap_between_splits": 0,
        "transform_matches_frozen_training_state": True,
        "future_feature_leakage_in_window_references": False,
        "scope_note": "Rounding screen does not prove independent telemetry or rule out all near-neighbors.",
    }
