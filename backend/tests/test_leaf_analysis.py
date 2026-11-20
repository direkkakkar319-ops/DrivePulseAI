"""Nissan integration: artificial fixtures are inputs, never claimed evaluation data."""

import asyncio
import importlib.util
import json
import secrets
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.api import deps
from app.config import Settings
from app.services import leaf_analysis as leaf
from app.services.inference_service import MLServiceError
from app.services.leaf_inference import LeafInferenceService

ROOT = Path(__file__).resolve().parents[2]
AUTH = {"Authorization": "Bearer test-only"}
BASE = "/api/v1/analysis"


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        database_url="postgresql://test:test@localhost/unused",
        ml_service_url="https://ml.test",
        ml_inference_api_key=secrets.token_urlsafe(32),
    )


def payload(rows, score=-0.5, threshold=-0.6):
    return {
        "schema_version": 1,
        "model_version": "nissan-leaf-isolation-forest-v1",
        "assessment_type": "unsupervised_novelty",
        "label_status": "unlabeled_dataset_unusual_telemetry_not_fault_diagnosis",
        "threshold": threshold,
        "explanation_status": "top_three_shap_contributions_for_unusual_rows",
        "results": [
            {
                "anomaly_score": score,
                "is_unusual": score < threshold,
                "explanation": None
                if score >= threshold
                else {
                    "method": "shap_permutation",
                    "output": "score_samples",
                    "baseline_score": -0.4,
                    "contributions": [
                        {
                            "rank": i + 1,
                            "feature": name,
                            "measured_value": row[name],
                            "shap_value": -(3 - i) * 0.1,
                            "direction": "toward_anomaly",
                        }
                        for i, name in enumerate(leaf.FEATURES[:3])
                    ],
                    "interpretation": "Model attribution, not cause",
                },
            }
            for row in rows
        ],
    }


@pytest.fixture
def harness(settings, monkeypatch):
    monkeypatch.setattr(main, "build_engine", lambda _: MagicMock())
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "test",
            "email": "test@example.test",
            "email_verified": True,
        },
    )
    calls, plan = [], {}

    def handler(request):
        assert (
            request.headers["X-ML-API-Key"]
            == settings.ml_inference_api_key.get_secret_value()
        )
        assert "Authorization" not in request.headers
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if "handler" in plan:
            return plan["handler"](request, body)
        if request.url.path.endswith("anomaly"):
            return httpx.Response(200, json=payload(body["observations"]))
        if request.url.path.endswith("health"):
            from ml.src.scoring.health_score import battery_health_score

            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "model_version": "nissan-leaf-soh-bands-v1",
                    "assessment_type": "soh_band_score",
                    **battery_health_score(body["SOH"]),
                },
            )
        # Explicit protocol mock, not a model prediction/evaluation claim.
        history = body["observations"]
        return httpx.Response(
            200,
            json={
                "schema_version": 1,
                "model_version": "nissan-leaf-soh-theilsen-v1",
                "assessment_type": "experimental_soh_threshold_distance",
                "target_definition": "kilometers until reported SOH reaches configured threshold",
                "status": "insufficient_history",
                "rul_km": None,
                "current_soh_pct": history[-1]["SOH"],
                "current_odometer_km": history[-1]["Odometer"],
                "daily_observations_used": len(history),
                "history_span_days": (
                    history[-1]["Timestamp"] - history[0]["Timestamp"]
                )
                // 86400000000,
                "eol_threshold_soh_pct": 80.0,
                "limitations": ["Protocol mock, not a prediction"],
            },
        )

    with TestClient(main.create_app(settings)) as client:
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client.app.state.leaf_inference = LeafInferenceService(settings, upstream)
        yield client, calls, plan
        client.portal.call(upstream.aclose)


def upload(client, data):
    return client.post(
        BASE + "/upload",
        headers=AUTH,
        files={"file": ("untrusted.csv", data, "text/csv")},
    )


def test_catalog_and_shared_pipeline(harness):
    client, calls, _ = harness
    catalog = client.get(BASE + "/samples", headers=AUTH)
    assert catalog.status_code == 200 and catalog.headers["cache-control"] == "no-store"
    assert catalog.json()["samples"][0]["synthetic"] is True
    result = client.post(BASE + f"/samples/{leaf.SAMPLE_ID}/analyze", headers=AUTH)
    assert result.status_code == 200
    sample = result.json()
    uploaded = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID)).json()
    for key in ("battery", "anomaly", "health", "rul", "telemetry"):
        assert sample[key] == uploaded[key]
    assert [
        len(body["observations"]) for path, body in calls if path.endswith("anomaly")
    ] == [32, 8, 32, 8]
    assert sample["battery"]["estimated_range_km"] is None
    assert sample["rul"]["status"] == "insufficient_history"
    assert sample["persisted"] is False and uploaded["source"]["synthetic"] is False


