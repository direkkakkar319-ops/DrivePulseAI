"""Tests for the rolling Z-score battery trend anomaly and drift detector."""

import numpy as np
import pandas as pd
import pytest

from ml.src.scoring.trend_anomaly import BatteryTrendAnomalyDetector


def _generate_trend_data(
    n_days: int = 25,
    base_spread: float = 0.5,
    soh_drop_per_day: float = 0.02,
    km_per_day: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base_time = 1_600_000_000_000_000
    day_us = 86_400 * 1_000_000
    rows = []
    for i in range(n_days):
        t = base_time + i * day_us
        odo = 20000.0 + i * km_per_day
        soh = 95.0 - i * soh_drop_per_day
        t1 = 25.0 + rng.normal(0, 0.2)
        t2 = 25.0 - base_spread / 2 + rng.normal(0, 0.2)
        t4 = 25.0 + base_spread / 2 + rng.normal(0, 0.2)
        avg_temp = (t1 + t2 + t4) / 3.0
        ambient = 20.0 + rng.normal(0, 0.5)
        rows.append({
            "Timestamp": t,
            "Odometer": odo,
            "SOH": soh,
            "Pack_1_C_Temp": t1,
            "Pack_2_C_Temp": t2,
            "Pack_4_C_Temp": t4,
            "Pack_Avg_C_Temp": avg_temp,
            "Ambient_C_Temp": ambient,
            "HV_Bat_Voltage": 380.0 - rng.normal(0, 1.0),
        })
    return pd.DataFrame(rows)


def test_trend_detector_init_validation():
    # Valid
    det = BatteryTrendAnomalyDetector()
    assert det.window_size == 14
    assert det.min_history_points == 7
    assert det.warning_z == 2.5
    assert det.critical_z == 3.5
    assert det.consecutive_points == 2

    # Invalid window
    with pytest.raises(ValueError, match="window_size must be at least 3"):
        BatteryTrendAnomalyDetector(window_size=2)

    # Invalid min history
    with pytest.raises(ValueError, match="min_history_points must be at least 3"):
        BatteryTrendAnomalyDetector(min_history_points=2)
    with pytest.raises(ValueError, match="min_history_points must be at least 3 and <= window_size"):
        BatteryTrendAnomalyDetector(window_size=10, min_history_points=12)

    # Invalid thresholds
    with pytest.raises(ValueError, match="warning_z must be positive"):
        BatteryTrendAnomalyDetector(warning_z=-1.0)
    with pytest.raises(ValueError, match="warning_z must be positive and critical_z > warning_z"):
        BatteryTrendAnomalyDetector(warning_z=3.0, critical_z=2.5)

    # Invalid consecutive points
    with pytest.raises(ValueError, match="consecutive_points must be at least 1"):
        BatteryTrendAnomalyDetector(consecutive_points=0)


def test_trend_detector_empty_and_insufficient_history():
    det = BatteryTrendAnomalyDetector(window_size=14, min_history_points=7)

    # Empty
    res_empty = det.analyze(pd.DataFrame())
    assert res_empty["status"] == "empty_input"
    assert not res_empty["is_drift_detected"]

    # Only 5 days (need min 7 + 1 = 8)
    df_short = _generate_trend_data(n_days=5)
    res_short = det.analyze(df_short)
    assert res_short["status"] == "insufficient_history"
    assert not res_short["is_drift_detected"]


def test_trend_detector_normal_operation():
    """Stable multi-day telemetry should not produce drift alerts."""
    det = BatteryTrendAnomalyDetector(window_size=14, min_history_points=7)
    df = _generate_trend_data(n_days=25)
    res = det.analyze(df)

    assert res["status"] == "ok"
    assert res["is_drift_detected"] is False
    assert res["drift_alerts_count"] == 0
    assert len(res["alerts"]) == 0
    assert "pack_temp_spread" in res["signal_details"]
    assert res["signal_details"]["pack_temp_spread"]["status"] == "normal"


def test_trend_detector_pack_thermal_spread_drift():
    """Gradual widening of module temperature delta must trigger a drift alert."""
    det = BatteryTrendAnomalyDetector(
        window_size=14,
        min_history_points=7,
        warning_z=2.5,
        critical_z=3.5,
        consecutive_points=2,
    )
    df = _generate_trend_data(n_days=25)

    # Induce thermal spread drift on the last 2 days on Pack_1
    df.loc[23, "Pack_1_C_Temp"] = 33.0  # ~8°C above baseline of ~25°C
    df.loc[24, "Pack_1_C_Temp"] = 34.0

    res = det.analyze(df)
    assert res["status"] == "ok"
    assert res["is_drift_detected"] is True
    assert res["drift_alerts_count"] >= 1

    alert = next(a for a in res["alerts"] if a["signal"] == "pack_temp_spread")
    assert alert["severity"] in {"warning", "critical"}
    assert alert["z_score"] >= 2.5
    assert alert["consecutive_days"] >= 2
    assert "standard deviations" in alert["explanation"]
    assert "Battery Pack Temperature Spread" in alert["explanation"]


def test_trend_detector_accelerated_soh_decline_drift():
    """Sudden acceleration in SOH degradation rate must trigger an alert."""
    det = BatteryTrendAnomalyDetector(
        window_size=14,
        min_history_points=7,
        warning_z=2.5,
        consecutive_points=2,
    )
    df = _generate_trend_data(n_days=25, soh_drop_per_day=0.01)

    # Induce accelerated SOH degradation on last 2 days
    # (e.g. drops by 0.5% each day instead of 0.01%)
    df.loc[23, "SOH"] = df.loc[22, "SOH"] - 0.40
    df.loc[24, "SOH"] = df.loc[23, "SOH"] - 0.45

    res = det.analyze(df)
    assert res["status"] == "ok"
    assert res["is_drift_detected"] is True
    alert = next(a for a in res["alerts"] if a["signal"] == "soh_decline_rate_per_kkm")
    assert alert["z_score"] >= 2.5
    assert "SOH Degradation Rate" in alert["label"]
