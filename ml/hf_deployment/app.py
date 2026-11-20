"""Authenticated Nissan Leaf battery assessment API."""

from __future__ import annotations

import hmac
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field

from ml.src.models.nissan_leaf_rul import NissanLeafRUL
from ml.src.scoring.health_score import battery_health_score
from ml.src.scoring.trend_anomaly import BatteryTrendAnomalyDetector

ROOT = Path(__file__).resolve().parent
MODEL_REPOSITORY_DIR = Path(
    os.environ.get("MODEL_REPOSITORY_DIR", ROOT / "model_repository")
)
ANOMALY_ARTIFACT = MODEL_REPOSITORY_DIR / "nissan_leaf_anomaly.joblib"
ANOMALY_MODEL_VERSION = "nissan-leaf-isolation-forest-v1"
RUL_MODEL_VERSION = "nissan-leaf-soh-theilsen-v1"
HEALTH_SCORE_VERSION = "nissan-leaf-soh-bands-v1"
TREND_ANOMALY_VERSION = "nissan-leaf-rolling-zscore-v1"
MAX_ANOMALY_BATCH_SIZE = 256
MAX_RUL_HISTORY_ROWS = 10_000
inference_key_header = APIKeyHeader(name="X-ML-API-Key", auto_error=False)


def anomaly_score_for_shap(values: np.ndarray, model, feature_names: list[str]):
    """Keep sklearn feature names intact while SHAP masks input rows."""
    frame = pd.DataFrame(values, columns=feature_names)
    return model.score_samples(frame)


def require_inference_key(
    request: Request, supplied: str | None = Security(inference_key_header)
) -> None:
    configured = getattr(request.app.state, "inference_key", None)
    if configured is None:
        raise HTTPException(503, "Inference authentication unavailable")
    if supplied is None or not hmac.compare_digest(
        supplied.encode("utf-8"), configured.encode("utf-8")
    ):
        raise HTTPException(401, "Invalid inference credentials")


@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.environ.get("ML_INFERENCE_API_KEY", "")
    app.state.inference_key = (
        key if len(key.encode("utf-8")) >= 32 and key.strip() == key else None
    )
    if not ANOMALY_ARTIFACT.is_file():
        raise RuntimeError(
            f"Nissan Leaf anomaly artifact not found: {ANOMALY_ARTIFACT}"
        )
    artifact = joblib.load(ANOMALY_ARTIFACT)
    if not isinstance(artifact, dict):
        raise TypeError("Nissan Leaf anomaly artifact has an unexpected format")
    model = artifact.get("model")
    features = artifact.get("features")
    threshold = artifact.get("threshold")
    background = artifact.get("shap_background")
    if (
        not hasattr(model, "score_samples")
        or features
        != [
            "HV_Bat_Voltage",
            "Pack_1_C_Temp",
            "SOC",
            "HV_Bat_Current_2",
            "Pack_2_C_Temp",
            "Pack_4_C_Temp",
        ]
        or not isinstance(threshold, (float, int))
        or not math.isfinite(threshold)
        or artifact.get("label_status")
        != "no verified fault labels; exploratory novelty score only"
    ):
        raise RuntimeError("Incompatible Nissan Leaf anomaly artifact")
    if getattr(model, "n_features_in_", None) != len(features):
        raise RuntimeError("Nissan Leaf anomaly feature count does not match")
    background = np.asarray(background, dtype=np.float64)
    if (
        background.ndim != 2
        or background.shape[1] != len(features)
        or background.shape[0] < 2
        or not np.isfinite(background).all()
    ):
        raise RuntimeError("Nissan Leaf SHAP background data is incompatible")
    app.state.anomaly_model = model
    app.state.anomaly_features = features
    app.state.anomaly_threshold = float(threshold)
    app.state.anomaly_explainer = shap.Explainer(
        lambda values: anomaly_score_for_shap(values, model, features),
        background,
        algorithm="permutation",
        feature_names=features,
        seed=42,
    )
    app.state.rul_model = NissanLeafRUL(eol_threshold_soh_pct=80.0)
    yield


app = FastAPI(
    title="DrivePulseAI Nissan Leaf battery models",
    version="2.0.0",
    lifespan=lifespan,
)


class AnomalyObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    HV_Bat_Voltage: float = Field(gt=0, le=500, allow_inf_nan=False)
    Pack_1_C_Temp: float = Field(allow_inf_nan=False)
    SOC: float = Field(ge=0, le=100, allow_inf_nan=False)
    HV_Bat_Current_2: float = Field(allow_inf_nan=False)
    Pack_2_C_Temp: float = Field(allow_inf_nan=False)
    Pack_4_C_Temp: float = Field(allow_inf_nan=False)


class AnomalyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    observations: list[AnomalyObservation] = Field(
        min_length=1, max_length=MAX_ANOMALY_BATCH_SIZE
    )


class RULObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    Timestamp: int = Field(ge=0)
    Odometer: float = Field(ge=0, allow_inf_nan=False)
    SOH: float = Field(ge=0, le=100, allow_inf_nan=False)
    Pack_Avg_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Pack_1_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Pack_2_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Pack_4_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    HV_Bat_Current_2: float | None = Field(default=None, allow_inf_nan=False)
    SOC: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    HV_Bat_Voltage: float | None = Field(
        default=None, gt=0, le=500, allow_inf_nan=False
    )


class RULRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    eol_threshold_soh_pct: float = Field(
        default=80.0, gt=0, lt=100, allow_inf_nan=False
    )
    n_bootstrap: int = Field(default=100, ge=0, le=500)
    confidence_level_pct: float = Field(default=80.0, gt=0, lt=100, allow_inf_nan=False)
    observations: list[RULObservation] = Field(
        min_length=1, max_length=MAX_RUL_HISTORY_ROWS
    )


class TrendAnomalyObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    Timestamp: int = Field(ge=0)
    Odometer: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    SOH: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    Pack_1_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Pack_2_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Pack_4_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Pack_Avg_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    Ambient_C_Temp: float | None = Field(default=None, allow_inf_nan=False)
    HV_Bat_Voltage: float | None = Field(
        default=None, gt=0, le=500, allow_inf_nan=False
    )
    HV_Bat_Current_2: float | None = Field(default=None, allow_inf_nan=False)


class TrendAnomalyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    window_size: int = Field(default=14, ge=3, le=90)
    min_history_points: int = Field(default=7, ge=3, le=60)
    warning_z: float = Field(default=2.5, gt=0, le=10, allow_inf_nan=False)
    critical_z: float = Field(default=3.5, gt=0, le=10, allow_inf_nan=False)
    consecutive_points: int = Field(default=2, ge=1, le=10)
    observations: list[TrendAnomalyObservation] = Field(
        min_length=1, max_length=MAX_RUL_HISTORY_ROWS
    )


class HealthScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    SOH: float = Field(ge=0, le=100, allow_inf_nan=False)


@app.exception_handler(RequestValidationError)
async def invalid_request(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                for item in error.errors()
            ]
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    if not all(
        hasattr(app.state, name)
        for name in ("anomaly_model", "rul_model", "anomaly_threshold")
    ):
        raise HTTPException(503, detail="Models are not ready")
    return {"status": "ok", "models": "nissan_leaf_loaded"}


