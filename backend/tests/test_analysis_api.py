"""Authenticated API + real sample/client + genuine recorded ML fixture responses."""

import copy
import importlib
import json
import resource
import secrets
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import deps
from app.config import Settings
from app.main import create_app
from app.schemas.analysis import PairAnalysis
from app.services import analysis_service
from app.services.inference_service import KITInferenceService
from app.services.kit_samples import MANIFEST_PATH, load_sample

BASE = "/api/v1/analysis/samples"
ANALYZE = BASE + "/kit-20180320-normal/analyze"
AUTH = {"Authorization": "Bearer verified-fixture"}
FIXTURE = Path(__file__).parent / "fixtures/kit_sample_ml_results.json"


@pytest.fixture(scope="module")
def genuine():
    return json.loads(FIXTURE.read_text())


def claims(token, _project):
    if token != "verified-fixture":
        raise HTTPException(401, "Invalid or expired authentication token")
    return {
        "uid": "test-account",
        "email": "driver@example.test",
        "email_verified": True,
    }


@pytest.fixture
def harness(genuine, monkeypatch):
    monkeypatch.setattr(deps, "verify_token", claims)
    key = secrets.token_urlsafe(32)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unit:unit@localhost/unused",
        ml_service_url="https://ml.example.test",
        ml_inference_api_key=key,
    )
    requests = []
    plan = {}
    originals = {item["pair_id"]: item for item in genuine["response"]["results"]}

    async def handler(request):
        assert request.headers["X-ML-API-Key"] == key
        assert "Authorization" not in request.headers
        payload = json.loads(request.content)
        requests.append(payload)
        if "handler" in plan:
            return plan["handler"](request, payload, len(requests))
        response = {
            **genuine["response"],
            "results": [originals[p["pair_id"]] for p in payload["pairs"]],
        }
        return httpx.Response(200, json=response)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with TestClient(create_app(settings)) as client:
        client.app.state.kit_inference = KITInferenceService(settings, upstream)
        yield SimpleNamespace(client=client, plan=plan, requests=requests, key=key)
        client.portal.call(upstream.aclose)


def test_catalog_is_manifest_backed_and_public_metadata_only(harness):
    response = harness.client.get(BASE, headers=AUTH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    item = response.json()["samples"][0]
    assert item["id"] == "kit-20180320-normal"
    assert item["recording_id"] == "KIT-2018-03-20_Seat_Leon_KA_KA_Normal"
    assert item["window_count"] == 163 and item["valid_pair_count"] == 162
    assert item["window_seconds"] == 10
    assert item["license"] == "CC-BY-4.0" and item["source_doi"] == "10.35097/1130"
    assert item["compatible_model_version"] == "kit-xgb-forecast-v1"
    assert "asset_file" not in response.text and "asset_sha256" not in response.text
    assert "backend/" not in response.text and harness.key not in response.text
    assert harness.requests == []


def check_complete_result(data, genuine):
    results = genuine["response"]["results"]
    assert data["window_count"] == 163 and data["pair_count"] == 162
    assert len(data["predictions"]) == len(data["score_series"]) == 162
    assert len(data["telemetry"]) == 163
    assert [p["pair_id"] for p in data["predictions"]] == [
        r["pair_id"] for r in results
    ]
    summary = data["summary"]
    assert summary["evaluated_pairs"] == 162
    assert summary["novel_pairs"] == 2 and summary["not_novel_pairs"] == 160
    assert summary["novel_percentage"] == pytest.approx(2 / 162 * 100)
    assert summary["max_anomaly_score"] == pytest.approx(11.339888612364291)
    assert summary["mean_anomaly_score"] == pytest.approx(1.7949504247994472)
    assert summary["threshold"] == pytest.approx(8.083880990992366)
    sample = load_sample("kit-20180320-normal")
    for index, (prediction, graph, reference) in enumerate(
        zip(data["predictions"], data["score_series"], results, strict=True)
    ):
        pair = sample.pairs[index]
        assert prediction["anomaly_score"] == pytest.approx(
            reference["anomaly_score"], abs=1e-9
        )
        assert prediction["is_novel"] == reference["is_novel"]
        assert (
            prediction["current_window"]["start_seconds"] == pair.current.start_seconds
        )
        assert (
            prediction["next_window"]["start_seconds"] == pair.following.start_seconds
        )
        assert (
            prediction["next_window"]["end_seconds"]
            == pair.following.start_seconds + 10
        )
        assert prediction["next_window"]["id"] == f"window-{index + 1:06d}"
        assert graph["window"] == prediction["next_window"]
        assert graph["anomaly_score"] == prediction["anomaly_score"]
        assert graph["is_novel"] == prediction["is_novel"]
        assert graph["threshold"] == summary["threshold"]
        assert prediction["top_signal_deviations"][0]["normalized_error"] == max(
            prediction["normalized_signal_errors"].values()
        )
    assert data["predictions"][0]["next_window"]["relative_start_seconds"] == 10
    assert data["predictions"][0]["anomaly_score"] == pytest.approx(
        3.435043761, abs=1e-6
    )
    assert data["telemetry"][0]["medians"]["coolant_temp_c"] == 3.0
    assert [
        (i["start_seconds"], i["end_seconds"]) for i in data["flagged_intervals"]
    ] == [(31660, 31670), (31770, 31780)]
    assert data["persisted"] is False


def test_full_authenticated_api_pipeline(harness, genuine):
    response = harness.client.post(ANALYZE, headers=AUTH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    check_complete_result(response.json(), genuine)
    assert [len(r["pairs"]) for r in harness.requests] == [32, 32, 32, 32, 32, 2]
    assert harness.key not in response.text
    assert "backend/" not in response.text


@pytest.mark.parametrize("method,path", [("get", BASE), ("post", ANALYZE)])
@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Basic invalid"}, {"Authorization": "Bearer invalid"}],
)
def test_missing_and_invalid_auth_never_reaches_ml(harness, method, path, headers):
    response = getattr(harness.client, method)(path, headers=headers)
    assert response.status_code == 401
    assert harness.requests == []


def test_unverified_auth_rejected(harness, monkeypatch):
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {
            "uid": "test",
            "email": "test@example.test",
            "email_verified": False,
        },
    )
    assert harness.client.post(ANALYZE, headers=AUTH).status_code == 403
    assert harness.requests == []


