"""HTTP serving app for DrivePulseAI's experimental KIT and Oxford models."""

from __future__ import annotations

import hmac
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ml.src.models.anomaly_detector import XGBoostForecastAnomalyDetector
from ml.src.models.rul_regressor import TheilSenCapacityTrendRUL

ROOT = Path(__file__).resolve().parent
MODEL_REPOSITORY_DIR = Path(
    os.environ.get("MODEL_REPOSITORY_DIR", ROOT / "model_repository")
)
KIT_ARTIFACT = MODEL_REPOSITORY_DIR / "kit_xgb_forecast.joblib"
OXFORD_ARTIFACT = MODEL_REPOSITORY_DIR / "oxford_rul_theilsen.joblib"
KIT_MODEL_VERSION = "kit-xgb-forecast-v1"
DEFAULT_MAX_BATCH_SIZE = 32
HARD_MAX_BATCH_SIZE = 256
inference_key_header = APIKeyHeader(name="X-ML-API-Key", auto_error=False)


def require_inference_key(
    request: Request, supplied: str | None = Security(inference_key_header)
) -> None:
    """Fail closed without exposing or logging credentials."""
    configured = getattr(request.app.state, "inference_key", None)
    if configured is None:
        raise HTTPException(503, "Inference authentication unavailable")
    if supplied is None or not hmac.compare_digest(
        supplied.encode("utf-8"), configured.encode("utf-8")
    ):
        raise HTTPException(401, "Invalid inference credentials")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load trusted model state once before accepting requests."""
    # Read configuration at process startup, never from a public request.
    key = os.environ.get("ML_INFERENCE_API_KEY", "")
    app.state.inference_key = (
        key if len(key.encode("utf-8")) >= 32 and key.strip() == key else None
    )
    try:
        maximum = int(os.environ.get("KIT_MAX_BATCH_SIZE", str(DEFAULT_MAX_BATCH_SIZE)))
        if not 1 <= maximum <= HARD_MAX_BATCH_SIZE:
            raise ValueError
    except ValueError:
        raise RuntimeError("Invalid KIT_MAX_BATCH_SIZE configuration") from None
    app.state.kit_max_batch_size = maximum
    for artifact in (KIT_ARTIFACT, OXFORD_ARTIFACT):
        if not artifact.is_file():
            raise RuntimeError(f"Model artifact was not found at {artifact}")
    kit_model = joblib.load(KIT_ARTIFACT)
    oxford_model = joblib.load(OXFORD_ARTIFACT)
    if not isinstance(kit_model, XGBoostForecastAnomalyDetector):
        raise TypeError("KIT artifact has an unexpected model type")
    if not isinstance(oxford_model, TheilSenCapacityTrendRUL):
        raise TypeError("Oxford artifact has an unexpected estimator type")
    if kit_model.threshold is None or kit_model.residual_scale is None:
        raise RuntimeError("KIT artifact must be fitted and calibrated")
    if (
        kit_model.feature_names is None
        or len(kit_model.feature_names) != 30
        or len(set(kit_model.feature_names)) != 30
        or len(kit_model.target_names) != 10
        or len(set(kit_model.target_names)) != 10
        or np.shape(kit_model.residual_scale) != (10,)
        or not np.isfinite(kit_model.residual_scale).all()
        or not (kit_model.residual_scale > 0).all()
        or not math.isfinite(kit_model.threshold)
        or kit_model.score_aggregation != "max"
    ):
        raise RuntimeError("Incompatible KIT model configuration")
    app.state.kit_model = kit_model
    app.state.oxford_model = oxford_model
    yield


app = FastAPI(
    title="DrivePulseAI research model API",
    version="1.0.0",
    lifespan=lifespan,
)


class KitWindowValues(BaseModel):
    """Finite prepared values shared by single and batch KIT requests."""

    model_config = ConfigDict(extra="forbid")

    current_window_features: dict[str, float]
    next_window_medians: dict[str, float]

    @field_validator("current_window_features", "next_window_medians")
    @classmethod
    def finite_values(cls, values: dict[str, float]) -> dict[str, float]:
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("feature values must be finite numbers")
        return values


class KitWindowPairRequest(KitWindowValues):
    """Original single-pair request; its fields and numerical behavior are retained."""

    schema_version: int = Field(ge=1, le=1)


class KitBatchPair(KitWindowValues):
    pair_id: str = Field(
        strict=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )


class KitWindowPairsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    pairs: list[KitBatchPair] = Field(min_length=1, max_length=HARD_MAX_BATCH_SIZE)

    @field_validator("pairs")
    @classmethod
    def unique_ids(cls, pairs: list[KitBatchPair]) -> list[KitBatchPair]:
        ids = [pair.pair_id for pair in pairs]
        if len(ids) != len(set(ids)):
            raise ValueError("pair IDs must be unique")
        return pairs


class OxfordObservation(BaseModel):
    """Capacity measurement from one Oxford characterization cycle."""

    model_config = ConfigDict(extra="forbid")

    characterization_cycle: int = Field(ge=0)
    capacity_1c_discharge_mah: float = Field(gt=0, allow_inf_nan=False)


class OxfordRULRequest(BaseModel):
    """Past capacity history and the caller's explicit EOL threshold."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    as_of_cycle: int = Field(ge=0)
    eol_threshold_capacity_mah: float = Field(gt=0, allow_inf_nan=False)
    observations: list[OxfordObservation] = Field(min_length=4)