@app.post(
    "/v1/score/nissan-leaf-anomaly", dependencies=[Depends(require_inference_key)]
)
def score_nissan_leaf_anomaly(request: AnomalyRequest, http_request: Request) -> dict:
    model = http_request.app.state.anomaly_model
    names = http_request.app.state.anomaly_features
    frame = pd.DataFrame(
        [[getattr(row, name) for name in names] for row in request.observations],
        columns=names,
    )
    try:
        scores = model.score_samples(frame)
    except (ValueError, RuntimeError, ArithmeticError):
        raise HTTPException(503, "Anomaly inference unavailable") from None
    if not np.isfinite(scores).all():
        raise HTTPException(503, "Anomaly inference unavailable")
    threshold = http_request.app.state.anomaly_threshold
    anomaly_explainer = http_request.app.state.anomaly_explainer
    results = []
    for index, score in enumerate(scores):
        unusual = bool(score < threshold)
        explanation = None
        if unusual:
            try:
                shap_result = anomaly_explainer(
                    frame.iloc[[index]],
                    max_evals=2 * (len(names) + 1) * 5,
                    silent=True,
                )
                values = np.asarray(shap_result.values, dtype=float).reshape(-1)
                base_value = float(np.asarray(shap_result.base_values).reshape(-1)[0])
                if len(values) != len(names) or not np.isfinite(values).all():
                    raise ValueError("Invalid SHAP values")
                ranking = sorted(
                    range(len(names)), key=lambda item: abs(values[item]), reverse=True
                )[:3]
                explanation = {
                    "method": "shap_permutation",
                    "output": "Isolation Forest score_samples; lower means more unusual",
                    "baseline_score": base_value,
                    "contributions": [
                        {
                            "rank": rank,
                            "feature": names[feature_index],
                            "measured_value": float(
                                frame.iloc[index][names[feature_index]]
                            ),
                            "shap_value": float(values[feature_index]),
                            "direction": "toward_anomaly"
                            if values[feature_index] < 0
                            else "toward_typical",
                        }
                        for rank, feature_index in enumerate(ranking, start=1)
                    ],
                    "interpretation": "Feature contributions explain this model score; they do not establish physical cause or fault diagnosis.",
                }
            except (
                ValueError,
                RuntimeError,
                ArithmeticError,
                TypeError,
                shap.utils._exceptions.ExplainerError,
            ):
                raise HTTPException(503, "Anomaly explanation unavailable") from None
        results.append(
            {
                "anomaly_score": float(score),
                "is_unusual": unusual,
                "explanation": explanation,
            }
        )
    return {
        "schema_version": 1,
        "model_version": ANOMALY_MODEL_VERSION,
        "assessment_type": "unsupervised_novelty",
        "label_status": "unlabeled_dataset_unusual_telemetry_not_fault_diagnosis",
        "threshold": threshold,
        "explanation_status": "top_three_shap_contributions_for_unusual_rows",
        "results": results,
    }


@app.post("/v1/estimate/nissan-leaf-rul", dependencies=[Depends(require_inference_key)])
def estimate_nissan_leaf_rul(request: RULRequest, http_request: Request) -> dict:
    observations = pd.DataFrame(
        [row.model_dump(exclude_none=True) for row in request.observations]
    )
    estimator = NissanLeafRUL(
        eol_threshold_soh_pct=request.eol_threshold_soh_pct,
        n_bootstrap=request.n_bootstrap,
        confidence_level_pct=request.confidence_level_pct,
    )
    try:
        result = estimator.estimate(observations)
    except (ValueError, RuntimeError, ArithmeticError):
        raise HTTPException(422, "Invalid Nissan Leaf SOH history") from None
    return {
        "schema_version": 1,
        "model_version": RUL_MODEL_VERSION,
        "assessment_type": "experimental_soh_threshold_distance",
        "target_definition": "kilometers until reported SOH reaches configured threshold",
        **result,
        "limitations": [
            "This is not remaining driving range on the current charge.",
            "The source represents one vehicle and does not establish fleet accuracy.",
            "Threshold estimates extrapolate beyond observed data when no crossing exists.",
            "Temperature, SOC, and voltage are reported as context; they do not alter the estimated SOH trend.",
            "Bootstrap confidence intervals capture sample variance and measurement noise; they do not account for unobserved late-life knee acceleration.",
        ],
    }


@app.post(
    "/v1/score/nissan-leaf-trend-anomaly",
    dependencies=[Depends(require_inference_key)],
)
def score_nissan_leaf_trend_anomaly(request: TrendAnomalyRequest) -> dict:
    observations = pd.DataFrame(
        [row.model_dump(exclude_none=True) for row in request.observations]
    )
    detector = BatteryTrendAnomalyDetector(
        window_size=request.window_size,
        min_history_points=request.min_history_points,
        warning_z=request.warning_z,
        critical_z=request.critical_z,
        consecutive_points=request.consecutive_points,
    )
    try:
        result = detector.analyze(observations)
    except (ValueError, RuntimeError, ArithmeticError):
        raise HTTPException(422, "Invalid trend observation telemetry") from None
    return {
        "schema_version": 1,
        "model_version": TREND_ANOMALY_VERSION,
        "assessment_type": "rolling_zscore_drift_detection",
        **result,
    }


@app.post("/v1/score/nissan-leaf-health", dependencies=[Depends(require_inference_key)])
def score_nissan_leaf_health(request: HealthScoreRequest) -> dict:
    return {
        "schema_version": 1,
        "model_version": HEALTH_SCORE_VERSION,
        "assessment_type": "soh_band_score",
        **battery_health_score(request.SOH),
    }