@pytest.mark.parametrize(
    "path,method",
    [
        (BASE + "/samples", "get"),
        (BASE + f"/samples/{leaf.SAMPLE_ID}/analyze", "post"),
        (BASE + "/upload", "post"),
    ],
)
def test_auth_missing(harness, path, method):
    assert getattr(harness[0], method)(path).status_code == 401


@pytest.mark.parametrize("verified,expected", [(False, 403), (True, 401)])
def test_auth_invalid(harness, monkeypatch, verified, expected):
    def verify(*_):
        if verified:
            raise HTTPException(401, "Invalid token")
        return {"uid": "test", "email": "test@example.test", "email_verified": False}

    monkeypatch.setattr(deps, "verify_token", verify)
    assert harness[0].get(BASE + "/samples", headers=AUTH).status_code == expected


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"Timestamp,SOC\n",
        b"Timestamp,SOC,SOC\n1,2,3",
        b"Timestamp,Unknown\n1704067200000000,2",
        b'Timestamp,SOC\n"broken',
        b"\xff",
        b"\x00",
    ],
)
def test_bad_csv(harness, data):
    assert upload(harness[0], data).status_code in (415, 422)


def test_partial_data_latest_timestamp_and_quality(harness):
    data = b"Timestamp,SOC,SOH\n1704153600000000,80,94\n1704067200000000,20,NaN\n1,50,90\n1704067200000000,inf,\n"
    response = upload(harness[0], data)
    assert response.status_code == 200
    result = response.json()
    assert result["battery"]["latest_soc"] == 80
    assert result["battery"]["latest_soh"] == 94
    assert (
        result["anomaly"]["status"] == "unavailable"
        and result["health"]["status"] == "completed"
    )
    assert result["rul"]["status"] == "unavailable"
    assert [r["row_id"] for r in result["telemetry"]] == [1, 2, 4]
    assert result["recording"]["missing_or_invalid_cells"] == 3
    assert result["recording"]["skipped_timestamp_rows"] == 1
    assert result["warnings"]


def test_daily_history_dense_coverage(settings):
    data = leaf.sample_bytes(leaf.SAMPLE_ID)
    rows, _ = leaf.parse_csv(data, settings)
    rows = rows + rows
    history = leaf.daily_history(rows)
    assert len(history) == 40
    assert history[0]["SOH"] == 94
    assert history[-1]["Timestamp"] - history[0]["Timestamp"] == 117 * 86400000000


@pytest.mark.parametrize("extra", ["Vehicle_ID", "RPM", "SOC [%]"])
def test_identity_and_unknown_columns(harness, extra):
    data = f"Timestamp,SOC,{extra}\n1704067200000000,50,a\n1704153600000000,51,b\n".encode()
    assert upload(harness[0], data).status_code == 422


def test_limits_and_multipart(harness, settings):
    client, _, _ = harness
    assert (
        client.post(
            BASE + "/upload",
            headers=AUTH,
            files=[("file", ("a.csv", b"a")), ("file", ("b.csv", b"b"))],
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE + "/upload",
            headers=AUTH,
            files={"file": ("a.csv", b"a")},
            data={"recording_date": "2024-01-01"},
        ).status_code
        == 422
    )
    client.app.state.settings.leaf_upload_max_bytes = 1024
    assert upload(client, b"a" * 1025).status_code == 413
    client.app.state.settings.leaf_upload_max_rows = 1
    assert (
        upload(
            client, b"Timestamp,SOC\n1704067200000000,0\n1704153600000000,0\n"
        ).status_code
        == 413
    )


@pytest.mark.parametrize("status", [401, 503, 500])
def test_upstream_errors_are_capability_failures(harness, status):
    client, _, plan = harness
    plan["handler"] = lambda *_: httpx.Response(
        status, json={"detail": "private upstream error"}
    )
    result = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID))
    assert result.status_code == 200
    assert (
        result.json()["anomaly"]["status"] == "failed"
        and result.json()["anomaly"]["results"] == []
    )
    assert "private upstream error" not in result.text


@pytest.mark.parametrize(
    "failure",
    ["timeout", "connection", "json", "missing", "direction", "later", "shap"],
)
def test_failure_no_partial_anomalies(harness, failure):
    client, calls, plan = harness

    def handler(request, body):
        if failure == "timeout":
            raise httpx.ReadTimeout("private", request=request)
        if failure == "connection":
            raise httpx.ConnectError("private", request=request)
        if failure == "json":
            return httpx.Response(200, content="not json")
        if not request.url.path.endswith("anomaly"):
            return httpx.Response(503)
        rows = body.get("observations", [])
        result = payload(rows)
        if failure == "missing":
            result["results"] = []
        if failure == "direction":
            result["results"][0]["is_unusual"] = True
        if failure == "later" and len(calls) > 1:
            return httpx.Response(503)
        if failure == "shap":
            result = payload(rows, score=-0.7)
            result["results"][0]["explanation"]["contributions"][0]["feature"] = "BAD"
        return httpx.Response(200, json=result)

    plan["handler"] = handler
    result = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID)).json()
    assert (
        result["anomaly"]["status"] == "failed" and result["anomaly"]["results"] == []
    )


