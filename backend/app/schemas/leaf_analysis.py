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
SIGNALS = (
    *FEATURES,
    "SOH",
    "Odometer",
    "Speed",
    "Instant_kW",
    "kWh_Remaining",
    "Pack_Avg_C_Temp",
)


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


TrendSignal = Literal[
    "pack_temp_spread", "pack_temp_rise", "soh_decline_rate_per_kkm", "pack_avg_temp"
]


class TrendSignalDetail(StrictModel):
    status: Literal[
        "normal",
        "warning",
        "critical",
        "non_finite_current_reading",
        "insufficient_baseline_points",
    ]
    label: str
    unit: str | None = None
    current_value: float | None = None
    baseline_mean: float | None = None
    baseline_std: float | None = Field(default=None, gt=0)
    z_score: float | None = None
    consecutive_abnormal_days: int | None = Field(default=None, ge=0)
    baseline_window_days: int | None = Field(default=None, ge=0)
    baseline_points_available: int | None = Field(default=None, ge=0)
    baseline_points_required: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def complete_signal(self):
        required = (
            "unit",
            "current_value",
            "baseline_mean",
            "baseline_std",
            "z_score",
            "consecutive_abnormal_days",
            "baseline_window_days",
        )
        if self.status in {"normal", "warning", "critical"} and any(
            getattr(self, name) is None for name in required
        ):
            raise ValueError("Incomplete trend signal")
        if self.status == "insufficient_baseline_points" and (
            self.baseline_points_available is None
            or self.baseline_points_required is None
        ):
            raise ValueError("Incomplete baseline coverage")
        return self


class TrendAlert(StrictModel):
    signal: TrendSignal
    label: str
    severity: Literal["warning", "critical"]
    z_score: float
    current_value: float
    baseline_mean: float
    baseline_std: float = Field(gt=0)
    unit: str
    consecutive_days: int = Field(ge=1)
    explanation: str


class TrendResponse(StrictModel):
    schema_version: Literal[1]
    model_version: Literal["nissan-leaf-rolling-zscore-v1"]
    assessment_type: Literal["rolling_zscore_drift_detection"]
    status: Literal["ok", "insufficient_history", "empty_input"]
    is_drift_detected: bool = Field(strict=True)
    drift_alerts_count: int = Field(ge=0, le=4, strict=True)
    alerts: list[TrendAlert] = Field(max_length=4)
    signal_details: dict[TrendSignal, TrendSignalDetail]
    days_available: int | None = Field(default=None, ge=0)
    min_days_required: int | None = Field(default=None, ge=1)
    days_evaluated: int | None = Field(default=None, ge=1)
    window_size_days: int | None = Field(default=None, ge=3, le=90)
    warning_z_threshold: float | None = Field(default=None, gt=0)
    critical_z_threshold: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def consistent_trends(self):
        if self.drift_alerts_count != len(
            self.alerts
        ) or self.is_drift_detected != bool(self.alerts):
            raise ValueError("Invalid trend alert count")
        signals = [alert.signal for alert in self.alerts]
        if len(set(signals)) != len(signals):
            raise ValueError("Duplicate trend alerts")
        if self.status == "ok":
            if any(
                getattr(self, name) is None
                for name in (
                    "days_evaluated",
                    "window_size_days",
                    "warning_z_threshold",
                    "critical_z_threshold",
                )
            ):
                raise ValueError("Missing trend metadata")
            if self.critical_z_threshold <= self.warning_z_threshold:
                raise ValueError("Invalid trend thresholds")
        else:
            if self.alerts or self.signal_details:
                raise ValueError("Unavailable trend must not contain alerts")
            if self.status == "insufficient_history" and (
                self.days_available is None or self.min_days_required is None
            ):
                raise ValueError("Missing trend history coverage")
            if (
                self.status == "insufficient_history"
                and self.days_available >= self.min_days_required
            ):
                raise ValueError("Inconsistent insufficient history")
        flagged = {
            name
            for name, detail in self.signal_details.items()
            if detail.status in {"warning", "critical"}
        }
        if flagged != set(signals):
            raise ValueError("Mismatched trend alerts/signals")
        for alert in self.alerts:
            detail = self.signal_details[alert.signal]
            if (
                detail.status != alert.severity
                or detail.label != alert.label
                or detail.unit != alert.unit
                or detail.consecutive_abnormal_days != alert.consecutive_days
            ):
                raise ValueError("Inconsistent trend signal identity")
            if any(
                getattr(detail, name) != getattr(alert, name)
                for name in (
                    "z_score",
                    "current_value",
                    "baseline_mean",
                    "baseline_std",
                )
            ):
                raise ValueError("Inconsistent trend measurements")
        return self


class SignalAvailability(StrictModel):
    status: Literal["available", "unavailable"]
    reason: str | None = None


class TrendAnalysis(StrictModel):
    status: Literal["completed", "unavailable", "insufficient_history", "failed"] = (
        "unavailable"
    )
    reason: str | None = "Trend analysis was not requested"
    prepared_readings: int = 0
    analyzed_readings: int = 0
    skipped_readings: int = 0
    observed_days: int = 0
    start_timestamp_us: int | None = None
    end_timestamp_us: int | None = None
    source_fields: list[str] = []
    signal_availability: dict[TrendSignal, SignalAvailability] = {}
    warnings: list[str] = []
    limitations: list[str] = []
    result: TrendResponse | None = None


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
    trend: TrendAnalysis = Field(default_factory=TrendAnalysis)
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
