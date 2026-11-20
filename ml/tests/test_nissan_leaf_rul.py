"""Tests for the Nissan Leaf RUL estimator, battery health integration, and bootstrap confidence intervals."""

import numpy as np
import pandas as pd
import pytest

from ml.src.models.nissan_leaf_rul import NissanLeafRUL


def _make_leaf_data(
    days: int = 15,
    start_soh: float = 95.0,
    soh_decline_per_day: float = 0.1,
    start_odometer: float = 10000.0,
    km_per_day: float = 100.0,
    base_timestamp_us: int = 1_600_000_000_000_000,
    include_context: bool = True,
) -> pd.DataFrame:
    """Helper to synthesize valid multi-day Leaf telemetry."""
    rows = []
    day_us = 86_400 * 1_000_000
    for i in range(days):
        t = base_timestamp_us + i * day_us
        soh = start_soh - i * soh_decline_per_day
        odo = start_odometer + i * km_per_day
        row = {
            "Timestamp": t,
            "Odometer": odo,
            "SOH": soh,
        }
        if include_context:
            row["Pack_Avg_C_Temp"] = 25.0 + (i % 3) * 0.5
            row["SOC"] = 70.0 + (i % 4) * 2.0
            row["HV_Bat_Voltage"] = 385.0 - (i % 2) * 4.0
        rows.append(row)
    return pd.DataFrame(rows)


def test_nissan_leaf_rul_init_validation():
    """Verify initialization parameter validation."""
    # Valid default init
    estimator = NissanLeafRUL()
    assert estimator.eol_threshold_soh_pct == 80.0
    assert estimator.lookback_days == 365
    assert estimator.min_daily_observations == 30
    assert estimator.min_history_span_days == 90
    assert estimator.n_bootstrap == 100
    assert estimator.confidence_level_pct == 80.0

    # Invalid EOL thresholds
    with pytest.raises(
        ValueError, match="eol_threshold_soh_pct must be between 0 and 100"
    ):
        NissanLeafRUL(eol_threshold_soh_pct=0.0)

    with pytest.raises(
        ValueError, match="eol_threshold_soh_pct must be between 0 and 100"
    ):
        NissanLeafRUL(eol_threshold_soh_pct=100.0)

    with pytest.raises(
        ValueError, match="eol_threshold_soh_pct must be between 0 and 100"
    ):
        NissanLeafRUL(eol_threshold_soh_pct=-10.0)

    # Invalid lookback / minimum observations / span
    with pytest.raises(ValueError, match="lookback_days and minimum span must be positive"):
        NissanLeafRUL(lookback_days=0)

    with pytest.raises(ValueError, match="lookback_days and minimum span must be positive"):
        NissanLeafRUL(min_daily_observations=2)

    with pytest.raises(ValueError, match="lookback_days and minimum span must be positive"):
        NissanLeafRUL(min_history_span_days=0)

    # Invalid bootstrap parameters
    with pytest.raises(ValueError, match="n_bootstrap must be nonnegative"):
        NissanLeafRUL(n_bootstrap=-1)

    with pytest.raises(ValueError, match="confidence_level_pct must be between 0 and 100"):
        NissanLeafRUL(confidence_level_pct=0)

    with pytest.raises(ValueError, match="confidence_level_pct must be between 0 and 100"):
        NissanLeafRUL(confidence_level_pct=100)


def test_nissan_leaf_rul_missing_required_columns():
    """Missing Timestamp, Odometer, or SOH must raise a ValueError."""
    estimator = NissanLeafRUL()
    df_missing_soh = pd.DataFrame({"Timestamp": [1], "Odometer": [100]})
    with pytest.raises(ValueError, match="observations are missing required columns"):
        estimator.estimate(df_missing_soh)

    df_missing_odo = pd.DataFrame({"Timestamp": [1], "SOH": [90]})
    with pytest.raises(ValueError, match="observations are missing required columns"):
        estimator.estimate(df_missing_odo)


def test_nissan_leaf_rul_empty_or_nonfinite_data():
    """Empty dataframe or data with non-finite values should return no_valid_history."""
    estimator = NissanLeafRUL()

    empty_df = pd.DataFrame(columns=["Timestamp", "Odometer", "SOH"])
    res_empty = estimator.estimate(empty_df)
    assert res_empty["status"] == "no_valid_history"
    assert res_empty["rul_km"] is None

    invalid_df = pd.DataFrame(
        {
            "Timestamp": [np.nan, 1000],
            "Odometer": [100.0, np.nan],
            "SOH": [np.nan, 120.0],  # 120% is outside [0, 100]
        }
    )
    res_invalid = estimator.estimate(invalid_df)
    assert res_invalid["status"] == "no_valid_history"
    assert res_invalid["rul_km"] is None