@app.get("/health")
def health() -> dict[str, str]:
    """Report endpoint and model readiness without exposing secrets."""
    ready = hasattr(app.state, "kit_model") and hasattr(app.state, "oxford_model")
    if not ready:
        raise HTTPException(status_code=503, detail="Models are not ready")
    return {"status": "ok", "models": "loaded"}


@app.exception_handler(RequestValidationError)
async def invalid_request(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    # Avoid echoing raw request values; NaN/Infinity must also produce valid JSON.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ]
        },
    )


def score_kit_pairs(
    model: XGBoostForecastAnomalyDetector, pairs: list[KitWindowValues]
) -> list[dict]:
    """Validate the whole request, then make one forecast call for all rows."""
    if model.feature_names is None:
        raise HTTPException(503, "KIT inference unavailable")
    for pair in pairs:
        if set(pair.current_window_features) != set(model.feature_names):
            raise HTTPException(
                422, "current_window_features must match all fitted feature names"
            )
        if set(pair.next_window_medians) != set(model.target_names):
            raise HTTPException(
                422, "next_window_medians must match all fitted target names"
            )
    features = pd.DataFrame(
        [
            [pair.current_window_features[name] for name in model.feature_names]
            for pair in pairs
        ],
        columns=model.feature_names,
    )
    targets = np.asarray(
        [
            [pair.next_window_medians[name] for name in model.target_names]
            for pair in pairs
        ]
    )
    try:
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            forecast = model.forecast(features)
            if forecast.shape != targets.shape:
                raise ValueError("Unexpected forecast dimensions")
            normalized = np.abs((targets - forecast) / model.residual_scale)
            scores = np.max(normalized, axis=1)
        if not np.isfinite(normalized).all() or not np.isfinite(scores).all():
            raise ValueError("Non-finite inference output")
    except (ValueError, RuntimeError, ArithmeticError):
        raise HTTPException(503, "KIT inference unavailable") from None
    return [
        {
            "schema_version": 1,
            "model_version": KIT_MODEL_VERSION,
            "assessment_type": "novelty",
            "anomaly_score": float(score),
            "threshold": float(model.threshold),
            "is_novel": bool(score > model.threshold),
            "normalized_signal_errors": {
                name.removesuffix("__median"): float(value)
                for name, value in zip(model.target_names, errors, strict=True)
            },
            "label_status": "unlabeled_dataset_not_fault_diagnosis",
        }
        for score, errors in zip(scores, normalized, strict=True)
    ]


@app.post("/v1/score/kit-window-pair", dependencies=[Depends(require_inference_key)])
def score_kit_window_pair(request: KitWindowPairRequest, http_request: Request) -> dict:
    """Original single-pair response, now requiring server-to-server authentication."""
    return score_kit_pairs(http_request.app.state.kit_model, [request])[0]


@app.post("/v1/score/kit-window-pairs", dependencies=[Depends(require_inference_key)])
def score_kit_window_pairs(
    request: KitWindowPairsRequest, http_request: Request
) -> dict:
    """Score a bounded batch atomically, preserving input order and caller pair IDs."""
    if len(request.pairs) > http_request.app.state.kit_max_batch_size:
        raise HTTPException(422, "Batch exceeds configured maximum size")
    model = http_request.app.state.kit_model
    results = score_kit_pairs(model, request.pairs)
    return {
        "schema_version": 1,
        "model_version": KIT_MODEL_VERSION,
        "assessment_type": "novelty",
        "threshold": float(model.threshold),
        "label_status": "unlabeled_dataset_not_fault_diagnosis",
        "results": [
            {"pair_id": pair.pair_id, **result}
            for pair, result in zip(request.pairs, results, strict=True)
        ],
    }


@app.post("/v1/estimate/oxford-rul", dependencies=[Depends(require_inference_key)])
def estimate_oxford_rul(request: OxfordRULRequest) -> dict:
    """Estimate proxy RUL from Oxford capacity history using Theil-Sen trend."""
    observations = pd.DataFrame(
        [
            {
                "characterization_cycle": row.characterization_cycle,
                "capacity_1c_discharge_mah": row.capacity_1c_discharge_mah,
                "eol_threshold_capacity_mah": request.eol_threshold_capacity_mah,
            }
            for row in request.observations
        ]
    )
    result = app.state.oxford_model.estimate(observations, request.as_of_cycle)
    return {
        "schema_version": 1,
        "model_version": "oxford-theilsen-proxy-v1",
        "assessment_type": "experimental_proxy_rul",
        "target_definition": "caller_supplied_capacity_threshold",
        "status": result["status"],
        "rul_cycles": result.get("rul_cycles"),
        "details": result,
        "limitations": [
            "Oxford target is an unconfirmed first-crossing proxy.",
            "Only two cells cross the 75% threshold in this dataset.",
            "This estimate is experimental and not validated for unseen cells.",
        ],
    }
