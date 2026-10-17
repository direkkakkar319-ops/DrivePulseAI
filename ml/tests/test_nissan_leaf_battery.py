"""Test battery-only eligibility, frozen splits, pure inputs and artifact immutability."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import test_nissan_leaf_preparation as legacy_tests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/src"))
from nissan_leaf_preparation.battery import (
    companion_metadata,
    inherit_splits,
    sorted_membership,
    verify_parent,
)
from nissan_leaf_preparation.core import (
    audit_trip,
    digest,
    fit_transformer,
    make_windows,
    transform,
    validate_config,
)


@pytest.fixture
def telemetry() -> pd.DataFrame:
    return legacy_tests.telemetry.__wrapped__()


@pytest.fixture
def battery_config() -> dict:
    return json.loads(
        (ROOT / "ml/notebooks/nissan_leaf_2018/config/battery_only.json").read_text()
    )


def test_exact_battery_order(battery_config: dict) -> None:
    validate_config(battery_config)
    for columns in [
        ["SOC", "Pack_1_C_Temp", "HV_Bat_Voltage"],
        ["Speed", *battery_config["features"]],
        ["SOC"],
    ]:
        bad = copy.deepcopy(battery_config)
        bad["features"] = columns
        with pytest.raises(ValueError, match="feature order"):
            validate_config(bad)


def test_no_split_recalculation_or_imputation_config(battery_config: dict) -> None:
    for key, value in [
        ("split_policy", "recalculate"),
        ("missing_policy", "training_median"),
    ]:
        with pytest.raises(ValueError):
            validate_config(dict(battery_config, **{key: value}))


@pytest.mark.parametrize("value", [-1.0, -999.0, np.nan, np.inf])
def test_drivetrain_cannot_block_battery(
    telemetry: pd.DataFrame, battery_config: dict, value: float
) -> None:
    original = audit_trip(telemetry, battery_config)
    changed = telemetry.copy()
    for col in ["Speed", "RPM", "Torque", "Motor_Temp"]:
        changed[col] = value
    result = audit_trip(changed, battery_config)
    assert result.quality_eligible.all()
    assert result.battery_blocking_flags.eq(0).all()
    pd.testing.assert_series_equal(original.segment_in_trip, result.segment_in_trip)
    if value == -1 or np.isnan(value):
        assert result.drivetrain_unavailable_suspected.all()


@pytest.mark.parametrize(
    "column,value",
    [
        ("SOC", -1),
        ("SOC", 101),
        ("HV_Bat_Voltage", 0),
        ("HV_Bat_Voltage", 655.35),
        ("Pack_1_C_Temp", -1),
        ("Pack_1_C_Temp", np.nan),
        ("Pack_1_C_Temp", np.inf),
        ("Pack_2_C_Temp", -1),
        ("Pack_4_C_Temp", -300),
    ],
)
def test_battery_rules_remain_required(
    telemetry: pd.DataFrame, battery_config: dict, column: str, value: float
) -> None:
    telemetry.loc[0, column] = value
    result = audit_trip(telemetry, battery_config)
    assert not result.quality_eligible.iloc[0]
    assert result.battery_blocking_flags.iloc[0] != 0
    assert result.quality_eligible.sum() + (~result.quality_eligible).sum() == len(
        result
    )
    assert result.quality_eligible.iloc[1:].all()


def test_frozen_membership_and_refusal_to_repartition() -> None:
    sessions = pd.DataFrame(
        {
            "Trip": [10, 11, 12],
            "rows": [5, 10, 20],
            "start_us": [0, 100, 200],
            "end_us": [50, 150, 250],
        }
    )
    frozen = sessions.assign(split=["train", "validation", "test"])
    result = inherit_splits(sessions.iloc[::-1], frozen)
    assert result.split.tolist() == ["train", "validation", "test"]
    assert result.groupby("Trip").split.nunique().max() == 1
    changed = sessions.copy()
    changed.loc[0, "rows"] += 1
    with pytest.raises(ValueError, match="refusing new boundaries"):
        inherit_splits(changed, frozen)
    with pytest.raises(ValueError):
        inherit_splits(sessions.iloc[:2], frozen)


def test_sorted_hash_lookup_equivalence() -> None:
    values = np.array([0, 1, 2, 2, 123, 2**64 - 1], dtype=np.uint64)
    earlier = np.array([0, 2, 4, 2**64 - 1], dtype=np.uint64)
    assert np.array_equal(
        sorted_membership(values, earlier),
        pd.Series(values).isin(set(earlier)).to_numpy(),
    )
    assert not sorted_membership(values, earlier[:0]).any()


def test_pure_feature_matrix_and_frozen_scaler(
    telemetry: pd.DataFrame, battery_config: dict
) -> None:
    frame = audit_trip(telemetry, battery_config)
    frame["segment_id"] = frame.segment_in_trip
    frame["split"] = "train"
    state = fit_transformer(frame, battery_config["features"], battery_config)
    original_state = copy.deepcopy(state)
    output = transform(frame, state)
    metadata = companion_metadata(frame)
    assert output.columns.tolist() == ["HV_Bat_Voltage", "Pack_1_C_Temp", "SOC"]
    assert len(metadata) == len(output)
    assert metadata.source_row.tolist() == frame.source_row.tolist()
    assert "Timestamp" not in output and "source_row" not in output
    future = frame.copy()
    future["split"] = "test"
    future["SOC"] = 90
    transform(future, json.loads(json.dumps(state, sort_keys=True)))
    assert state == original_state
    with pytest.raises(ValueError, match="training-only"):
        fit_transformer(future, battery_config["features"], battery_config)


def test_battery_windows_safe_despite_drivetrain_dropout(
    telemetry: pd.DataFrame, battery_config: dict
) -> None:
    telemetry["Speed"] = -1.0
    frame = audit_trip(telemetry, battery_config)
    frame["split"] = "train"
    frame["segment_id"] = frame.segment_in_trip
    frame["export_eligible"] = frame.quality_eligible
    spec = dict(
        battery_config["temperature"],
        horizon_seconds=3,
        lookback_seconds=2,
        stride_seconds=1,
        tolerance_seconds=0.25,
    )
    windows, _ = make_windows(frame, spec)
    assert len(windows)
    assert windows.anchor_row.lt(windows.target_row).all()
    assert np.array_equal(
        windows.target_temperature_c, frame.Pack_1_C_Temp.iloc[windows.target_row]
    )
    # An actual gap must split windows even if all battery fields remain available.
    telemetry.loc[32:, "Timestamp"] += 2_000_000
    frame = audit_trip(telemetry, battery_config)
    frame["split"] = "train"
    frame["segment_id"] = frame.segment_in_trip
    frame["export_eligible"] = frame.quality_eligible
    windows, _ = make_windows(frame, spec)
    for row in windows.itertuples():
        interval = frame.iloc[row.input_start_row : row.target_row + 1]
        assert interval.segment_id.nunique() == 1
        assert interval.Timestamp.diff().dropna().le(1e6).all()
    frame.loc[0, "Trip"] = 99
    with pytest.raises(ValueError, match="boundary"):
        make_windows(frame, spec)


def test_original_artifacts_and_config_unchanged(battery_config: dict) -> None:
    parent = (
        ROOT
        / "ml/artifacts/nissan_leaf_2018/preparation"
        / battery_config["parent_run_id"]
    )
    if not parent.exists():
        pytest.skip("Parent preparation artifacts are Git-ignored")
    original, hashes = verify_parent(ROOT, battery_config)
    assert original["run_id"] == "d7e9e32e1ff2981a"
    assert len(hashes) == len(original["outputs"]) + 2


def test_tampered_parent_is_rejected(tmp_path: Path, battery_config: dict) -> None:
    run = battery_config["parent_run_id"]
    parent = tmp_path / "ml/artifacts/nissan_leaf_2018/preparation" / run
    parent.mkdir(parents=True)
    old_config = tmp_path / "ml/notebooks/nissan_leaf_2018/config/preparation.json"
    old_config.parent.mkdir(parents=True)
    old_config.write_text("{}\n")
    payload = parent / "artifact.txt"
    payload.write_text("synthetic code-test payload\n")
    manifest = parent / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"run_id": run, "outputs": {payload.name: {"sha256": digest(payload)}}}
        )
    )
    config = dict(
        battery_config,
        parent_manifest_sha256=digest(manifest),
        original_config_sha256=digest(old_config),
    )
    verify_parent(tmp_path, config)
    payload.write_text("changed\n")
    with pytest.raises(ValueError, match="artifact checksum"):
        verify_parent(tmp_path, config)


def test_battery_release_integrity_when_present(battery_config: dict) -> None:
    path = ROOT / "ml/reports/nissan_leaf_2018/tables/battery_only/summary.json"
    if not path.exists():
        pytest.skip("Run battery preparation to create integration outputs")
    summary = json.loads(path.read_text())
    assert summary["validation"]["passed"]
    assert summary["run_id"] != battery_config["parent_run_id"]
    assert [x["trips"] for x in summary["splits"]] == [142, 34, 51]
    for row in summary["splits"]:
        assert (
            row["source_rows"]
            == row["quality_excluded_rows"]
            + row["cross_split_repeat_exclusions"]
            + row["feature_rows"]
        )
    directory = ROOT / summary["artifact_directory"]
    if not directory.exists():
        pytest.skip("Battery preparation artifacts are Git-ignored")
    for name, info in summary["outputs"].items():
        assert digest(directory / name) == info["sha256"], name
    report = (
        ROOT / "ml/reports/nissan_leaf_2018/BATTERY_ONLY_PREPARATION_REPORT.md"
    ).read_text()
    assert all(f"## {n}." in report for n in range(1, 19))
