"""Recording orchestration and deterministic postprocessing of genuine ML output."""

from collections import defaultdict
from datetime import date
from math import fsum

from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisExplanation,
    AnalysisSummary,
    FlaggedInterval,
    PairAnalysis,
    PreparedAnalysis,
    SampleAnalysis,
    SampleInfo,
    ScorePoint,
    SignalDefinition,
    SignalDeviation,
    TelemetryWindow,
    UploadedAnalysis,
    UploadedSource,
    WindowReference,
)
from app.schemas.inference import KitInferenceResult, KitModelMetadata
from app.services.inference_service import KITInferenceService
from app.services.kit_samples import (
    MANIFEST_PATH,
    SIGNALS,
    WINDOW_SECONDS,
    KitSample,
    KitWindow,
    KitWindowPair,
    SampleDataError,
    load_sample,
    make_window_pairs,
    sample_ids,
    validate_window,
)

UNITS = ("°C", "kPa", "RPM", "km/h", "°C", "g/s", "%", "°C", "%", "%")
SIGNAL_LABELS = (
    "Engine coolant temperature",
    "Intake manifold absolute pressure",
    "Engine RPM",
    "Vehicle speed",
    "Intake air temperature",
    "Mass air flow",
    "Throttle position",
    "Ambient air temperature",
    "Accelerator pedal position D",
    "Accelerator pedal position E",
)
DISCLAIMERS = (
    "Novelty means unusual forecast deviation, not confirmed mechanical fault diagnosis.",
    "Largest signal errors are not causal explanations or confirmed broken components.",
    "No EV battery-health, failure-probability or predictive-maintenance estimate is made.",
)


def public_sample(sample: KitSample) -> SampleInfo:
    fields = SampleInfo.model_fields
    try:
        values = {name: sample.manifest[name] for name in fields}
        values["recording_date"] = date.fromisoformat(values["recording_date"])
        result = SampleInfo.model_validate(values)
        if result.window_count != len(sample.windows) or result.valid_pair_count != len(
            sample.pairs
        ):
            raise ValueError
        return result
    except (KeyError, TypeError, ValueError, ValidationError):
        raise SampleDataError("Incompatible public sample metadata") from None


def available_samples() -> list[SampleInfo]:
    # Validate assets too: a listing must not advertise missing/corrupt recordings.
    return [
        public_sample(load_sample(value, manifest_path=MANIFEST_PATH))
        for value in sample_ids(manifest_path=MANIFEST_PATH)
    ]


def load_analysis_sample(sample_id: str) -> tuple[KitSample, SampleInfo]:
    sample = load_sample(sample_id, manifest_path=MANIFEST_PATH)
    return sample, public_sample(sample)


def window_key(window: KitWindow) -> tuple:
    return (
        window.recording_id,
        window.recording_date,
        window.segment_id,
        window.split,
        window.start_seconds,
    )


def merge_flagged_intervals(predictions: list[PairAnalysis]) -> list[FlaggedInterval]:
    intervals = []
    previous = None
    for prediction in predictions:
        if not prediction.is_novel:
            previous = None
            continue
        target = prediction.next_window
        group = (
            target.recording_id,
            target.recording_date,
            target.split,
            target.segment_id,
        )
        if (
            previous is not None
            and previous.end_seconds == target.start_seconds
            and (
                previous.recording_id,
                previous.recording_date,
                previous.split,
                previous.segment_id,
            )
            == group
        ):
            previous.end_seconds = target.end_seconds
            previous.pair_ids.append(prediction.pair_id)
            previous.peak_anomaly_score = max(
                previous.peak_anomaly_score, prediction.anomaly_score
            )
        else:
            previous = FlaggedInterval(
                recording_id=target.recording_id,
                recording_date=target.recording_date,
                split=target.split,
                segment_id=target.segment_id,
                start_seconds=target.start_seconds,
                end_seconds=target.end_seconds,
                pair_ids=[prediction.pair_id],
                peak_anomaly_score=prediction.anomaly_score,
            )
            intervals.append(previous)
    return intervals


