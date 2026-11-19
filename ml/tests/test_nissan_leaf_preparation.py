"""Tests for Nissan Leaf preparation primitives (quality audit, time parsing, scaling, splitting, windows)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.src.data.nissan_leaf_preparation.battery import (
    inherit_splits,
    sorted_membership,
)
from ml.src.data.nissan_leaf_preparation.core import (
    FLAGS,
    audit_trip,
    chronological_split,
    digest,
    fit_transformer,
    parse_time,
    transform,
    validate_config,
    validate_schema,
)


@pytest.fixture
def base_config() -> dict:
    return {
        "features": [
            "Speed",
            "Torque",
            "Motor_Temp",
            "HV_Bat_Voltage",
            "Pack_1_C_Temp",
            "SOC",
        ],
        "source_version": "raw",
        "missing_policy": "exclude",
        "scaling": "robust",
        "gap_seconds": 1.0,
        "voltage_review_max": 500.0,
        "temperature_sentinel_band": [-1.01, -0.99],
        "odometer_jump_km": 1.0,
        "odometer_jump_interval_seconds": 1.0,
        "formula_atol": 1e-08,
        "formula_rtol": 1e-08,
        "split_fractions": [0.7, 0.15, 0.15],
        "split_embargo_seconds": 95.0,
        "duplicate_round_decimals": {
            "Speed": 1,
            "Torque": 2,
            "Motor_Temp": 1,
            "HV_Bat_Voltage": 2,
            "Pack_1_C_Temp": 2,
            "SOC": 2,
        },
        "temperature": {
            "target": "Pack_1_C_Temp",
            "lookback_seconds": 30.0,
            "horizon_seconds": 60.0,
            "tolerance_seconds": 0.5,
            "stride_seconds": 10.0,
        },
        "typical_interval_band_seconds": [0.2, 0.3],
    }


def test_digest(tmp_path: Path):
    """Verify SHA-256 calculation matches hashlib directly."""
    f = tmp_path / "sample.txt"
    content = b"DrivePulseAI test content 12345"
    f.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert digest(f) == expected


def test_validate_schema():
    """Exact schema order and uniqueness are strictly checked."""
    validate_schema(["a", "b", "c"], ["a", "b", "c"])

    with pytest.raises(ValueError, match="Source schema mismatch"):
        validate_schema(["a", "b"], ["a", "b", "c"])

    with pytest.raises(ValueError, match="Source schema mismatch"):
        validate_schema(["a", "a", "b"], ["a", "a", "b"])


def test_parse_time():
    """Verify microsecond integer parsing to UTC datetime and error handling."""
    ts = pd.Series([1_600_000_000_000_000, 1_600_000_001_000_000])
    parsed = parse_time(ts)
    assert parsed.dt.tz is not None
    assert str(parsed.dt.tz) == "UTC"

    # Non-integer / float fraction raises
    with pytest.raises(ValueError, match="Invalid microsecond timestamp"):
        parse_time(pd.Series([1_600_000_000_000_000.5]))

    # Non-numeric string raises
    with pytest.raises(ValueError, match="Invalid microsecond timestamp"):
        parse_time(pd.Series(["not_a_time"]))


def test_validate_config(base_config):
    """Ensure valid config passes and violations raise appropriate errors."""
    validate_config(base_config)

    # Unknown feature
    bad_feat = base_config.copy()
    bad_feat["features"] = ["Speed", "UnknownFeature"]
    with pytest.raises(ValueError, match="Only reviewed, unique measurement features"):
        validate_config(bad_feat)

    # Bad split fractions
    bad_split = base_config.copy()
    bad_split["split_fractions"] = [0.5, 0.5]  # Not 3 fractions
    with pytest.raises(ValueError, match="Three positive split fractions"):
        validate_config(bad_split)

    # Short embargo
    bad_embargo = base_config.copy()
    bad_embargo["split_embargo_seconds"] = 10.0  # < 30 + 60 + 0.5
    with pytest.raises(ValueError, match="Embargo is shorter than full window span"):
        validate_config(bad_embargo)


def test_audit_trip(base_config):
    """Test trip audit quality flags, domain checks, and row categorization."""
    base_us = 1_600_000_000_000_000
    rows = []
    # 5 consecutive rows, 0.25s apart (250_000 us)
    for i in range(5):
        rows.append(
            {
                "Trip": 1,
                "Timestamp": base_us + i * 250_000,
                "Speed": 40.0 if i != 2 else -5.0,  # row 2 has negative speed
                "Torque": 50.0,
                "Motor_Temp": 35.0,
                "HV_Bat_Voltage": 380.0
                if i != 3
                else 600.0,  # row 3 triggers voltage_review (> 500)
                "Pack_1_C_Temp": 22.0,
                "Pack_2_C_Temp": 22.0,
                "Pack_4_C_Temp": 22.0,
                "Pack_Avg_C_Temp": 22.0,
                "SOC": 80.0 if i != 4 else 105.0,  # row 4 triggers soc_domain (> 100)
                "TP_FR": 32.0,
                "TP_FL": 32.0,
                "TP_RR": 32.0,
                "TP_RL": 32.0,
                "Odometer": 15000.0 + i * 0.01,
                "SOH": 92.0,
                "Instant_kW": 380.0 * 10.0 / 1000,
                "HV_Bat_Current_2": 10.0,
            }
        )
    df = pd.DataFrame(rows)

    audited = audit_trip(df, base_config)

    assert "quality_flags" in audited.columns
    assert "quality_eligible" in audited.columns
    assert "segment_in_trip" in audited.columns

    # Row 0 is clean
    assert bool(audited.loc[0, "quality_eligible"]) is True
    assert audited.loc[0, "quality_flags"] == 0

    # Row 2 flagged speed_negative
    speed_flag_bit = FLAGS["speed_negative"][0]
    assert audited.loc[2, "quality_flags"] & speed_flag_bit != 0

    # Row 3 flagged voltage_review
    voltage_flag_bit = FLAGS["voltage_review"][0]
    assert audited.loc[3, "quality_flags"] & voltage_flag_bit != 0

    # Row 4 flagged soc_domain
    soc_flag_bit = FLAGS["soc_domain"][0]
    assert audited.loc[4, "quality_flags"] & soc_flag_bit != 0


def test_fit_transformer_and_transform_robust(base_config):
    """Test robust scaling (median / IQR) fitting and transformation."""
    features = ["Speed", "Torque"]
    train_df = pd.DataFrame(
        {
            "Speed": [10.0, 20.0, 30.0, 40.0, 50.0],
            "Torque": [100.0, 110.0, 120.0, 130.0, 140.0],
            "split": ["train"] * 5,
        }
    )

    state = fit_transformer(train_df, features, base_config)
    assert state["scaling"] == "robust"
    assert state["median"]["Speed"] == 30.0
    assert state["median"]["Torque"] == 120.0

    eval_df = pd.DataFrame(
        {
            "Speed": [30.0, 50.0],
            "Torque": [120.0, 140.0],
        }
    )
    transformed = transform(eval_df, state)
    assert transformed.shape == (2, 2)
    # Center value transforms to 0.0
    assert pytest.approx(float(transformed.loc[0, "Speed"])) == 0.0
    assert pytest.approx(float(transformed.loc[0, "Torque"])) == 0.0


def test_transform_missing_policy_training_median(base_config):
    """Ensure training_median policy creates __missing indicator columns."""
    cfg = base_config.copy()
    cfg["missing_policy"] = "training_median"
    features = ["Speed"]

    train_df = pd.DataFrame(
        {
            "Speed": [10.0, 20.0, 30.0],
            "split": ["train"] * 3,
        }
    )
    state = fit_transformer(train_df, features, cfg)
    assert "Speed__missing" in state["output_features"]

    eval_df = pd.DataFrame({"Speed": [np.nan, 20.0]})
    transformed = transform(eval_df, state)
    assert "Speed__missing" in transformed.columns
    assert transformed.loc[0, "Speed__missing"] == 1.0
    assert transformed.loc[1, "Speed__missing"] == 0.0


def test_chronological_split(base_config):
    """Verify chronological whole-trip split assignments."""
    day_us = 86_400 * 1_000_000
    base_us = 1_600_000_000_000_000
    trips = pd.DataFrame(
        [
            {"Trip": 1, "start_us": base_us, "end_us": base_us + 1000, "rows": 100},
            {
                "Trip": 2,
                "start_us": base_us + day_us,
                "end_us": base_us + day_us + 1000,
                "rows": 100,
            },
            {
                "Trip": 3,
                "start_us": base_us + 2 * day_us,
                "end_us": base_us + 2 * day_us + 1000,
                "rows": 100,
            },
            {
                "Trip": 4,
                "start_us": base_us + 3 * day_us,
                "end_us": base_us + 3 * day_us + 1000,
                "rows": 100,
            },
        ]
    )
    cfg = base_config.copy()
    cfg["split_embargo_seconds"] = 1.0

    split_trips = chronological_split(trips, cfg)
    assert "split" in split_trips.columns
    unique_splits = set(split_trips.split.unique())
    assert {"train", "validation", "test"} <= unique_splits


def test_sorted_membership():
    """Verify numpy searchsorted fast membership tester."""
    reference = np.array([10, 20, 30, 40, 50], dtype=np.uint64)
    queries = np.array([5, 10, 25, 30, 55], dtype=np.uint64)
    mask = sorted_membership(queries, reference)
    expected = np.array([False, True, False, True, False], dtype=bool)
    np.testing.assert_array_equal(mask, expected)

    # Empty reference
    empty_mask = sorted_membership(queries, np.array([], dtype=np.uint64))
    assert not empty_mask.any()


def test_inherit_splits():
    """Verify session split inheritance matches frozen source trips exactly."""
    sessions = pd.DataFrame(
        [
            {"Trip": 1, "rows": 100, "start_us": 1000, "end_us": 2000},
            {"Trip": 2, "rows": 200, "start_us": 3000, "end_us": 4000},
            {"Trip": 3, "rows": 150, "start_us": 5000, "end_us": 6000},
        ]
    )
    frozen = pd.DataFrame(
        [
            {
                "Trip": 1,
                "rows": 100,
                "start_us": 1000,
                "end_us": 2000,
                "split": "train",
            },
            {
                "Trip": 2,
                "rows": 200,
                "start_us": 3000,
                "end_us": 4000,
                "split": "validation",
            },
            {"Trip": 3, "rows": 150, "start_us": 5000, "end_us": 6000, "split": "test"},
        ]
    )

    inherited = inherit_splits(sessions, frozen)
    assert inherited.split.tolist() == ["train", "validation", "test"]

    # Mismatched row counts must raise
    mismatched = sessions.copy()
    mismatched.loc[0, "rows"] = 99
    with pytest.raises(
        ValueError, match="Frozen split source trips/counts/timestamps differ"
    ):
        inherit_splits(mismatched, frozen)
