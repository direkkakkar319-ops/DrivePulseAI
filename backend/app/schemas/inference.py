"""Main-backend wire contracts matching the secured KIT batch service."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.kit_samples import FEATURE_NAMES, SIGNALS, TARGET_NAMES

NonNegativeFinite = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class KitPairPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    pair_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    )
    current_window_features: dict[str, float]
    next_window_medians: dict[str, float]

    @field_validator("current_window_features", "next_window_medians")
    @classmethod
    def fitted_columns(cls, value, info):
        expected = (
            FEATURE_NAMES
            if info.field_name == "current_window_features"
            else TARGET_NAMES
        )
        if set(value) != set(expected) or not all(
            math.isfinite(v) for v in value.values()
        ):
            raise ValueError("Invalid KIT inference features")
        return {name: value[name] for name in expected}


class KitBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    pairs: list[KitPairPayload] = Field(min_length=1, max_length=256)


class KitModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    schema_version: int = Field(ge=1, le=1)
    model_version: Literal["kit-xgb-forecast-v1"]
    assessment_type: Literal["novelty"]
    threshold: float = Field(gt=0, allow_inf_nan=False)
    label_status: Literal["unlabeled_dataset_not_fault_diagnosis"]


class KitPrediction(KitModelMetadata):
    pair_id: str
    anomaly_score: NonNegativeFinite
    is_novel: bool
    normalized_signal_errors: dict[str, NonNegativeFinite]

    @model_validator(mode="after")
    def consistent_score(self):
        if set(self.normalized_signal_errors) != set(SIGNALS):
            raise ValueError("Invalid signal-error columns")
        if not math.isclose(
            self.anomaly_score,
            max(self.normalized_signal_errors.values()),
            rel_tol=1e-9,
            abs_tol=1e-12,
        ) or self.is_novel != (self.anomaly_score > self.threshold):
            raise ValueError("Inconsistent KIT prediction")
        return self


class KitInferenceResult(KitModelMetadata):
    results: list[KitPrediction]


class KitBatchResponse(KitInferenceResult):
    results: list[KitPrediction] = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def consistent_metadata(self):
        if any(result.threshold != self.threshold for result in self.results):
            raise ValueError("Inconsistent KIT response metadata")
        return self