def test_unknown_missing_corrupt_sample(harness, monkeypatch, tmp_path):
    client, _, _ = harness
    assert (
        client.post(BASE + "/samples/unknown/analyze", headers=AUTH).status_code == 404
    )
    monkeypatch.setattr(leaf, "SAMPLE_PATH", tmp_path / "missing.csv")
    assert (
        client.post(
            BASE + f"/samples/{leaf.SAMPLE_ID}/analyze", headers=AUTH
        ).status_code
        == 503
    )
    (tmp_path / "missing.csv").write_text("corrupt")
    (tmp_path / "missing.json").write_text('{"sha256":"bad"}')
    assert (
        client.post(
            BASE + f"/samples/{leaf.SAMPLE_ID}/analyze", headers=AUTH
        ).status_code
        == 503
    )


def test_batch_256_boundary(settings):
    async def run():
        sizes = []

        def handler(request):
            rows = json.loads(request.content)["observations"]
            sizes.append(len(rows))
            return httpx.Response(200, json=payload(rows))

        settings.leaf_ml_batch_size = 256
        rows, _ = leaf.parse_csv(leaf.sample_bytes(leaf.SAMPLE_ID), settings)
        row = {name: rows[0].values[name] for name in leaf.FEATURES}
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await LeafInferenceService(settings, client).anomaly([row] * 257)
        assert sizes == [256, 1] and len(result.results) == 257

    asyncio.run(run())


def test_missing_configuration(settings):
    async def run():
        settings.ml_service_url = None
        async with httpx.AsyncClient() as client:
            with pytest.raises(MLServiceError, match="not configured"):
                await LeafInferenceService(settings, client).health(90)

    asyncio.run(run())


def test_real_ml_sample_and_csv(settings, monkeypatch, capsys):
    """Actual model, SHAP and RUL; no production requests, Firebase stub only."""
    pytest.importorskip(
        "shap",
        reason="Optional real-model verification requires existing ML serving dependencies",
    )
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "leaf_ml_under_test", ROOT / "ml/hf_deployment/app.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setenv(
        "ML_INFERENCE_API_KEY", settings.ml_inference_api_key.get_secret_value()
    )
    monkeypatch.setattr(main, "build_engine", lambda _: MagicMock())
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "local",
            "email": "local@example.test",
            "email_verified": True,
        },
    )

    async def run():
        async with (  # noqa: SIM117 -- distinct main/ML lifespan and client ownership.
            module.app.router.lifespan_context(module.app),
            main.create_app(settings).router.lifespan_context(
                app := main.create_app(settings)
            ),
        ):
            # create_app's lifespan closure uses the same settings; no DB query is made.
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=module.app),
                base_url="https://ml.test",
            ) as upstream:
                app.state.leaf_inference = LeafInferenceService(settings, upstream)
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://backend.test",
                ) as client:
                    started = time.perf_counter()
                    sample = await client.post(
                        BASE + f"/samples/{leaf.SAMPLE_ID}/analyze", headers=AUTH
                    )
                    uploaded = await client.post(
                        BASE + "/upload",
                        headers=AUTH,
                        files={
                            "file": (
                                "synthetic.csv",
                                leaf.sample_bytes(leaf.SAMPLE_ID),
                                "text/csv",
                            )
                        },
                    )
                    assert sample.status_code == uploaded.status_code == 200, (
                        sample.text,
                        uploaded.text,
                    )
                    a, b = sample.json(), uploaded.json()
                    assert a["anomaly"]["status"] == "completed", a
                    for key in ("anomaly", "health", "rul", "battery", "telemetry"):
                        assert a[key] == b[key]
                    assert a["anomaly"]["analyzed_count"] == 40
                    assert (
                        a["health"]["status"] == "completed"
                        and a["rul"]["result"]["status"] == "ok"
                    )
                    ci = a["rul"]["result"]["confidence_interval"]
                    assert ci is not None and ci["bootstrap_iterations_valid"] >= 10
                    assert ci["rul_km_p10"] <= ci["rul_km_p50"] <= ci["rul_km_p90"]
                    assert a["rul"]["result"]["rul_km_p50"] == ci["rul_km_p50"]
                    print(
                        "REAL_INTEGRATION",
                        json.dumps(
                            {
                                "total_seconds": time.perf_counter() - started,
                                "response_bytes": len(sample.content),
                                "analyzed": 40,
                                "unusual": a["anomaly"]["unusual_count"],
                                "threshold": a["anomaly"]["threshold"],
                            }
                        ),
                    )

                # Deliberately extreme synthetic protocol inputs, not real vehicle events.
                extreme = {
                    "HV_Bat_Voltage": 499.0,
                    "Pack_1_C_Temp": 100.0,
                    "SOC": 0.0,
                    "HV_Bat_Current_2": 300.0,
                    "Pack_2_C_Temp": 100.0,
                    "Pack_4_C_Temp": 100.0,
                }
                started_shap = time.perf_counter()
                shap_response = await app.state.leaf_inference.anomaly([extreme] * 32)
                assert len(shap_response.results) == 32
                assert all(
                    p.is_unusual and p.explanation for p in shap_response.results
                )
                print(
                    "REAL_SHAP_BATCH",
                    json.dumps(
                        {
                            "observations": 32,
                            "seconds": time.perf_counter() - started_shap,
                            "score": shap_response.results[0].anomaly_score,
                            "threshold": shap_response.threshold,
                        }
                    ),
                )

    asyncio.run(run())


