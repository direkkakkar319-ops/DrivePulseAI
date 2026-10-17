"""Frozen-parent verification, trip inheritance and metadata for the battery-only view."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .core import digest


def verify_parent(root: Path, config: dict) -> tuple[dict, dict]:
    """Verify every original artifact and original configuration without writing them."""
    run_id = config["parent_run_id"]
    if not re.fullmatch(r"[0-9a-f]{16}", run_id):
        raise ValueError("Invalid parent run identity")
    parent = root / "ml/artifacts/nissan_leaf_2018/preparation" / run_id
    manifest = parent / "manifest.json"
    if digest(manifest) != config["parent_manifest_sha256"]:
        raise ValueError("Original artifact manifest checksum changed")
    original = json.loads(manifest.read_text())
    if original["run_id"] != run_id:
        raise ValueError("Parent identity mismatch")
    expected = {str(manifest.relative_to(root)): config["parent_manifest_sha256"]}
    for name, info in original["outputs"].items():
        path = parent / name
        if path.parent != parent or digest(path) != info["sha256"]:
            raise ValueError(f"Original artifact checksum changed: {name}")
        expected[str(path.relative_to(root))] = info["sha256"]
    old_config = root / "ml/notebooks/nissan_leaf_2018/config/preparation.json"
    if digest(old_config) != config["original_config_sha256"]:
        raise ValueError("Original six-feature configuration changed")
    expected[str(old_config.relative_to(root))] = config["original_config_sha256"]
    return original, expected


def inherit_splits(sessions: pd.DataFrame, frozen: pd.DataFrame) -> pd.DataFrame:
    """Reuse membership exactly, rejecting mismatched source trips or ranges."""
    keys = ["Trip", "rows", "start_us", "end_us"]
    left = sessions[keys].sort_values("Trip").reset_index(drop=True)
    right = frozen[keys].sort_values("Trip").reset_index(drop=True)
    if sessions.Trip.duplicated().any() or frozen.Trip.duplicated().any():
        raise ValueError("Duplicate trip in frozen membership")
    try:
        pd.testing.assert_frame_equal(left, right, check_dtype=False)
    except AssertionError as exc:
        raise ValueError(
            "Frozen split source trips/counts/timestamps differ; refusing new boundaries"
        ) from exc
    result = (
        sessions.merge(frozen[["Trip", "split"]], on="Trip", validate="one_to_one")
        .sort_values("start_us")
        .reset_index(drop=True)
    )
    if result.split.drop_duplicates().tolist() != ["train", "validation", "test"]:
        raise ValueError("Frozen splits are not chronological")
    return result


def sorted_membership(values: np.ndarray, sorted_reference: np.ndarray) -> np.ndarray:
    """Exact uint64 membership without rebuilding a million-entry hash table per trip."""
    if len(sorted_reference) == 0:
        return np.zeros(len(values), dtype=bool)
    locations = np.searchsorted(sorted_reference, values)
    inside = locations < len(sorted_reference)
    found = np.zeros(len(values), dtype=bool)
    found[inside] = sorted_reference[locations[inside]] == values[inside]
    return found


def companion_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    """Lineage and audit context aligned row-for-row with the pure feature matrix."""
    out = frame[
        [
            "source_row",
            "index",
            "Timestamp",
            "Trip",
            "split",
            "segment_id",
            "quality_flags",
            "battery_blocking_flags",
            "drivetrain_unavailable_suspected",
        ]
    ].copy()
    out["quality_status"] = np.where(
        out.quality_flags.eq(0), "no_configured_row_flags", "retained_with_review_flags"
    )
    out["source_dataset"] = "raw"
    out["source_file"] = "data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv"
    return out.reset_index(drop=True)
