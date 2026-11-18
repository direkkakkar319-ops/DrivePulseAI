"""Tests for anomaly detector and RUL regressor interfaces and exports."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.src.models.anomaly_detector import XGBoostForecastAnomalyDetector
from ml.src.models.rul_regressor import (
    ExponentialCapacityTrendRUL,
    TheilSenCapacityTrendRUL,
)


def test_anomaly_detector_init_validation():
    """Verify validation of parameters in XGBoostForecastAnomalyDetector."""
    with pytest.raises(
        ValueError, match="target_names must contain at least one signal"
    ):
        XGBoostForecastAnomalyDetector(target_names=[])

    with pytest.raises(ValueError, match="threshold_quantile must be between 0 and 1"):
        XGBoostForecastAnomalyDetector(target_names=["speed"], threshold_quantile=1.5)

    with pytest.raises(ValueError, match="score_aggregation must be 'rms' or 'max'"):
        XGBoostForecastAnomalyDetector(target_names=["speed"], score_aggregation="sum")

    with pytest.raises(ValueError, match="invalid per-target forecast modes"):
        XGBoostForecastAnomalyDetector(
            target_names=["speed"],
            forecast_modes={"speed": "invalid_mode"},
        )


def test_anomaly_detector_persistence_mode_fit_predict(tmp_path: Path):
    """Test fast anomaly detector fit, calibrate, predict, and joblib save/load."""
    detector = XGBoostForecastAnomalyDetector(
        target_names=["target_val"],
        threshold_quantile=0.90,
        forecast_modes={"target_val": "persistence"},
    )

    # Synthetic features: target_val lag and current target_val
    X_train = pd.DataFrame(
        {"target_val": [10.0, 10.2, 10.1, 10.3, 10.2, 10.1, 10.2, 10.0, 10.1, 10.2]}
    )
    Y_train = pd.DataFrame(
        {"target_val": [10.1, 10.3, 10.2, 10.4, 10.3, 10.2, 10.3, 10.1, 10.2, 10.3]}
    )

    detector.fit(X_train, Y_train)
    assert detector.feature_names == ["target_val"]

    # Calibrate learns residual scale and threshold
    detector.calibrate(X_train, Y_train)
    assert detector.threshold is not None
    assert detector.residual_scale is not None

    # Normal row: small difference
    X_test = pd.DataFrame({"target_val": [10.0, 10.0]})
    Y_normal = pd.DataFrame({"target_val": [10.1, 10.1]})
    pred_normal = detector.predict(X_test, Y_normal)
    assert "anomaly_score" in pred_normal.columns
    assert "is_novel" in pred_normal.columns

    # Anomalous row: large divergence
    Y_anomaly = pd.DataFrame({"target_val": [50.0, 50.0]})
    pred_anomaly = detector.predict(X_test, Y_anomaly)
    assert (
        pred_anomaly.iloc[0]["is_novel"] is True
        or pred_anomaly.iloc[0]["anomaly_score"] > pred_normal.iloc[0]["anomaly_score"]
    )

    # Save & reload
    model_path = tmp_path / "model.joblib"
    detector.save(model_path)
    loaded = XGBoostForecastAnomalyDetector.load(model_path)
    assert loaded.threshold == detector.threshold
    assert loaded.feature_names == detector.feature_names


def test_theilsen_rul_regressor_validation():
    """Verify parameter and data validation in TheilSenCapacityTrendRUL."""
    with pytest.raises(ValueError, match="lookback_cycles must be positive"):
        TheilSenCapacityTrendRUL(lookback_cycles=0)

    with pytest.raises(ValueError, match="min_observations must be at least two"):
        TheilSenCapacityTrendRUL(min_observations=1)

    regressor = TheilSenCapacityTrendRUL()
    missing_cols = pd.DataFrame({"cycle": [1, 2]})
    with pytest.raises(ValueError, match="observations are missing required columns"):
        regressor.estimate(missing_cols, as_of_cycle=2)


def test_theilsen_rul_regressor_lifecycle():
    """Test RUL estimation across insufficient history, threshold crossed, and normal fade."""
    regressor = TheilSenCapacityTrendRUL(lookback_cycles=1000, min_observations=4)

    # Insufficient history (< 4 observations)
    short_df = pd.DataFrame(
        {
            "characterization_cycle": [100, 200],
            "capacity_1c_discharge_mah": [2000.0, 1980.0],
            "eol_threshold_capacity_mah": [1600.0, 1600.0],
        }
    )
    res_short = regressor.estimate(short_df, as_of_cycle=200)
    assert res_short["status"] == "insufficient_history"
    assert res_short["rul_cycles"] is None

    # Normal degradation series (e.g. 5 characterizations, losing ~0.1 mAh per cycle)
    cycles = [100, 200, 300, 400, 500]
    capacities = [2000.0, 1990.0, 1980.0, 1970.0, 1960.0]  # slope = -0.1 mAh/cycle
    normal_df = pd.DataFrame(
        {
            "characterization_cycle": cycles,
            "capacity_1c_discharge_mah": capacities,
            "eol_threshold_capacity_mah": [1600.0] * 5,
        }
    )
    res_normal = regressor.estimate(normal_df, as_of_cycle=500)
    assert res_normal["status"] == "ok"
    assert res_normal["rul_cycles"] is not None
    # Remaining capacity = 1960 - 1600 = 360 mAh. Slope = -0.1 mAh/cycle. RUL = 3600 cycles.
    assert res_normal["rul_cycles"] == pytest.approx(3600.0, rel=0.05)

    # Threshold already crossed
    crossed_df = pd.DataFrame(
        {
            "characterization_cycle": cycles,
            "capacity_1c_discharge_mah": [1590.0, 1580.0, 1570.0, 1560.0, 1550.0],
            "eol_threshold_capacity_mah": [1600.0] * 5,
        }
    )
    res_crossed = regressor.estimate(crossed_df, as_of_cycle=500)
    assert res_crossed["status"] == "threshold_already_crossed"
    assert res_crossed["rul_cycles"] == 0.0


def test_exponential_rul_regressor():
    """Verify ExponentialCapacityTrendRUL estimation on decaying capacity."""
    regressor = ExponentialCapacityTrendRUL(lookback_cycles=1000, min_observations=4)

    cycles = [100, 200, 300, 400, 500]
    # Exponential decay C(t) = C0 * exp(-lambda * t)
    capacities = [2000.0 * np.exp(-0.0001 * c) for c in cycles]
    df = pd.DataFrame(
        {
            "characterization_cycle": cycles,
            "capacity_1c_discharge_mah": capacities,
            "eol_threshold_capacity_mah": [1600.0] * 5,
        }
    )
    res = regressor.estimate(df, as_of_cycle=500)
    assert res["status"] == "ok"
    assert res["rul_cycles"] is not None
    assert res["rul_cycles"] > 0
