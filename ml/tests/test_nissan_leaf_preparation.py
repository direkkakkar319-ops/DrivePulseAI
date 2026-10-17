"""Test preparation safety with explicitly synthetic code fixtures, never training data."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/src"))
from nissan_leaf_preparation.core import (
    AUDIT_COLUMNS,
    FLAGS,
    audit_trip,
    chronological_split,
    fingerprints,
    fit_transformer,
    make_windows,
    parse_time,
    transform,
    validate_config,
    validate_schema,
)
from nissan_leaf_preparation.pipeline import trip_chunks


@pytest.fixture
def config() -> dict:
    return json.loads(
        (ROOT / "ml/notebooks/nissan_leaf_2018/config/preparation.json").read_text()
    )


@pytest.fixture
def telemetry() -> pd.DataFrame:
    """Synthetic code-only fixture; no file is exported as real telemetry."""
    n = 64
    frame = pd.DataFrame({col: np.zeros(n) for col in AUDIT_COLUMNS})
    frame["source_row"] = np.arange(n)
    frame["index"] = np.arange(n) + 100
    frame["Trip"] = 5
    frame["Timestamp"] = 1605186068000000 + np.arange(n) * 250000
    frame["Speed"] = 30.0
    frame["SOC"] = 60.0
    frame["SOH"] = 95.0
    frame["Motor_Temp"] = 40.0
    frame["HV_Bat_Voltage"] = 360.0
    frame["HV_Bat_Current_2"] = -10
    frame["Instant_kW"] = -3.6
    for pack in [1, 2, 4]:
        frame[f"Pack_{pack}_C_Temp"] = 20 + np.arange(n) / 100
    frame["Pack_Avg_C_Temp"] = frame.Pack_1_C_Temp
    for tire in ["TP_FR", "TP_FL", "TP_RR", "TP_RL"]:
        frame[tire] = 35
    return frame


def test_config_and_feature_selection(config: dict) -> None:
    validate_config(config)
    for feature in ["Timestamp", "Trip", "SOH", "Instant_kW", "HV_Bat_Current_2"]:
        bad = copy.deepcopy(config)
        bad["features"].append(feature)
        with pytest.raises(ValueError):
            validate_config(bad)


def test_invalid_config_policies(config: dict) -> None:
    for key, value in [
        ("source_version", "processed"),
        ("scaling", "PCA"),
        ("missing_policy", "backfill"),
        ("split_embargo_seconds", 1),
    ]:
        bad = dict(config, **{key: value})
        with pytest.raises(ValueError):
            validate_config(bad)


def test_schema() -> None:
    validate_schema(["Trip", "Timestamp"], ["Trip", "Timestamp"])
    for bad in [["Trip"], ["Timestamp", "Trip"], ["Trip", "Trip"]]:
        with pytest.raises(ValueError):
            validate_schema(bad, ["Trip", "Timestamp"])


def test_timestamp_parse(telemetry: pd.DataFrame) -> None:
    parsed = parse_time(telemetry.Timestamp)
    assert str(parsed.dt.tz) == "UTC"
    assert parsed.diff().dropna().dt.total_seconds().eq(0.25).all()
    for bad in [
        pd.Series([np.nan]),
        pd.Series(["invalid"]),
        pd.Series([1.5]),
        pd.Series([np.inf]),
    ]:
        with pytest.raises(ValueError):
            parse_time(bad)


def test_ordering_and_trip_scope(telemetry: pd.DataFrame, config: dict) -> None:
    with pytest.raises(ValueError, match="reversal"):
        audit_trip(telemetry.iloc[::-1], config)
    telemetry.loc[1, "Trip"] = 7
    with pytest.raises(ValueError, match="one nonmissing trip"):
        audit_trip(telemetry, config)


def test_missing_and_sentinel_are_distinct(
    telemetry: pd.DataFrame, config: dict
) -> None:
    telemetry.loc[0, "Speed"] = np.nan
    telemetry.loc[1, "Pack_1_C_Temp"] = -1
    telemetry.loc[2, "Torque"] = -1
    before = telemetry.copy(deep=True)
    frame = audit_trip(telemetry, config)
    pd.testing.assert_frame_equal(telemetry, before)
    assert frame.quality_flags.iloc[0] & FLAGS["missing_candidate"][0]
    assert frame.quality_flags.iloc[1] & FLAGS["pack_sentinel"][0]
    assert not frame.quality_eligible.iloc[:2].any()
    assert frame.quality_eligible.iloc[
        2
    ]  # negative torque is legitimate, not blanket-masked


def test_quality_categories_and_nonfeature_flags(
    telemetry: pd.DataFrame, config: dict
) -> None:
    telemetry.loc[0, "SOC"] = 101
    telemetry.loc[1, "HV_Bat_Voltage"] = 655.35
    telemetry.loc[2, "SOH"] = 0
    telemetry.loc[3, "TP_FR"] = 0
    telemetry.loc[4, "Motor_Temp"] = np.inf
    telemetry.loc[5, "Motor_Temp"] = -40  # statistical extreme alone must survive
    frame = audit_trip(telemetry, config)
    assert not frame.quality_eligible.iloc[[0, 1, 4]].any()
    assert frame.quality_eligible.iloc[[2, 3, 5]].all()
    assert frame.quality_flags.iloc[2] & FLAGS["soh_zero"][0]


def test_formula_flags_do_not_repair(telemetry: pd.DataFrame, config: dict) -> None:
    telemetry.loc[0, "Instant_kW"] = 100
    telemetry.loc[1, "Pack_Avg_C_Temp"] = 100
    frame = audit_trip(telemetry, config)
    assert frame.quality_flags.iloc[0] & FLAGS["power_formula"][0]
    assert frame.quality_flags.iloc[1] & FLAGS["temperature_formula"][0]
    assert frame.Instant_kW.iloc[0] == 100
    assert frame.Pack_Avg_C_Temp.iloc[1] == 100
    assert frame.quality_eligible.all()


def test_gaps_and_duplicate_times(telemetry: pd.DataFrame, config: dict) -> None:
    telemetry.loc[32:, "Timestamp"] += 2000000
    frame = audit_trip(telemetry, config)
    assert frame.segment_in_trip.nunique() == 2
    telemetry.loc[10, "Timestamp"] = telemetry.Timestamp.iloc[9]
    frame = audit_trip(telemetry, config)
    assert not frame.quality_eligible.iloc[[9, 10]].any()
    assert frame.segment_in_trip.iloc[11] != frame.segment_in_trip.iloc[9]


def trip_table() -> pd.DataFrame:
    start = 1605186068000000 + np.arange(10) * 86400000000
    return pd.DataFrame(
        {
            "Trip": np.arange(10),
            "rows": 100,
            "start_us": start,
            "end_us": start + 60000000,
        }
    )


def test_grouped_split_exclusive_and_deterministic(config: dict) -> None:
    split = chronological_split(trip_table(), config)
    pd.testing.assert_frame_equal(
        split, chronological_split(trip_table().sample(frac=1, random_state=1), config)
    )
    assert split.Trip.nunique() == 10
    assert split.groupby("Trip").split.nunique().max() == 1
    assert list(split.split.drop_duplicates()) == ["train", "validation", "test"]


def test_split_overlap_or_missing_boundaries_blocks(config: dict) -> None:
    trips = trip_table()
    trips.loc[0, "end_us"] = trips.start_us.iloc[1]
    with pytest.raises(ValueError, match="overlapping"):
        chronological_split(trips, config)
    with pytest.raises(ValueError, match="boundaries"):
        chronological_split(trip_table().iloc[:2], config)


def test_transform_fit_rejects_validation(
    telemetry: pd.DataFrame, config: dict
) -> None:
    telemetry["split"] = "validation"
    with pytest.raises(ValueError, match="training-only"):
        fit_transformer(telemetry, config["features"], config)


@pytest.mark.parametrize("scaling", ["robust", "standard", "none"])
def test_training_transform_and_no_test_leakage(
    telemetry: pd.DataFrame, config: dict, scaling: str
) -> None:
    config = dict(config, scaling=scaling)
    telemetry["split"] = "train"
    state = fit_transformer(telemetry, config["features"], config)
    frozen = json.dumps(state, sort_keys=True)
    test = telemetry.copy()
    test["split"] = "test"
    test["Pack_1_C_Temp"] = 1000
    result = transform(test, state)
    assert json.dumps(state, sort_keys=True) == frozen
    assert result.columns.tolist() == config["features"]
    assert state["center"]["Pack_1_C_Temp"] < 100
    assert np.isfinite(result).all().all()
    pd.testing.assert_frame_equal(result, transform(test, json.loads(frozen)))


def test_optional_train_median_and_indicators(
    telemetry: pd.DataFrame, config: dict
) -> None:
    config = dict(config, missing_policy="training_median")
    telemetry["split"] = "train"
    telemetry.loc[0, "Speed"] = np.nan
    state = fit_transformer(telemetry, config["features"], config)
    test = telemetry.iloc[:1].copy()
    test["split"] = "test"
    output = transform(test, state)
    assert state["median"]["Speed"] == 30
    assert output.Speed__missing.iloc[0] == 1
    assert output.Speed.iloc[0] == 0
    assert np.isnan(test.Speed.iloc[0])


def window_frame(telemetry: pd.DataFrame, config: dict) -> pd.DataFrame:
    frame = audit_trip(telemetry, config)
    frame["segment_id"] = frame.segment_in_trip
    frame["split"] = "train"
    frame["export_eligible"] = frame.quality_eligible
    return frame


def spec(config: dict) -> dict:
    return dict(
        config["temperature"],
        lookback_seconds=2,
        horizon_seconds=3,
        tolerance_seconds=0.25,
        stride_seconds=1,
    )


def test_window_future_target_not_input(telemetry: pd.DataFrame, config: dict) -> None:
    frame = window_frame(telemetry, config)
    windows, counts = make_windows(frame, spec(config))
    assert len(windows) > 0
    assert counts["anchors_considered"] == sum(
        counts[key] for key in counts if key != "anchors_considered"
    )
    assert (windows.target_us > windows.anchor_us).all()
    assert (windows.input_start_row <= windows.anchor_row).all()
    assert (windows.anchor_row < windows.target_row).all()
    assert np.array_equal(
        windows.target_temperature_c, frame.Pack_1_C_Temp.iloc[windows.target_row]
    )


def test_window_no_future_dependency_in_input_selection(
    telemetry: pd.DataFrame, config: dict
) -> None:
    frame = window_frame(telemetry, config)
    before, _ = make_windows(frame, spec(config))
    changed = frame.copy()
    target_row = int(before.target_row.iloc[-1])
    changed.loc[target_row, "Pack_1_C_Temp"] += 10
    after, _ = make_windows(changed, spec(config))
    pd.testing.assert_frame_equal(
        before.drop(columns=["target_temperature_c", "temperature_change_c"]),
        after.drop(columns=["target_temperature_c", "temperature_change_c"]),
    )
    assert (
        after.target_temperature_c.iloc[-1] == before.target_temperature_c.iloc[-1] + 10
    )


def test_window_boundaries_and_excluded_intervals(
    telemetry: pd.DataFrame, config: dict
) -> None:
    telemetry.loc[32:, "Timestamp"] += 2000000
    frame = window_frame(telemetry, config)
    frame.loc[10, "export_eligible"] = False
    windows, _ = make_windows(frame, spec(config))
    for row in windows.itertuples():
        interval = frame.iloc[row.input_start_row : row.target_row + 1]
        assert interval.export_eligible.all()
        assert interval.segment_id.nunique() == 1
    frame.loc[0, "split"] = "test"
    with pytest.raises(ValueError, match="boundary"):
        make_windows(frame, spec(config))


def test_window_rejects_filtered_source_rows(
    telemetry: pd.DataFrame, config: dict
) -> None:
    frame = window_frame(telemetry, config).drop(index=8)
    with pytest.raises(ValueError, match="full source rows"):
        make_windows(frame, spec(config))


def test_rounded_repeat_screen(telemetry: pd.DataFrame, config: dict) -> None:
    left = telemetry.iloc[:1].copy()
    right = left.copy()
    right["source_row"] = 100000
    right["Trip"] = 999
    right["Speed"] += 0.001
    assert fingerprints(left, config)[0] == fingerprints(right, config)[0]
    right["Speed"] += 10
    assert fingerprints(left, config)[0] != fingerprints(right, config)[0]


def test_chunk_boundary_trip_handling(tmp_path: Path, telemetry: pd.DataFrame) -> None:
    telemetry.loc[32:, "Trip"] = 6
    path = tmp_path / "synthetic_code_fixture.csv"
    telemetry[AUDIT_COLUMNS].to_csv(path, index=False)
    chunks = list(trip_chunks(path, AUDIT_COLUMNS, 7))
    assert [len(g) for g in chunks] == [32, 32]
    assert pd.concat(chunks).source_row.tolist() == list(range(64))
    telemetry.loc[60:, "Trip"] = 5
    telemetry[AUDIT_COLUMNS].to_csv(path, index=False)
    with pytest.raises(ValueError, match="reused"):
        list(trip_chunks(path, AUDIT_COLUMNS, 7))


def test_completed_output_summary() -> None:
    path = (
        ROOT / "ml/reports/nissan_leaf_2018/tables/preparation/preparation_summary.json"
    )
    if not path.exists():
        pytest.skip(
            "Full-data integration report is generated by the preparation command"
        )
    result = json.loads(path.read_text())
    assert result["validation"]["passed"]
    assert result["audit"]["raw"]["rows"] == 2322105
    assert sum(s["source_rows"] for s in result["splits"]) == 2322105
    for split in result["splits"]:
        assert (
            split["source_rows"]
            == split["quality_excluded_rows"]
            + split["cross_split_repeat_exclusions"]
            + split["feature_rows"]
        )
    assert result["transformer"]["fit_rows"] == result["splits"][0]["feature_rows"]
    assert result["task_status"]["energy"] == "blocked"