def build_analysis(
    windows: tuple[KitWindow, ...],
    pairs: tuple[KitWindowPair, ...],
    inference: KitInferenceResult,
) -> PreparedAnalysis:
    """No sample-specific parsing or model invocation; reusable after CSV preparation."""
    if not windows or not pairs or len(inference.results) != len(pairs):
        raise ValueError("Incomplete analysis inputs")
    # Recheck mutable objects at the aggregation boundary, before serializing.
    inference = KitInferenceResult.model_validate(inference.model_dump())
    seen_groups = set()
    previous_group = previous_start = None
    for window in windows:
        validate_window(window)
        group = window_key(window)[:-1]
        if group != previous_group:
            if group in seen_groups:
                raise ValueError("Interleaved prepared timelines")
            seen_groups.add(group)
        elif window.start_seconds <= previous_start:
            raise ValueError("Unordered prepared timeline")
        previous_group, previous_start = group, window.start_seconds
    if pairs != make_window_pairs(windows):
        raise ValueError("Incomplete or incompatible prepared pairs")
    starts = defaultdict(list)
    for window in windows:
        starts[window_key(window)[:-1]].append(window.start_seconds)
    bases = {group: min(values) for group, values in starts.items()}
    refs = {
        window_key(w): WindowReference(
            id=f"window-{i:06d}",
            recording_id=w.recording_id,
            recording_date=w.recording_date,
            split=w.split,
            segment_id=w.segment_id,
            start_seconds=w.start_seconds,
            end_seconds=w.start_seconds + WINDOW_SECONDS,
            relative_start_seconds=w.start_seconds - bases[window_key(w)[:-1]],
        )
        for i, w in enumerate(windows)
    }
    if len(refs) != len(windows):
        raise ValueError("Duplicate prepared window keys")
    predictions = []
    for index, (pair, result) in enumerate(zip(pairs, inference.results, strict=True)):
        if (
            result.pair_id != f"pair-{index:06d}"
            or result.threshold != inference.threshold
        ):
            raise ValueError("Incompatible pair result")
        ranked = sorted(
            SIGNALS, key=lambda name: -result.normalized_signal_errors[name]
        )
        predictions.append(
            PairAnalysis(
                pair_id=result.pair_id,
                current_window=refs[window_key(pair.current)],
                next_window=refs[window_key(pair.following)],
                anomaly_score=result.anomaly_score,
                threshold=result.threshold,
                is_novel=result.is_novel,
                normalized_signal_errors=result.normalized_signal_errors,
                top_signal_deviations=[
                    SignalDeviation(
                        signal=name,
                        normalized_error=result.normalized_signal_errors[name],
                    )
                    for name in ranked[:3]
                ],
            )
        )
    scores = [p.anomaly_score for p in predictions]
    count = len(scores)
    novel = sum(p.is_novel for p in predictions)
    maximum = max(scores)
    # Scale before summation to avoid overflow for large finite scores while
    # retaining subnormal values when the entire collection is very small.
    mean = (
        maximum * (fsum(score / maximum for score in scores) / count) if maximum else 0
    )
    intervals = merge_flagged_intervals(predictions)
    return PreparedAnalysis(
        model=KitModelMetadata.model_validate(
            inference.model_dump(exclude={"results"})
        ),
        window_count=len(windows),
        pair_count=len(pairs),
        summary=AnalysisSummary(
            evaluated_pairs=count,
            novel_pairs=novel,
            not_novel_pairs=count - novel,
            novel_percentage=novel / count * 100,
            max_anomaly_score=maximum,
            mean_anomaly_score=mean,
            threshold=inference.threshold,
        ),
        predictions=predictions,
        flagged_intervals=intervals,
        explanation=explain(predictions, intervals),
        score_series=[
            ScorePoint(
                pair_id=p.pair_id,
                window=p.next_window,
                anomaly_score=p.anomaly_score,
                threshold=p.threshold,
                is_novel=p.is_novel,
            )
            for p in predictions
        ],
        signals=[
            SignalDefinition(name=name, unit=unit, display_name=label)
            for name, unit, label in zip(SIGNALS, UNITS, SIGNAL_LABELS, strict=True)
        ],
        telemetry=[
            TelemetryWindow(
                window=refs[window_key(w)],
                medians={name: w.features[f"{name}__median"] for name in SIGNALS},
                missing_fractions={
                    name: w.features[f"{name}__missing_fraction"]
                    for name in SIGNALS
                    if w.features[f"{name}__missing_fraction"] > 0
                },
            )
            for w in windows
        ],
    )


