"""HTTP serving app for DrivePulseAI's experimental KIT and Oxford models."""

from __future__ import annotations

import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ml.src.models.anomaly_detector import XGBoostForecastAnomalyDetector
from ml.src.models.rul_regressor import TheilSenCapacityTrendRUL

ROOT = Path(__file__).resolve().parent
MODEL_REPOSITORY_DIR = Path(os.environ.get("MODEL_REPOSITORY_DIR", ROOT / "model_repository"))
KIT_ARTIFACT = MODEL_REPOSITORY_DIR / "kit_xgb_forecast.joblib"
OXFORD_ARTIFACT = MODEL_REPOSITORY_DIR / "oxford_rul_theilsen.joblib"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load trusted model state once before accepting requests."""
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
    app.state.kit_model = kit_model
    app.state.oxford_model = oxford_model
    yield


app = FastAPI(
    title="DrivePulseAI research model API",
    version="1.0.0",
    lifespan=lifespan,
)


class KitWindowPairRequest(BaseModel):
    """Pair a KIT feature window with the following window's actual targets."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    current_window_features: dict[str, float]
    next_window_medians: dict[str, float]

    @field_validator("current_window_features", "next_window_medians")
    @classmethod
    def finite_values(cls, values: dict[str, float]) -> dict[str, float]:
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("feature values must be finite numbers")
        return values


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


@app.post("/v1/score/kit-window-pair")
def score_kit_window_pair(request: KitWindowPairRequest) -> dict:
    """Return a calibrated novelty score for one consecutive KIT window pair."""
    model: XGBoostForecastAnomalyDetector = app.state.kit_model
    assert model.feature_names is not None
    if set(request.current_window_features) != set(model.feature_names):
        raise HTTPException(
            status_code=422,
            detail="current_window_features must match all fitted feature names",
        )
    if set(request.next_window_medians) != set(model.target_names):
        raise HTTPException(
            status_code=422,
            detail="next_window_medians must match all fitted target names",
        )

    features = pd.DataFrame(
        [[request.current_window_features[name] for name in model.feature_names]],
        columns=model.feature_names,
    )
    targets = pd.DataFrame(
        [[request.next_window_medians[name] for name in model.target_names]],
        columns=model.target_names,
    )
    forecast = model.forecast(features)[0]
    residuals = targets.to_numpy()[0] - forecast
    normalized = np.abs(residuals / model.residual_scale)
    score = float(np.max(normalized))
    return {
        "schema_version": 1,
        "model_version": "kit-xgb-forecast-v1",
        "assessment_type": "novelty",
        "anomaly_score": score,
        "threshold": float(model.threshold),
        "is_novel": bool(score > model.threshold),
        "normalized_signal_errors": {
            name.removesuffix("__median"): float(value)
            for name, value in zip(model.target_names, normalized, strict=True)
        },
        "label_status": "unlabeled_dataset_not_fault_diagnosis",
    }


@app.post("/v1/estimate/oxford-rul")
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
