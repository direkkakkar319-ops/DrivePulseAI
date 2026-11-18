"""Mocked HTTP protocol tests plus optional local ASGI/model integration."""

import asyncio
import json
import secrets
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services.inference_service import (
    KITInferenceService,
    MLServiceError,
    bounded_batches,
)
from app.services.kit_samples import SIGNALS, load_sample

pytestmark = pytest.mark.asyncio


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        database_url="postgresql://test:test@localhost/unused",
        ml_service_url="https://ml.example.test/",
        ml_inference_api_key=secrets.token_urlsafe(32),
    )


@pytest.fixture(scope="module")
def sample():
    return load_sample("kit-20180320-normal")


def mock_response(payload):
    """Protocol double, not computed predictions for the recording.

    Reuse the previously observed first-pair response solely to test transport,
    ordering and rejection. The optional integration test uses real inference.
    """
    errors = dict.fromkeys(SIGNALS, 0.0)
    errors.update(
        coolant_temp_c=1.4148030227234043,
        engine_rpm=3.4350437611685285,
        speed_kmph=0.19998863630410724,
        maf_gs=0.9324217461072069,
        pedal_d_pct=3.306972062409628e-8,
    )
    metadata = {
        "schema_version": 1,
        "model_version": "kit-xgb-forecast-v1",
        "assessment_type": "novelty",
        "threshold": 8.083880990992366,
        "label_status": "unlabeled_dataset_not_fault_diagnosis",
    }
    return {
        **metadata,
        "results": [
            {
                **metadata,
                "pair_id": pair["pair_id"],
                "anomaly_score": 3.4350437611685285,
                "is_novel": False,
                "normalized_signal_errors": errors.copy(),
            }
            for pair in payload["pairs"]
        ],
    }


async def test_exact_url_header_and_known_request(settings, sample):
    def handler(request):
        assert str(request.url) == "https://ml.example.test/v1/score/kit-window-pairs"
        assert request.method == "POST"
        assert (
            request.headers["X-ML-API-Key"]
            == settings.ml_inference_api_key.get_secret_value()
        )
        assert "Authorization" not in request.headers
        payload = json.loads(request.content)
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/kit_known_request.json").read_text()
        )
        expected = {k: v for k, v in fixture.items() if k != "schema_version"}
        assert payload == {
            "schema_version": 1,
            "pairs": [{"pair_id": "known-30480", **expected}],
        }
        return httpx.Response(200, json=mock_response(payload))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await KITInferenceService(settings, client).score_pairs(
            sample.pairs[:1], pair_ids=["known-30480"]
        )
    assert result.results[0].pair_id == "known-30480"
    assert result.results[0].anomaly_score == pytest.approx(3.435043761)


async def test_162_pairs_sequential_six_batches_and_order(settings, sample):
    batches = []
    active = 0

    async def handler(request):
        nonlocal active
        active += 1
        assert active == 1
        await asyncio.sleep(0)
        payload = json.loads(request.content)
        batches.append(payload["pairs"])
        active -= 1
        return httpx.Response(200, json=mock_response(payload))

    ids = [f"sample-{i}" for i in range(162)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await KITInferenceService(settings, client).score_pairs(
            sample.pairs, pair_ids=ids
        )
    assert [len(batch) for batch in batches] == [32, 32, 32, 32, 32, 2]
    assert [r.pair_id for r in result.results] == ids
    assert [p["pair_id"] for batch in batches for p in batch] == ids


@pytest.mark.parametrize(
    "mode",
    [
        "empty",
        "ids-length",
        "duplicate-ids",
        "bad-id",
        "late-feature",
        "segment",
        "gap",
    ],
)
async def test_full_input_validated_before_any_request(settings, sample, mode):
    pairs = list(sample.pairs)
    ids = [f"p-{i}" for i in range(len(pairs))]
    if mode == "empty":
        pairs = []
        ids = []
    elif mode == "ids-length":
        ids.pop()
    elif mode == "duplicate-ids":
        ids[-1] = ids[0]
    elif mode == "bad-id":
        ids[-1] = "invalid id"
    elif mode == "late-feature":
        invalid = replace(
            pairs[-1].current,
            features={**pairs[-1].current.features, "engine_rpm__median": float("nan")},
        )
        pairs[-1] = replace(pairs[-1], current=invalid)
    elif mode == "segment":
        pairs[-1] = replace(
            pairs[-1], following=replace(pairs[-1].following, segment_id=1)
        )
    elif mode == "gap":
        pairs[-1] = replace(
            pairs[-1],
            following=replace(
                pairs[-1].following,
                start_seconds=pairs[-1].following.start_seconds + 10,
            ),
        )

    def handler(_):
        pytest.fail("Invalid input reached HTTP")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MLServiceError) as error:
            await KITInferenceService(settings, client).score_pairs(pairs, pair_ids=ids)
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("ml_service_url", None),
        ("ml_inference_api_key", None),
        ("ml_inference_api_key", "short"),
    ],
)
async def test_missing_configuration(settings, sample, field, value):
    values = settings.model_dump()
    values[field] = value
    configured = Settings(_env_file=None, **values)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("Unconfigured HTTP"))
    ) as client:
        with pytest.raises(MLServiceError, match="not configured") as error:
            await KITInferenceService(configured, client).score_pairs(sample.pairs[:1])
    assert error.value.status_code == 503


