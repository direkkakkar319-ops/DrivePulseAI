"""Trend integration and independence; protocol fixtures are explicitly synthetic."""

import asyncio
import copy

import httpx
import pytest
from pydantic import ValidationError
from test_leaf_analysis import (
    AUTH,
    BASE,
    trend_payload,
    upload,
)
from test_leaf_analysis import (
    harness as harness,  # noqa: PLC0414 -- shared pytest fixture
)
from test_leaf_analysis import (
    settings as settings,  # noqa: PLC0414 -- shared pytest fixture
)

from app.schemas.leaf_analysis import Reading, TrendResponse
from app.services import leaf_analysis as leaf
from app.services.leaf_inference import LeafInferenceService
from app.services.leaf_trend import prepare_trend


def test_complete_history_request_and_shared_workflows(harness):
    client, calls, _ = harness
    a = client.post(BASE + f"/samples/{leaf.SAMPLE_ID}/analyze", headers=AUTH).json()
    b = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID)).json()
    assert a["trend"] == b["trend"]
    result = a["trend"]
    assert result["status"] == "completed" and result["observed_days"] == 40
    assert result["analyzed_readings"] == result["prepared_readings"] == 40
    assert result["signal_availability"]["pack_avg_temp"]["status"] == "unavailable"
    assert result["signal_availability"]["pack_temp_rise"]["status"] == "unavailable"
    requests = [body for path, body in calls if path.endswith("trend-anomaly")]
    assert (
        len(requests) == 2
    )  # one complete-history request per analysis, not point batches
    rows = requests[0]["observations"]
    assert [r["Timestamp"] for r in rows] == [r["timestamp_us"] for r in a["telemetry"]]
    assert (
        "SOC" not in rows[0]
        and "Pack_Avg_C_Temp" not in rows[0]
        and "row_id" not in rows[0]
    )


def test_unsupported_history_is_independent(harness):
    result = upload(harness[0], b"Timestamp,SOC\n1704067200000000,70\n").json()
    assert (
        result["trend"]["status"] == "unavailable" and result["trend"]["result"] is None
    )
    assert result["trend"]["analyzed_readings"] == 0
    assert result["battery"]["latest_soc"] == 70
    assert not harness[1]


def test_short_temperature_history_is_honest(harness):
    result = upload(
        harness[0], b"Timestamp,Pack_1_C_Temp,Pack_2_C_Temp\n1704067200000000,25,25\n"
    ).json()
    assert result["trend"]["status"] == "insufficient_history"
    assert result["trend"]["result"]["min_days_required"] == 8
    assert result["trend"]["result"]["days_available"] == 1
    assert result["anomaly"]["status"] == "unavailable"


def test_explicit_average_temperature_is_supported_without_invented_ambient(harness):
    data = b"Timestamp,Pack_Avg_C_Temp\n" + b"".join(
        f"{1704067200000000 + i * 86400000000},25\n".encode() for i in range(8)
    )
    response = upload(harness[0], data)
    assert response.status_code == 200
    result = response.json()
    assert result["trend"]["status"] == "completed"
    assert set(result["trend"]["result"]["signal_details"]) == {"pack_avg_temp"}
    assert (
        result["trend"]["signal_availability"]["pack_temp_rise"]["status"]
        == "unavailable"
    )


def test_partial_sensor_days_never_become_fake_zero_spread(settings):
    rows = [
        Reading(
            row_id=1,
            timestamp_us=1704067200000000,
            values={
                "Pack_1_C_Temp": 25,
                "Pack_2_C_Temp": 26,
                "SOH": 94,
                "Odometer": 20000,
            },
        ),
        Reading(
            row_id=2,
            timestamp_us=1704153600000000,
            values={
                "Pack_1_C_Temp": 25,
                "Pack_2_C_Temp": None,
                "SOH": 94,
                "Odometer": 20010,
            },
        ),
    ]
    payload, metadata = prepare_trend(rows)
    assert metadata.signal_availability["pack_temp_spread"].status == "unavailable"
    assert all(
        "Pack_1_C_Temp" not in row and "Pack_2_C_Temp" not in row for row in payload
    )
    assert payload[0]["Timestamp"] == rows[0].timestamp_us
    assert rows[0].values["Pack_1_C_Temp"] == 25  # original measurements are untouched
    assert metadata.warnings


