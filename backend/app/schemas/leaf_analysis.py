"""Versioned observation-based contract; independent of obsolete KIT windows."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FEATURES = (
    "HV_Bat_Voltage",
    "Pack_1_C_Temp",
    "SOC",
    "HV_Bat_Current_2",
    "Pack_2_C_Temp",
    "Pack_4_C_Temp",
)
SIGNALS = (*FEATURES, "SOH", "Odometer", "Speed", "Instant_kW", "kWh_Remaining")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Contribution(StrictModel):
    rank: int = Field(ge=1, le=3)
    feature: str
    measured_value: float
    shap_value: float
    direction: Literal["toward_anomaly", "toward_typical"]


class Explanation(StrictModel):
    method: Literal["shap_permutation"]
    output: str
    baseline_score: float
    contributions: list[Contribution] = Field(min_length=3, max_length=3)
    interpretation: str


class Prediction(StrictModel):
    anomaly_score: float
    is_unusual: bool
    explanation: Explanation | None


class AnomalyResponse(StrictModel):
    schema_version: Literal[1]
    model_version: Literal["nissan-leaf-isolation-forest-v1"]
    assessment_type: Literal["unsupervised_novelty"]
    label_status: Literal["unlabeled_dataset_unusual_telemetry_not_fault_diagnosis"]
    threshold: float
    explanation_status: Literal["top_three_shap_contributions_for_unusual_rows"]
    results: list[Prediction]


class Availability(StrictModel):
    status: Literal["completed", "unavailable", "insufficient_history", "failed"]
    reason: str | None = None
    result: dict[str, Any] | None = None


class Reading(StrictModel):
    row_id: int
    timestamp_us: int
    values: dict[str, float | None]


class ScoredReading(Prediction):
    row_id: int
    timestamp_us: int


class AnomalyAnalysis(StrictModel):
    status: Literal["completed", "unavailable", "failed"]
    reason: str | None = None
    model_version: str | None = None
    threshold: float | None = None
    score_direction: Literal["lower_is_more_unusual"] = "lower_is_more_unusual"
    analyzed_count: int = 0
    skipped_count: int = 0
    unusual_count: int = 0
    unusual_percentage: float = 0
    explanation_status: str | None = None
    results: list[ScoredReading] = []


class BatteryOverview(StrictModel):
    latest_soc: float | None
    soc_timestamp_us: int | None
    latest_soh: float | None
    soh_timestamp_us: int | None
    estimated_range_km: float | None = None
    range_status: Literal["unavailable"] = "unavailable"
    range_reason: str = "Verified usable energy and a reliable consumption rate are not available. SOC, SOH and nominal capacity alone cannot establish driving range."


class LeafAnalysis(StrictModel):
    schema_version: Literal[1] = 1
    analysis_type: Literal["nissan_leaf_telemetry"] = "nissan_leaf_telemetry"
    source_type: Literal["built_in_sample", "uploaded_csv"]
    source: dict[str, Any]
    recording: dict[str, Any]
    battery: BatteryOverview
    anomaly: AnomalyAnalysis
    health: Availability
    rul: Availability
    telemetry: list[Reading]
    units: dict[str, str]
    warnings: list[str]
    limitations: list[str]
    persisted: Literal[False] = False


class HealthBand(StrictModel):
    minimum_soh_pct: float = Field(ge=0, le=100)
    maximum_soh_pct: float = Field(ge=0, le=100)
    score: int = Field(ge=1, le=5)


class HealthResponse(StrictModel):
    schema_version: Literal[1]
    model_version: Literal["nissan-leaf-soh-bands-v1"]
    assessment_type: Literal["soh_band_score"]
    health_score: int = Field(ge=1, le=5, strict=True)
    score_scale: str
    soh_pct: float = Field(ge=0, le=100)
    label: Literal[
        "very_healthy",
        "healthy",
        "moderate_degradation",
        "degraded",
        "end_of_life_range",
    ]
    bands: list[HealthBand] = Field(min_length=5, max_length=5)
    threshold_note: str


class RULConfidenceInterval(StrictModel):
    level_pct: float = Field(gt=0, lt=100)
    rul_km_p10: float = Field(ge=0)
    rul_km_p50: float = Field(ge=0)
    rul_km_p90: float = Field(ge=0)
    estimated_days_p10: float | None = Field(default=None, ge=0)
    estimated_days_p50: float | None = Field(default=None, ge=0)
    estimated_days_p90: float | None = Field(default=None, ge=0)
    bootstrap_iterations_valid: int = Field(ge=0)
    interpretation: str | None = None

    @model_validator(mode="after")
    def ordered_bounds(self):
        if not self.rul_km_p10 <= self.rul_km_p50 <= self.rul_km_p90:
            raise ValueError("Unordered RUL interval")
        days = [
            self.estimated_days_p10,
            self.estimated_days_p50,
            self.estimated_days_p90,
        ]
        if any(v is not None for v in days) and (
            any(v is None for v in days) or not days[0] <= days[1] <= days[2]
        ):
            raise ValueError("Invalid days interval")
        return self


class RULResponse(StrictModel):
    schema_version: Literal[1]
    model_version: Literal["nissan-leaf-soh-theilsen-v1"]
    assessment_type: Literal["experimental_soh_threshold_distance"]
    target_definition: str
    status: Literal[
        "ok",
        "no_valid_history",
        "threshold_reached",
        "insufficient_history",
        "insufficient_odometer_variation",
        "non_declining_trend",
    ]
    rul_km: float | None = Field(ge=0)
    rul_km_p10: float | None = Field(default=None, ge=0)
    rul_km_p50: float | None = Field(default=None, ge=0)
    rul_km_p90: float | None = Field(default=None, ge=0)
    estimated_days_to_threshold_p10: float | None = Field(default=None, ge=0)
    estimated_days_to_threshold_p50: float | None = Field(default=None, ge=0)
    estimated_days_to_threshold_p90: float | None = Field(default=None, ge=0)
    confidence_interval: RULConfidenceInterval | None = None
    current_soh_pct: float | None = Field(default=None, ge=0, le=100)
    current_odometer_km: float | None = Field(default=None, ge=0)
    health_score: int | None = Field(default=None, ge=1, le=5)
    health_label: str | None = None
    eol_threshold_soh_pct: float | None = Field(default=None, gt=0, lt=100)
    daily_observations_used: int | None = Field(default=None, ge=0)
    history_span_days: int | None = Field(default=None, ge=0)
    minimum_history_span_days: int | None = Field(default=None, ge=1)
    context_summary: dict[str, float] | None = None
    context_use: str | None = None
    soh_slope_pct_per_1000_km: float | None = None
    estimated_days_to_threshold: float | None = Field(default=None, ge=0)
    average_calendar_distance_km_per_day: float | None = Field(default=None, gt=0)
    validation_status: str | None = None
    limitations: list[str]

    @model_validator(mode="after")
    def compatible_optional_intervals(self):
        for names in (
            ("rul_km_p10", "rul_km_p50", "rul_km_p90"),
            (
                "estimated_days_to_threshold_p10",
                "estimated_days_to_threshold_p50",
                "estimated_days_to_threshold_p90",
            ),
        ):
            values = [getattr(self, name) for name in names]
            if any(v is not None for v in values) and (
                any(v is None for v in values)
                or not values[0] <= values[1] <= values[2]
            ):
                raise ValueError("Invalid RUL percentile fields")
        if self.confidence_interval is not None:
            for flat, nested in (
                ("rul_km_p10", "rul_km_p10"),
                ("rul_km_p50", "rul_km_p50"),
                ("rul_km_p90", "rul_km_p90"),
                ("estimated_days_to_threshold_p10", "estimated_days_p10"),
                ("estimated_days_to_threshold_p50", "estimated_days_p50"),
                ("estimated_days_to_threshold_p90", "estimated_days_p90"),
            ):
                value = getattr(self, flat)
                if value is not None and value != getattr(
                    self.confidence_interval, nested
                ):
                    raise ValueError("Inconsistent RUL interval fields")
        return self