@pytest.mark.parametrize(
    "field,value",
    [
        ("leaf_ml_batch_size", 0),
        ("leaf_ml_batch_size", 257),
        ("leaf_ml_batch_size", True),
        ("leaf_upload_max_rows", 0),
    ],
)
def test_invalid_leaf_settings(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql://test:test@localhost/unused",
            **{field: value},
        )


def test_zero_soc_and_missing_soh_do_not_invent_health_or_range(harness):
    result = upload(harness[0], b"Timestamp,SOC\n1704067200000000,0\n").json()
    assert result["battery"]["latest_soc"] == 0
    assert result["battery"]["latest_soh"] is None
    assert result["health"]["status"] == "unavailable"
    assert result["rul"]["status"] == "unavailable"
    assert result["battery"]["estimated_range_km"] is None


def test_overall_deadline_without_silently_extending_limits(harness):
    client, _, _ = harness
    client.app.state.settings.leaf_analysis_timeout_seconds = 0.01
    original = client.app.state.leaf_inference.anomaly

    async def slow(*args):
        await asyncio.sleep(0.1)
        return await original(*args)

    client.app.state.leaf_inference.anomaly = slow
    response = upload(client, leaf.sample_bytes(leaf.SAMPLE_ID))
    assert response.status_code == 504
    assert "results" not in response.json()


def test_short_history_returns_actual_insufficient_status(harness):
    result = upload(
        harness[0], b"Timestamp,SOH,Odometer\n1704067200000000,94,20000\n"
    ).json()
    assert result["health"]["status"] == "completed"
    assert result["rul"]["status"] == "insufficient_history"
    assert result["rul"]["result"]["rul_km"] is None


@pytest.mark.parametrize(
    "variant", ["absent", "null", "valid", "unordered", "nonfinite", "inconsistent"]
)
def test_rul_optional_confidence_contract(variant):
    """Protocol fixtures, not claimed model/evaluation results."""
    from pydantic import ValidationError

    from app.schemas.leaf_analysis import RULResponse

    value = {
        "schema_version": 1,
        "model_version": "nissan-leaf-soh-theilsen-v1",
        "assessment_type": "experimental_soh_threshold_distance",
        "target_definition": "distance to SOH threshold",
        "status": "ok",
        "rul_km": 1000.0,
        "limitations": ["Protocol fixture"],
    }
    if variant == "null":
        value.update(
            confidence_interval=None, rul_km_p10=None, rul_km_p50=None, rul_km_p90=None
        )
    elif variant != "absent":
        value.update(
            rul_km_p10=800.0,
            rul_km_p50=1000.0,
            rul_km_p90=1200.0,
            confidence_interval={
                "level_pct": 80.0,
                "rul_km_p10": 800.0,
                "rul_km_p50": 1000.0,
                "rul_km_p90": 1200.0,
                "estimated_days_p10": None,
                "estimated_days_p50": None,
                "estimated_days_p90": None,
                "bootstrap_iterations_valid": 100,
            },
        )
        if variant == "unordered":
            value["confidence_interval"]["rul_km_p10"] = 1300.0
        if variant == "nonfinite":
            value["confidence_interval"]["rul_km_p50"] = float("nan")
        if variant == "inconsistent":
            value["rul_km_p10"] = 700.0
    if variant in ("unordered", "nonfinite", "inconsistent"):
        with pytest.raises(ValidationError):
            RULResponse.model_validate(value)
    else:
        result = RULResponse.model_validate(value).model_dump(exclude_unset=True)
        assert result == value