def test_nissan_leaf_rul_threshold_already_reached():
    """When current SOH <= threshold, return threshold_reached and 0.0 rul_km."""
    estimator = NissanLeafRUL(eol_threshold_soh_pct=80.0)
    df = _make_leaf_data(days=10, start_soh=80.0, soh_decline_per_day=0.1)
    # Final SOH will be 79.1 <= 80.0
    res = estimator.estimate(df)
    assert res["status"] == "threshold_reached"
    assert res["rul_km"] == 0.0
    assert res["rul_km_p10"] == 0.0
    assert res["rul_km_p90"] == 0.0
    assert res["health_score"] == 1
    assert res["health_label"] == "end_of_life_range"


def test_nissan_leaf_rul_insufficient_history():
    """Fewer than min_daily_observations days should return insufficient_history."""
    estimator = NissanLeafRUL(min_daily_observations=8, min_history_span_days=5)
    # Only 5 days
    df = _make_leaf_data(days=5, start_soh=95.0)
    res = estimator.estimate(df)
    assert res["status"] == "insufficient_history"
    assert res["rul_km"] is None
    assert res["daily_observations_used"] == 5


def test_nissan_leaf_rul_insufficient_odometer_variation():
    """When odometer readings are static (no distance accumulated), variation is insufficient."""
    estimator = NissanLeafRUL(min_daily_observations=8, min_history_span_days=5)
    df = _make_leaf_data(days=10, start_soh=95.0, km_per_day=0.0)
    res = estimator.estimate(df)
    assert res["status"] == "insufficient_odometer_variation"
    assert res["rul_km"] is None


def test_nissan_leaf_rul_non_declining_trend():
    """When SOH is increasing or flat over time, return non_declining_trend."""
    estimator = NissanLeafRUL(min_daily_observations=8, min_history_span_days=5)
    # Positive slope: SOH increasing by 0.1 each day
    df = _make_leaf_data(days=10, start_soh=90.0, soh_decline_per_day=-0.1)
    res = estimator.estimate(df)
    assert res["status"] == "non_declining_trend"
    assert res["rul_km"] is None
    assert res["soh_slope_pct_per_1000_km"] > 0


def test_nissan_leaf_rul_valid_projection():
    """Successful RUL estimation on degrading battery history with bootstrap intervals."""
    estimator = NissanLeafRUL(
        eol_threshold_soh_pct=80.0,
        min_daily_observations=8,
        min_history_span_days=10,
        n_bootstrap=50,
        confidence_level_pct=80.0,
    )
    df = _make_leaf_data(
        days=15,
        start_soh=92.0,
        soh_decline_per_day=0.05,
        start_odometer=20000.0,
        km_per_day=100.0,
    )
    res = estimator.estimate(df)
    assert res["status"] == "ok"
    assert res["rul_km"] is not None
    assert res["rul_km"] > 0
    assert res["current_soh_pct"] == pytest.approx(92.0 - 14 * 0.05, abs=0.01)
    assert res["current_odometer_km"] == 20000.0 + 14 * 100.0
    assert res["health_score"] in {3, 4}
    assert res["soh_slope_pct_per_1000_km"] < 0
    assert res["estimated_days_to_threshold"] > 0
    assert res["average_calendar_distance_km_per_day"] == pytest.approx(100.0)
    assert (
        res["validation_status"]
        == "unvalidated_extrapolation_single_vehicle_no_threshold_crossing"
    )

    # Bootstrap confidence interval checks
    assert res["confidence_interval"] is not None
    assert res["rul_km_p10"] is not None
    assert res["rul_km_p50"] is not None
    assert res["rul_km_p90"] is not None
    assert res["rul_km_p10"] <= res["rul_km_p50"] <= res["rul_km_p90"]
    assert res["confidence_interval"]["level_pct"] == 80.0
    assert res["confidence_interval"]["bootstrap_iterations_valid"] >= 10
    assert res["estimated_days_to_threshold_p10"] is not None
    assert res["estimated_days_to_threshold_p90"] is not None
    assert res["estimated_days_to_threshold_p10"] <= res["estimated_days_to_threshold_p90"]


def test_nissan_leaf_rul_context_summary():
    """Context columns (Pack_Avg_C_Temp, SOC, HV_Bat_Voltage) are summarized."""
    estimator = NissanLeafRUL(min_daily_observations=5, min_history_span_days=5)
    df = _make_leaf_data(days=10, include_context=True)
    res = estimator.estimate(df)
    assert "context_summary" in res
    assert "Pack_Avg_C_Temp" in res["context_summary"]
    assert "SOC" in res["context_summary"]
    assert "HV_Bat_Voltage" in res["context_summary"]
    assert res["context_summary"]["Pack_Avg_C_Temp"] > 0
    assert res["context_summary"]["SOC"] > 0
    assert res["context_summary"]["HV_Bat_Voltage"] > 0
