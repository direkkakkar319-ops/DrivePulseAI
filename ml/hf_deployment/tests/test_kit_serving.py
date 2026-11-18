"""Real KIT artifact tests for authenticated single and vectorized batch inference."""

import copy
import csv
import gzip
import hashlib
import importlib
import json
import secrets
from itertools import pairwise
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
SINGLE = "/v1/score/kit-window-pair"
BATCH = "/v1/score/kit-window-pairs"
KIT_HASH = "eba2fc21dc683ab9f4a60c625fe4c5245741f6c6f937df59244f2d504c61af0c"


@pytest.fixture(scope="module")
def serving():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT))
        yield importlib.import_module("ml.hf_deployment.app")


@pytest.fixture
def client(serving, monkeypatch):
    monkeypatch.setenv("ML_INFERENCE_API_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("KIT_MAX_BATCH_SIZE", "32")
    with TestClient(serving.app) as value:
        yield value


@pytest.fixture(scope="module")
def real_pairs():
    source = ROOT / "data/automotive_obd/kit_obd/processed/windows_10s.csv.gz"
    with gzip.open(source, "rt", newline="") as stream:
        reader = csv.DictReader(stream)
        features = [n for n in reader.fieldnames if "__" in n]
        targets = [n for n in features if n.endswith("__median")]
        rows = [
            r
            for r in reader
            if r["recording_id"] == "KIT-2018-03-20_Seat_Leon_KA_KA_Normal"
            and r["segment_id"] == "0"
        ]
    result = []
    for a, b in pairwise(rows[:4]):
        assert a["split"] == b["split"] == "test"
        assert float(b["window_start_seconds"]) - float(a["window_start_seconds"]) == 10
        result.append(
            {
                "pair_id": f"window-{a['window_start_seconds']}",
                "current_window_features": {n: float(a[n]) for n in features},
                "next_window_medians": {n: float(b[n]) for n in targets},
            }
        )
    assert rows[0]["window_start_seconds"] == "30480"
    assert rows[1]["window_start_seconds"] == "30490"
    return result


def headers(client):
    return {"X-ML-API-Key": client.app.state.inference_key}


def single_request(pair):
    return {"schema_version": 1, **{k: v for k, v in pair.items() if k != "pair_id"}}


def test_known_pair_preserves_single_response_and_matches_batch(client, real_pairs):
    original = client.post(
        SINGLE, json=single_request(real_pairs[0]), headers=headers(client)
    )
    batch = client.post(
        BATCH,
        json={"schema_version": 1, "pairs": real_pairs[:1]},
        headers=headers(client),
    )
    assert original.status_code == batch.status_code == 200
    result = original.json()
    assert result["model_version"] == "kit-xgb-forecast-v1"
    assert result["anomaly_score"] == pytest.approx(3.4350437611685285, abs=1e-9)
    assert result["threshold"] == pytest.approx(8.083880990992366)
    assert result["is_novel"] is False
    assert result["assessment_type"] == "novelty"
    assert result["label_status"] == "unlabeled_dataset_not_fault_diagnosis"
    assert set(result["normalized_signal_errors"]) == {
        name.removesuffix("__median")
        for name in client.app.state.kit_model.target_names
    }
    item = batch.json()["results"][0]
    assert item.pop("pair_id") == real_pairs[0]["pair_id"]
    assert item == result


def test_multiple_pairs_one_forecast_call_and_input_order(
    client, real_pairs, monkeypatch
):
    model = client.app.state.kit_model
    forecast = Mock(wraps=model.forecast)
    monkeypatch.setattr(model, "forecast", forecast)
    pairs = list(reversed(real_pairs))
    response = client.post(
        BATCH, json={"schema_version": 1, "pairs": pairs}, headers=headers(client)
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["pair_id"] for r in results] == [p["pair_id"] for p in pairs]
    forecast.assert_called_once()
    assert forecast.call_args.args[0].shape == (3, 30)
    features = pd.DataFrame([p["current_window_features"] for p in pairs])
    targets = pd.DataFrame([p["next_window_medians"] for p in pairs])
    expected = model.predict(features, targets)
    for item, (_, reference) in zip(results, expected.iterrows(), strict=True):
        assert item["anomaly_score"] == pytest.approx(
            reference["anomaly_score"], abs=1e-12
        )
        assert item["is_novel"] == bool(reference["is_novel"])
    for pair, item in zip(pairs, results, strict=True):
        single = client.post(SINGLE, json=single_request(pair), headers=headers(client))
        assert single.status_code == 200
        assert {k: v for k, v in item.items() if k != "pair_id"} == single.json()


def test_duplicate_ids_rejected(client, real_pairs):
    pair = real_pairs[0]
    response = client.post(
        BATCH,
        json={"schema_version": 1, "pairs": [pair, pair]},
        headers=headers(client),
    )
    assert response.status_code == 422


def test_later_invalid_pair_rejects_entire_batch(client, real_pairs, monkeypatch):
    pairs = copy.deepcopy(real_pairs[:2])
    del pairs[1]["next_window_medians"]["engine_rpm__median"]
    forecast = Mock(side_effect=AssertionError("Partial batch reached model"))
    monkeypatch.setattr(client.app.state.kit_model, "forecast", forecast)
    response = client.post(
        BATCH, json={"schema_version": 1, "pairs": pairs}, headers=headers(client)
    )
    assert response.status_code == 422
    forecast.assert_not_called()


def test_key_comparison_is_constant_time(client, real_pairs, serving, monkeypatch):
    compare = Mock(wraps=serving.hmac.compare_digest)
    monkeypatch.setattr(serving.hmac, "compare_digest", compare)
    response = client.post(
        SINGLE, json=single_request(real_pairs[0]), headers=headers(client)
    )
    assert response.status_code == 200
    compare.assert_called_once()
    assert all(isinstance(value, bytes) for value in compare.call_args.args)


def test_swagger_declares_key_security_without_exposing_key(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert client.app.state.inference_key not in response.text
    spec = response.json()
    for route in (SINGLE, BATCH):
        assert spec["paths"][route]["post"]["security"]


@pytest.mark.parametrize("bad_id", ["", "bad id", " ", "a" * 129, 17])
def test_invalid_pair_ids(client, real_pairs, bad_id):
    pair = {**real_pairs[0], "pair_id": bad_id}
    assert (
        client.post(
            BATCH, json={"schema_version": 1, "pairs": [pair]}, headers=headers(client)
        ).status_code
        == 422
    )


@pytest.mark.parametrize("field", ["current_window_features", "next_window_medians"])
@pytest.mark.parametrize("mode", ["missing", "extra", "nan", "inf", "-inf"])
@pytest.mark.parametrize("route", [SINGLE, BATCH])
def test_invalid_features_fail_without_forecasting(
    client, real_pairs, monkeypatch, field, mode, route
):
    pair = copy.deepcopy(real_pairs[0])
    name = next(iter(pair[field]))
    if mode == "missing":
        del pair[field][name]
    elif mode == "extra":
        pair[field]["not_a_model_feature"] = 0.0
    else:
        pair[field][name] = float(mode)
    body = (
        single_request(pair)
        if route == SINGLE
        else {"schema_version": 1, "pairs": [pair]}
    )
    forecast = Mock(side_effect=AssertionError("Invalid inputs reached model"))
    monkeypatch.setattr(client.app.state.kit_model, "forecast", forecast)
    response = client.post(
        route,
        content=json.dumps(body),
        headers={**headers(client), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    forecast.assert_not_called()


@pytest.mark.parametrize("count", [0, 33, 257])
def test_empty_or_oversized_batches(client, real_pairs, count, monkeypatch):
    pairs = [{**real_pairs[0], "pair_id": f"pair-{i}"} for i in range(count)]
    forecast = Mock(side_effect=AssertionError("Oversized batch reached model"))
    monkeypatch.setattr(client.app.state.kit_model, "forecast", forecast)
    assert (
        client.post(
            BATCH, json={"schema_version": 1, "pairs": pairs}, headers=headers(client)
        ).status_code
        == 422
    )
    forecast.assert_not_called()


@pytest.mark.parametrize("route", [SINGLE, BATCH, "/v1/estimate/oxford-rul"])
@pytest.mark.parametrize("supplied", [None, "invalid", ""])
def test_inference_requires_credentials(client, real_pairs, route, supplied):
    body = (
        single_request(real_pairs[0])
        if route == SINGLE
        else {"schema_version": 1, "pairs": real_pairs[:1]}
    )
    supplied_headers = {} if supplied is None else {"X-ML-API-Key": supplied}
    response = client.post(route, json=body, headers=supplied_headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid inference credentials"}
    assert client.app.state.inference_key not in response.text


@pytest.mark.parametrize("configured", [None, "", "short", " " * 40])
def test_auth_configuration_fails_closed_but_health_remains_usable(
    serving, monkeypatch, real_pairs, configured
):
    if configured is None:
        monkeypatch.delenv("ML_INFERENCE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ML_INFERENCE_API_KEY", configured)
    monkeypatch.setenv("KIT_MAX_BATCH_SIZE", "32")
    with TestClient(serving.app) as client:
        assert client.get("/health").json() == {"status": "ok", "models": "loaded"}
        for route in (SINGLE, BATCH):
            body = (
                single_request(real_pairs[0])
                if route == SINGLE
                else {"schema_version": 1, "pairs": real_pairs[:1]}
            )
            response = client.post(
                route, json=body, headers={"X-ML-API-Key": "unconfigured"}
            )
            assert response.status_code == 503
            assert response.json() == {"detail": "Inference authentication unavailable"}


def test_batch_limit_is_configurable(serving, monkeypatch, real_pairs):
    monkeypatch.setenv("ML_INFERENCE_API_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("KIT_MAX_BATCH_SIZE", "2")
    with TestClient(serving.app) as client:
        assert (
            client.post(
                BATCH,
                json={"schema_version": 1, "pairs": real_pairs[:2]},
                headers=headers(client),
            ).status_code
            == 200
        )
        assert (
            client.post(
                BATCH,
                json={"schema_version": 1, "pairs": real_pairs},
                headers=headers(client),
            ).status_code
            == 422
        )


@pytest.mark.parametrize("value", ["0", "-1", "257", "not-an-integer"])
def test_invalid_batch_configuration_fails_startup(serving, monkeypatch, value):
    monkeypatch.setenv("KIT_MAX_BATCH_SIZE", value)
    with (
        pytest.raises(RuntimeError, match="Invalid KIT_MAX_BATCH_SIZE"),
        TestClient(serving.app),
    ):
        pass


def test_nonfinite_outputs_and_inference_errors_are_safe(
    client, real_pairs, monkeypatch
):
    forecast = Mock(return_value=np.full((1, 10), np.inf))
    monkeypatch.setattr(client.app.state.kit_model, "forecast", forecast)
    response = client.post(
        SINGLE, json=single_request(real_pairs[0]), headers=headers(client)
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "KIT inference unavailable"}
    forecast.side_effect = RuntimeError("sensitive internal implementation detail")
    response = client.post(
        BATCH,
        json={"schema_version": 1, "pairs": real_pairs[:1]},
        headers=headers(client),
    )
    assert response.status_code == 503
    assert "sensitive" not in response.text


def test_artifact_unchanged():
    artifact = ROOT / "ml/hf_deployment/model_repository/kit_xgb_forecast.joblib"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == KIT_HASH