@pytest.mark.parametrize("size", [0, -1, 257, True, 1.5])
async def test_invalid_batch_helper(size):
    with pytest.raises(MLServiceError):
        bounded_batches([1, 2], size)


@pytest.mark.parametrize(
    "status,expected",
    [(401, 503), (503, 503), (404, 502), (422, 502), (500, 502), (302, 502)],
)
async def test_upstream_status_is_safe_and_not_retried(
    settings, sample, status, expected
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="sensitive upstream information",
            headers={"Location": "https://untrusted.example"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(MLServiceError) as error:
            await KITInferenceService(settings, client).score_pairs(sample.pairs[:1])
    assert error.value.status_code == expected
    assert "sensitive" not in str(error.value)
    assert settings.ml_inference_api_key.get_secret_value() not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "exception,expected",
    [
        (httpx.ConnectError, 503),
        (httpx.ReadTimeout, 504),
        (httpx.ConnectTimeout, 504),
        (httpx.RemoteProtocolError, 503),
    ],
)
async def test_network_errors(settings, sample, exception, expected):
    def handler(request):
        raise exception("private request details", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MLServiceError) as error:
            await KITInferenceService(settings, client).score_pairs(sample.pairs[:1])
    assert error.value.status_code == expected
    assert "private" not in str(error.value)


async def test_total_per_batch_deadline(settings, sample):
    configured = Settings(
        _env_file=None, **{**settings.model_dump(), "ml_request_timeout_seconds": 0.01}
    )

    async def handler(_):
        await asyncio.sleep(1)
        pytest.fail("Deadline did not cancel")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MLServiceError, match="timed out"):
            await KITInferenceService(configured, client).score_pairs(sample.pairs[:1])


@pytest.mark.parametrize(
    "mode",
    [
        "json",
        "schema",
        "missing",
        "duplicate",
        "unexpected",
        "reordered",
        "version",
        "threshold",
        "nonfinite",
        "signals",
        "flag",
        "score",
        "partial",
        "too-large",
    ],
)
async def test_invalid_upstream_response(settings, sample, mode):
    def handler(request):
        if mode == "json":
            return httpx.Response(200, text="not json")
        if mode == "too-large":
            return httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))
        data = mock_response(json.loads(request.content))
        if mode == "schema":
            data = {"unexpected": True}
        elif mode in {"missing", "partial"}:
            data["results"].pop()
        elif mode == "duplicate":
            data["results"][1]["pair_id"] = data["results"][0]["pair_id"]
        elif mode == "unexpected":
            data["results"][0]["pair_id"] = "unknown"
        elif mode == "reordered":
            data["results"].reverse()
        elif mode == "version":
            data["model_version"] = "different-model"
        elif mode == "threshold":
            data["results"][0]["threshold"] += 1
        elif mode == "nonfinite":
            data["results"][0]["anomaly_score"] = "NaN"
        elif mode == "signals":
            del data["results"][0]["normalized_signal_errors"]["engine_rpm"]
        elif mode == "flag":
            data["results"][0]["is_novel"] = True
        elif mode == "score":
            data["results"][0]["anomaly_score"] += 1
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MLServiceError) as error:
            await KITInferenceService(settings, client).score_pairs(sample.pairs[:2])
    assert error.value.status_code == 502


@pytest.mark.parametrize("failure", ["http", "metadata"])
async def test_later_batch_failure_never_returns_partial_success(
    settings, sample, failure
):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        data = mock_response(json.loads(request.content))
        if calls == 2:
            if failure == "http":
                return httpx.Response(503)
            data["threshold"] += 1
            for item in data["results"]:
                item["threshold"] = data["threshold"]
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MLServiceError):
            await KITInferenceService(settings, client).score_pairs(sample.pairs)
    assert calls == 2


async def test_unrelated_health_without_ml_settings_and_client_cleanup():
    pytest.importorskip("firebase_admin")
    from app.main import create_app

    settings = Settings(
        _env_file=None,
        database_url="postgresql://test:test@localhost/unused",
        ml_service_url=None,
        ml_inference_api_key=None,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        service = client.app.state.kit_inference
        assert not service._client.is_closed
    assert service._client.is_closed
