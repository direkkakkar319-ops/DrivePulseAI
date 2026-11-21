"""Versioned recorded KIT analysis; no health, fault or maintenance estimates."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inference import KitModelMetadata, NonNegativeFinite


class SampleInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    display_name: str
    recording_id: str
    recording_date: date
    dataset: str
    creator: str
    source_doi: str
    license: str
    license_url: str
    source_split: Literal["train", "validation", "test"]
    window_count: int = Field(gt=0)
    valid_pair_count: int = Field(gt=0)
    window_seconds: Literal[10]
    compatible_model_version: Literal["kit-xgb-forecast-v1"]
    limitations: list[str] = Field(min_length=1)


class SampleCatalog(BaseModel):
    schema_version: Literal[1] = 1
    samples: list[SampleInfo]


class WindowReference(BaseModel):
    id: str
    recording_id: str
    recording_date: str
    split: str
    segment_id: int
    start_seconds: int
    end_seconds: int
    relative_start_seconds: int


class SignalDeviation(BaseModel):
    signal: str
    normalized_error: NonNegativeFinite


class PairAnalysis(BaseModel):
    pair_id: str
    current_window: WindowReference
    next_window: WindowReference
    anomaly_score: NonNegativeFinite
    threshold: NonNegativeFinite
    is_novel: bool
    normalized_signal_errors: dict[str, NonNegativeFinite]
    top_signal_deviations: list[SignalDeviation]


class AnalysisSummary(BaseModel):
    evaluated_pairs: int = Field(gt=0)
    novel_pairs: int = Field(ge=0)
    not_novel_pairs: int = Field(ge=0)
    novel_percentage: NonNegativeFinite = Field(le=100)
    max_anomaly_score: NonNegativeFinite
    mean_anomaly_score: NonNegativeFinite
    threshold: NonNegativeFinite = Field(gt=0)


class FlaggedInterval(BaseModel):
    recording_id: str
    recording_date: str
    split: str
    segment_id: int
    start_seconds: int
    end_seconds: int
    pair_ids: list[str]
    peak_anomaly_score: NonNegativeFinite


class ScorePoint(BaseModel):
    pair_id: str
    window: WindowReference
    anomaly_score: NonNegativeFinite
    threshold: NonNegativeFinite
    is_novel: bool


class SignalDefinition(BaseModel):
    name: str
    unit: str
    display_name: str = ""


class TelemetryWindow(BaseModel):
    window: WindowReference
    medians: dict[str, Annotated[float, Field(allow_inf_nan=False)]]
    # Sparse: omitted signals have zero missing fraction, never an absent median.
    missing_fractions: dict[
        str, Annotated[float, Field(ge=0, lt=1, allow_inf_nan=False)]
    ] = Field(default_factory=dict)


class AnalysisExplanation(BaseModel):
    summary: str
    signal_summary: str
    signal_scope: Literal["flagged_pairs", "all_evaluated_pairs"]
    # Maximum per-signal normalized error over the stated scope, positive only.
    strongest_signal_deviations: list[SignalDeviation]
    score_definition: str = (
        "Maximum absolute observed-minus-forecast target-median residual divided "
        "by its saved per-signal calibration scale; dimensionless, not a probability."
    )
    threshold_definition: str = (
        "Saved calibration 99th-percentile score; a pair is novel only when "
        "score > threshold. Equality is not novel."
    )
    signal_definition: str = (
        "Ranked normalized forecast deviations, not causal feature importance "
        "or evidence that a component is broken. Ties follow fitted signal order."
    )
    measurement_definition: str = (
        "Telemetry contains observed ten-second medians, not forecasts. Sparse "
        "missing_fractions report partial missingness; omitted entries mean zero "
        "missingness. Entirely missing required signals make a window ineligible. "
        "No zero filling, interpolation or UTC timezone inference is performed."
    )
    limitations: str = (
        "KIT is unlabeled combustion-engine research telemetry. Novelty is not "
        "confirmed mechanical fault diagnosis, model accuracy, vehicle health, "
        "EV battery health or remaining useful life. Unflagged data does not "
        "establish the absence of faults."
    )


class PreparedAnalysis(BaseModel):
    """Shared sample/CSV result after preparation; additive version-1 contract."""

    schema_version: Literal[1] = 1
    analysis_type: Literal["kit_telemetry_novelty"] = "kit_telemetry_novelty"
    model: KitModelMetadata
    window_count: int
    pair_count: int
    window_seconds: Literal[10] = 10
    summary: AnalysisSummary
    predictions: list[PairAnalysis]
    flagged_intervals: list[FlaggedInterval]
    score_series: list[ScorePoint]
    signals: list[SignalDefinition]
    telemetry: list[TelemetryWindow]
    explanation: AnalysisExplanation
    time_basis: str = "source clock seconds since midnight; timezone unknown"
    relative_time_basis: str = (
        "seconds from first retained window of each recording/date/segment/split"
    )
    interval_definition: str = (
        "[start, end); consecutive flagged target windows only; no gap bridging"
    )
    contribution_definition: str = (
        "largest normalized forecast errors; not causal fault attribution"
    )
    persisted: Literal[False] = False


class SampleAnalysis(PreparedAnalysis):
    source_type: Literal["packaged_sample"] = "packaged_sample"
    sample: SampleInfo
    limitations: list[str]


class UploadedSource(BaseModel):
    kind: Literal["uploaded_csv"] = "uploaded_csv"
    format_version: Literal["kit_obd_raw_v1"] = "kit_obd_raw_v1"
    preprocessing_version: Literal["kit-10s-window-recipe-v1"] = (
        "kit-10s-window-recipe-v1"
    )
    recording_id: str
    recording_date: str
    metadata_verification: Literal["caller_supplied_unverified"] = (
        "caller_supplied_unverified"
    )
    input_bytes: int
    accepted_rows: int
    missing_cells: int
    discarded_incomplete_windows: int
    backward_timestamp_jumps: int
    duplicate_timestamp_rows: int


class UploadedAnalysis(PreparedAnalysis):
    source_type: Literal["uploaded_csv"] = "uploaded_csv"
    source: UploadedSource
    limitations: list[str]
