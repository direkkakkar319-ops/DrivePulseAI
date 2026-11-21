"""Tests for Nissan Leaf battery health score computation and band classification."""

import pytest

from ml.src.scoring.health_score import HEALTH_SCORE_BANDS, battery_health_score


def test_battery_health_score_very_healthy_band():
    """SOH >= 95.0 should be scored as 5 ('very_healthy')."""
    res_100 = battery_health_score(100.0)
    assert res_100["health_score"] == 5
    assert res_100["label"] == "very_healthy"
    assert res_100["soh_pct"] == 100.0

    res_95 = battery_health_score(95.0)
    assert res_95["health_score"] == 5
    assert res_95["label"] == "very_healthy"

    res_97_5 = battery_health_score(97.5)
    assert res_97_5["health_score"] == 5
    assert res_97_5["label"] == "very_healthy"


def test_battery_health_score_healthy_band():
    """90.0 <= SOH < 95.0 should be scored as 4 ('healthy')."""
    res_94_9 = battery_health_score(94.9)
    assert res_94_9["health_score"] == 4
    assert res_94_9["label"] == "healthy"

    res_90 = battery_health_score(90.0)
    assert res_90["health_score"] == 4
    assert res_90["label"] == "healthy"


def test_battery_health_score_moderate_degradation_band():
    """85.0 <= SOH < 90.0 should be scored as 3 ('moderate_degradation')."""
    res_89_9 = battery_health_score(89.9)
    assert res_89_9["health_score"] == 3
    assert res_89_9["label"] == "moderate_degradation"

    res_85 = battery_health_score(85.0)
    assert res_85["health_score"] == 3
    assert res_85["label"] == "moderate_degradation"


def test_battery_health_score_degraded_band():
    """80.0 <= SOH < 85.0 should be scored as 2 ('degraded')."""
    res_84_9 = battery_health_score(84.9)
    assert res_84_9["health_score"] == 2
    assert res_84_9["label"] == "degraded"

    res_80 = battery_health_score(80.0)
    assert res_80["health_score"] == 2
    assert res_80["label"] == "degraded"


def test_battery_health_score_end_of_life_band():
    """SOH < 80.0 should be scored as 1 ('end_of_life_range')."""
    res_79_9 = battery_health_score(79.9)
    assert res_79_9["health_score"] == 1
    assert res_79_9["label"] == "end_of_life_range"

    res_50 = battery_health_score(50.0)
    assert res_50["health_score"] == 1
    assert res_50["label"] == "end_of_life_range"

    res_0 = battery_health_score(0.0)
    assert res_0["health_score"] == 1
    assert res_0["label"] == "end_of_life_range"


def test_battery_health_score_response_schema():
    """Validate all response dictionary keys and structure."""
    result = battery_health_score(91.2)
    expected_keys = {
        "health_score",
        "score_scale",
        "soh_pct",
        "label",
        "bands",
        "threshold_note",
    }
    assert set(result.keys()) == expected_keys
    assert result["score_scale"] == "1=lowest health, 5=highest health"
    assert result["bands"] == HEALTH_SCORE_BANDS
    assert isinstance(result["threshold_note"], str)


def test_battery_health_score_invalid_range():
    """Values < 0 or > 100 must raise ValueError."""
    with pytest.raises(
        ValueError, match=r"soh_pct must be finite and within \[0, 100\]"
    ):
        battery_health_score(-0.01)

    with pytest.raises(
        ValueError, match=r"soh_pct must be finite and within \[0, 100\]"
    ):
        battery_health_score(100.01)

    with pytest.raises(
        ValueError, match=r"soh_pct must be finite and within \[0, 100\]"
    ):
        battery_health_score(-50.0)


def test_battery_health_score_nonfinite_inputs():
    """NaN and +/- inf must raise ValueError."""
    with pytest.raises(
        ValueError, match=r"soh_pct must be finite and within \[0, 100\]"
    ):
        battery_health_score(float("nan"))

    with pytest.raises(
        ValueError, match=r"soh_pct must be finite and within \[0, 100\]"
    ):
        battery_health_score(float("inf"))

    with pytest.raises(
        ValueError, match=r"soh_pct must be finite and within \[0, 100\]"
    ):
        battery_health_score(float("-inf"))