@pytest.mark.parametrize(
    "failure",
    [
        "unauthorized",
        "missing_endpoint",
        "timeout",
        "connection",
        "invalid_json",
        "count",
        "version",
        "coverage",
        "missing_signal",
        "nonfinite",
    ],
)
def test_trend_failure_does_not_erase_other_capabilities(harness, failure):
    client, _, _ = harness

    def handler(request, body):
        assert request.url.path.endswith("trend-anomaly")
        if failure == "unauthorized":
            return httpx.Response(401, json={"detail": "private secret"})
        if failure == "missing_endpoint":
            return httpx.Response(404)
        if failure == "timeout":
            raise httpx.ReadTimeout("private", request=request)
        if failure == "connection":
            raise httpx.ConnectError("private", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, content="private invalid body")
        value = trend_payload(body["observations"])
        if failure == "count":
            value["drift_alerts_count"] = 1
        if failure == "version":
            value["model_version"] = "wrong"
        if failure == "coverage":
            value["days_evaluated"] = 100
        if failure == "missing_signal":
            value["signal_details"].pop("pack_temp_spread")
        if failure == "nonfinite":
            value["signal_details"]["pack_temp_spread"]["z_score"] = "NaN"
        return httpx.Response(200, json=value)

    # Wrap only the trend method's transport; other methods keep the shared harness.
    original_call = client.app.state.leaf_inference.call

    async def call(path, body):
        if path.endswith("trend-anomaly"):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as upstream:
                return await LeafInferenceService(
                    client.app.state.settings, upstream
                ).call(path, body)
        return await original_call(path, body)

    client.app.state.leaf_inference.call = call
    result = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID))
    assert result.status_code == 200
    value = result.json()
    assert value["trend"]["status"] == "failed" and value["trend"]["result"] is None
    assert (
        value["anomaly"]["status"] == "completed"
        and value["health"]["status"] == "completed"
    )
    assert "private" not in result.text


def test_trend_deadline_uses_existing_overall_budget(harness):
    client, _, _ = harness
    original = client.app.state.leaf_inference.trend

    async def slow(rows):
        await asyncio.sleep(1)
        return await original(rows)

    client.app.state.leaf_inference.trend = slow
    client.app.state.settings.leaf_analysis_timeout_seconds = 0.1
    result = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID))
    assert result.status_code == 504
    assert (
        "anomaly" not in result.json()
    )  # no misleading completed partial HTTP response


@pytest.mark.parametrize("severity", ["warning", "critical"])
def test_alert_schema_preserves_model_severity_instead_of_recomputing(severity):
    rows = [
        {"Timestamp": 1704067200000000 + i * 86400000000, "Pack_Avg_C_Temp": 25}
        for i in range(8)
    ]
    value = trend_payload(rows)
    detail = value["signal_details"]["pack_avg_temp"]
    detail.update(
        status=severity, current_value=27.5, z_score=3.5, consecutive_abnormal_days=2
    )
    value.update(
        is_drift_detected=True,
        drift_alerts_count=1,
        alerts=[
            {
                "signal": "pack_avg_temp",
                "label": detail["label"],
                "severity": severity,
                "z_score": detail["z_score"],
                "current_value": detail["current_value"],
                "baseline_mean": detail["baseline_mean"],
                "baseline_std": detail["baseline_std"],
                "unit": detail["unit"],
                "consecutive_days": 2,
                "explanation": "Synthetic protocol fixture",
            }
        ],
    )
    # Rounded 3.50 can be warning from an unrounded value just below the critical threshold.
    response = TrendResponse.model_validate(value)
    assert response.alerts[0].severity == severity
    bad = copy.deepcopy(value)
    bad["alerts"][0]["current_value"] = 999
    with pytest.raises(ValidationError):
        TrendResponse.model_validate(bad)