@pytest.mark.parametrize(
    "sample_id,status",
    [
        ("unknown", 404),
        ("bad.name", 422),
        ("bad%20id", 422),
        ("a" * 65, 422),
        ("..%2Fetc%2Fpasswd", 404),
    ],
)
def test_unknown_or_malicious_ids(harness, sample_id, status):
    response = harness.client.post(f"{BASE}/{sample_id}/analyze", headers=AUTH)
    assert response.status_code == status
    assert harness.requests == []


@pytest.mark.parametrize(
    "mode", ["missing", "corrupt", "checksum", "metadata", "model", "manifest"]
)
@pytest.mark.parametrize("method", ["get", "post"])
def test_broken_package_rejected_safely(harness, tmp_path, monkeypatch, mode, method):
    folder = tmp_path / "kit"
    shutil.copytree(MANIFEST_PATH.parent, folder)
    manifest = folder / "manifest.json"
    asset = folder / "kit-20180320-normal.csv.gz"
    if mode == "missing":
        asset.unlink()
    elif mode == "corrupt":
        asset.write_bytes(b"not gzip")
    elif mode == "manifest":
        manifest.write_text("not json")
    else:
        data = json.loads(manifest.read_text())
        entry = data["samples"][0]
        if mode == "checksum":
            entry["asset_sha256"] = "0" * 64
        elif mode == "metadata":
            entry["creator"] = None
        elif mode == "model":
            entry["compatible_model_version"] = "unsupported-model"
        manifest.write_text(json.dumps(data))
    monkeypatch.setattr(analysis_service, "MANIFEST_PATH", manifest)
    response = getattr(harness.client, method)(
        BASE if method == "get" else ANALYZE, headers=AUTH
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Sample data unavailable"}
    assert str(tmp_path) not in response.text
    assert harness.requests == []


@pytest.mark.parametrize(
    "mode,status",
    [
        ("first", 503),
        ("later", 503),
        ("auth", 503),
        ("timeout", 504),
        ("connection", 503),
        ("json", 502),
        ("missing", 502),
        ("duplicate", 502),
        ("unexpected", 502),
        ("count", 502),
        ("schema", 502),
        ("reordered", 502),
        ("old-service", 502),
    ],
)
def test_ml_failures_never_report_partial_success(harness, genuine, mode, status):
    def handler(request, payload, number):
        if mode == "later" and number == 1:
            return httpx.Response(
                200,
                json={
                    **genuine["response"],
                    "results": genuine["response"]["results"][:32],
                },
            )
        if mode in {"first", "later"}:
            return httpx.Response(503, text="private upstream error")
        if mode == "auth":
            return httpx.Response(401, text=harness.key)
        if mode == "old-service":
            return httpx.Response(404)
        if mode == "timeout":
            raise httpx.ReadTimeout("private details", request=request)
        if mode == "connection":
            raise httpx.ConnectError("private details", request=request)
        if mode == "json":
            return httpx.Response(200, text="not json")
        data = copy.deepcopy(genuine["response"])
        data["results"] = data["results"][: len(payload["pairs"])]
        if mode == "missing":
            data["results"].pop()
        elif mode == "duplicate":
            data["results"][1]["pair_id"] = data["results"][0]["pair_id"]
        elif mode == "unexpected":
            data["results"][0]["pair_id"] = "unknown"
        elif mode == "count":
            data["results"].append(data["results"][0])
        elif mode == "schema":
            data = {"invalid": True}
        elif mode == "reordered":
            data["results"].reverse()
        return httpx.Response(200, json=data)

    harness.plan["handler"] = handler
    response = harness.client.post(ANALYZE, headers=AUTH)
    assert response.status_code == status
    assert set(response.json()) == {"detail"}
    assert harness.key not in response.text and "private" not in response.text
    assert len(harness.requests) == (2 if mode == "later" else 1)


def test_missing_ml_configuration(harness):
    service = harness.client.app.state.kit_inference
    service._settings.ml_service_url = None
    response = harness.client.post(ANALYZE, headers=AUTH)
    assert response.status_code == 503 and harness.requests == []


def test_unexpected_processing_error_is_safe(harness, monkeypatch):
    def failed(*_):
        raise RuntimeError("private/path secret internals")

    monkeypatch.setattr(analysis_service, "build_analysis", failed)
    response = harness.client.post(ANALYZE, headers=AUTH)
    assert response.status_code == 500
    assert response.json() == {"detail": "Sample analysis failed"}


@pytest.mark.parametrize(
    "boundary", ["none", "adjacent", "gap", "recording", "date", "segment", "split"]
)
def test_interval_grouping_with_genuine_flagged_predictions(harness, boundary):
    # Reuse two genuine above-threshold outputs. Only metadata is varied to
    # exercise grouping boundaries; no synthetic model prediction is asserted.
    data = harness.client.post(ANALYZE, headers=AUTH).json()
    flagged = [
        PairAnalysis.model_validate(p) for p in data["predictions"] if p["is_novel"]
    ]
    if boundary == "none":
        assert (
            analysis_service.merge_flagged_intervals(
                [PairAnalysis.model_validate(data["predictions"][0])]
            )
            == []
        )
        return
    a, b = flagged
    if boundary != "gap":
        b.next_window.start_seconds = a.next_window.end_seconds
        b.next_window.end_seconds = b.next_window.start_seconds + 10
    if boundary == "recording":
        b.next_window.recording_id = "other-recording"
    elif boundary == "date":
        b.next_window.recording_date = "2018-03-21"
    elif boundary == "segment":
        b.next_window.segment_id = 1
    elif boundary == "split":
        b.next_window.split = "validation"
    intervals = analysis_service.merge_flagged_intervals([a, b])
    assert len(intervals) == (1 if boundary == "adjacent" else 2)
    assert sum(len(i.pair_ids) for i in intervals) == 2


@pytest.mark.asyncio
async def test_real_full_sample_both_apps_and_existing_client(genuine, monkeypatch):
    for package in ("joblib", "numpy", "pandas", "sklearn", "xgboost"):
        pytest.importorskip(package)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    serving = importlib.import_module("ml.hf_deployment.app")
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("ML_INFERENCE_API_KEY", key)
    monkeypatch.setenv("KIT_MAX_BATCH_SIZE", "32")
    monkeypatch.setattr(deps, "verify_token", claims)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unit:unit@localhost/unused",
        ml_service_url="https://local-ml.example.test",
        ml_inference_api_key=key,
    )
    main = create_app(settings)
    times = []
    batches = []
    transport = httpx.ASGITransport(app=serving.app)

    async def forward(request):
        start = time.perf_counter()
        batches.append(len(json.loads(request.content)["pairs"]))
        response = await transport.handle_async_request(request)
        times.append((time.perf_counter() - start) * 1000)
        return response

    start = time.perf_counter()
    load_sample("kit-20180320-normal")
    load_ms = (time.perf_counter() - start) * 1000
    async with (
        serving.lifespan(serving.app),
        main.router.lifespan_context(main),
        httpx.AsyncClient(transport=httpx.MockTransport(forward)) as upstream,
    ):
        main.state.kit_inference = KITInferenceService(settings, upstream)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main),
            base_url="https://main.example.test",
        ) as client:
            start = time.perf_counter()
            response = await client.post(ANALYZE, headers=AUTH)
            total_ms = (time.perf_counter() - start) * 1000
    assert response.status_code == 200
    check_complete_result(response.json(), genuine)
    assert batches == [32, 32, 32, 32, 32, 2]
    assert key not in response.text
    print(
        {
            "sample_load_ms": round(load_ms, 3),
            "six_ml_calls_ms": [round(t, 3) for t in times],
            "main_request_ms": round(total_ms, 3),
            "response_bytes": len(response.content),
            "process_peak_rss_mib": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
            ),
        }
    )
