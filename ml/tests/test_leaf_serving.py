"""Real-artifact local serving contracts; synthetic inputs are not evaluation data."""

import importlib.util
import secrets
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def serving():
    path = Path(__file__).resolve().parents[1] / "hf_deployment/app.py"
    spec = importlib.util.spec_from_file_location("leaf_serving_contract_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    key = secrets.token_urlsafe(32)
    with (
        patch.dict("os.environ", {"ML_INFERENCE_API_KEY": key}),
        TestClient(module.app) as client,
    ):
        yield module, client, {"X-ML-API-Key": key}


def test_public_health(serving):
    _, client, _ = serving
    assert client.get("/health").json() == {
        "status": "ok",
        "models": "nissan_leaf_loaded",
    }


@pytest.mark.parametrize("headers", [{}, {"X-ML-API-Key": "invalid"}])
def test_key_required(serving, headers):
    assert (
        serving[1]
        .post(
            "/v1/score/nissan-leaf-health",
            headers=headers,
            json={"schema_version": 1, "SOH": 94},
        )
        .status_code
        == 401
    )


def test_missing_configuration_fails_closed(serving):
    module, client, headers = serving
    original = module.app.state.inference_key
    try:
        module.app.state.inference_key = None
        assert (
            client.post(
                "/v1/score/nissan-leaf-health",
                headers=headers,
                json={"schema_version": 1, "SOH": 94},
            ).status_code
            == 503
        )
    finally:
        module.app.state.inference_key = original


def test_real_artifact_order_and_threshold(serving):
    module, client, headers = serving
    # Use actual saved training-background readings, not fabricated sensor values.
    import joblib

    artifact = joblib.load(module.ANOMALY_ARTIFACT)
    rows = [
        dict(zip(artifact["features"], map(float, row), strict=True))
        for row in artifact["shap_background"][:2]
    ]
    expected = module.app.state.anomaly_model.score_samples(
        __import__("pandas").DataFrame(rows, columns=artifact["features"])
    )
    response = client.post(
        "/v1/score/nissan-leaf-anomaly",
        headers=headers,
        json={"schema_version": 1, "observations": rows},
    )
    assert response.status_code == 200
    assert [r["anomaly_score"] for r in response.json()["results"]] == pytest.approx(
        expected
    )
    assert [r["is_unusual"] for r in response.json()["results"]] == [
        bool(score < artifact["threshold"]) for score in expected
    ]


def test_schema_limits_and_nonfinite(serving):
    _, client, headers = serving
    row = {
        "HV_Bat_Voltage": 360,
        "Pack_1_C_Temp": 25,
        "SOC": 70,
        "HV_Bat_Current_2": 10,
        "Pack_2_C_Temp": 25,
        "Pack_4_C_Temp": 25,
    }
    assert (
        client.post(
            "/v1/score/nissan-leaf-anomaly",
            headers=headers,
            json={"schema_version": 1, "observations": [row] * 257},
        ).status_code
        == 422
    )
    row["SOC"] = "NaN"
    response = client.post(
        "/v1/score/nissan-leaf-anomaly",
        headers=headers,
        json={"schema_version": 1, "observations": [row]},
    )
    assert response.status_code == 422 and "input" not in response.json()["detail"][0]


def test_health_and_insufficient_history(serving):
    _, client, headers = serving
    health = client.post(
        "/v1/score/nissan-leaf-health",
        headers=headers,
        json={"schema_version": 1, "SOH": 94},
    )
    assert health.status_code == 200 and health.json()["health_score"] == 4
    rul = client.post(
        "/v1/estimate/nissan-leaf-rul",
        headers=headers,
        json={
            "schema_version": 1,
            "observations": [
                {"Timestamp": 1704067200000000, "Odometer": 20000, "SOH": 94}
            ],
        },
    )
    assert (
        rul.status_code == 200
        and rul.json()["status"] == "insufficient_history"
        and rul.json()["rul_km"] is None
    )


def test_shap_failure_is_explicit_and_sanitized(serving):
    module, client, headers = serving
    original = module.app.state.anomaly_explainer

    def failure(*args, **kwargs):
        raise ValueError("private explanation failure")

    try:
        module.app.state.anomaly_explainer = failure
        row = {
            "HV_Bat_Voltage": 499,
            "Pack_1_C_Temp": 100,
            "SOC": 0,
            "HV_Bat_Current_2": 300,
            "Pack_2_C_Temp": 100,
            "Pack_4_C_Temp": 100,
        }
        response = client.post(
            "/v1/score/nissan-leaf-anomaly",
            headers=headers,
            json={"schema_version": 1, "observations": [row]},
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Anomaly explanation unavailable"}
    finally:
        module.app.state.anomaly_explainer = original