def explain(
    predictions: list[PairAnalysis], intervals: list[FlaggedInterval]
) -> AnalysisExplanation:
    """Deterministic text from validated results, without causal inference."""
    flagged = [p for p in predictions if p.is_novel]
    scope = flagged or predictions
    errors = {
        name: max(p.normalized_signal_errors[name] for p in scope) for name in SIGNALS
    }
    ranked = sorted(SIGNALS, key=lambda name: -errors[name])
    strongest = [
        SignalDeviation(signal=name, normalized_error=errors[name])
        for name in ranked
        if errors[name] > 0
    ][:3]
    count, total = len(flagged), len(predictions)
    if not count:
        summary = (
            f"None of {total} evaluated window pairs exceeded the model's novelty "
            "threshold. No novel intervals were detected. This does not rule out faults."
        )
    else:
        summary = (
            f"{count} of {total} evaluated window pairs exceeded the model's novelty "
            f"threshold, forming {len(intervals)} flagged "
            f"{'interval' if len(intervals) == 1 else 'intervals'}. "
            "Interval details show the scored time ranges and corresponding window pairs."
        )
    labels = dict(zip(SIGNALS, SIGNAL_LABELS, strict=True))
    if strongest:
        names = ", ".join(labels[item.signal] for item in strongest)
        signal_summary = (
            f"Largest normalized forecast deviations across "
            f"{'flagged' if flagged else 'evaluated'} pairs: {names}. "
            "Each listed value is that signal's maximum over this scope, not a cause."
        )
    else:
        signal_summary = "All returned normalized forecast deviations were zero."
    return AnalysisExplanation(
        summary=summary,
        signal_summary=signal_summary,
        signal_scope="flagged_pairs" if flagged else "all_evaluated_pairs",
        strongest_signal_deviations=strongest,
    )


async def analyze_prepared(
    windows: tuple[KitWindow, ...],
    pairs: tuple[KitWindowPair, ...],
    service: KITInferenceService,
) -> PreparedAnalysis:
    inference = await service.score_pairs(pairs)
    return build_analysis(windows, pairs, inference)


async def analyze_sample(
    sample: KitSample, info: SampleInfo, service: KITInferenceService
) -> SampleAnalysis:
    result = await analyze_prepared(sample.windows, sample.pairs, service)
    if info.compatible_model_version != result.model.model_version:
        raise SampleDataError("Incompatible sample/model version")
    return SampleAnalysis(
        **result.model_dump(),
        sample=info,
        limitations=list(dict.fromkeys([*info.limitations, *DISCLAIMERS])),
    )


async def analyze_upload(recording, service: KITInferenceService) -> UploadedAnalysis:
    result = await analyze_prepared(recording.windows, recording.pairs, service)
    return UploadedAnalysis(
        **result.model_dump(),
        source=UploadedSource(
            recording_id=recording.recording_id,
            recording_date=recording.recording_date,
            input_bytes=recording.input_bytes,
            accepted_rows=recording.accepted_rows,
            missing_cells=recording.missing_cells,
            discarded_incomplete_windows=recording.discarded_windows,
            backward_timestamp_jumps=recording.backward_jumps,
            duplicate_timestamp_rows=recording.duplicate_timestamps,
        ),
        limitations=[
            *DISCLAIMERS,
            "Uploaded provenance, declared date and physical sensor accuracy are unverified.",
            "The upload identifier is a content reference, not a vehicle identity.",
            "No Garage association, UTC timezone or dataset train/test role is inferred.",
            "Only the documented KIT raw header/unit contract is supported.",
        ],
    )
