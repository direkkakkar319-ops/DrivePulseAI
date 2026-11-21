"""Phase 3C contracts; controlled boundary fixtures are not claimed ML results."""

import copy
import json
import math
from dataclasses import replace

import pytest
from pydantic import ValidationError
from test_analysis_api import ANALYZE, AUTH
from test_analysis_api import genuine as genuine  # noqa: PLC0414
from test_analysis_api import harness as harness  # noqa: PLC0414

from app.schemas.analysis import SampleAnalysis
from app.schemas.inference import KitInferenceResult
from app.services.analysis_service import build_analysis
from app.services.kit_samples import SIGNALS, load_sample, make_window_pairs

# This suite targets the retired KIT API/assets, removed before Nissan integration.
# Retain its assertions for historical reference; active coverage is test_leaf_analysis.py.
pytestmark = pytest.mark.skip(
    reason="Retired KIT contract/assets; replaced by Nissan observation analysis"
)


def controlled(genuine, scores, windows=None):
    """Use real windows with explicitly synthetic scores to test arithmetic edges."""
    windows = windows or load_sample("kit-20180320-normal").windows[: len(scores) + 1]
    pairs = make_window_pairs(windows)
    assert len(pairs) == len(scores)
    payload = copy.deepcopy(genuine["response"])
    payload["results"] = payload["results"][: len(scores)]
    for item, score in zip(payload["results"], scores, strict=True):
        item["anomaly_score"] = score
        item["is_novel"] = score > item["threshold"]
        item["normalized_signal_errors"] = dict.fromkeys(SIGNALS, score)
    return windows, pairs, KitInferenceResult.model_validate(payload)


@pytest.mark.parametrize(
    "scores,intervals",
    [
        ([0.0, 0.0], 0),
        ([9.0], 1),
        ([9.0, 10.0, 11.0], 1),
        ([9.0, 0.0, 10.0], 2),
        ([0.0, 9.0, 0.0], 1),
    ],
)
def test_explanations_and_interval_edges(genuine, scores, intervals):
    result = build_analysis(*controlled(genuine, scores))
    count = sum(v > result.summary.threshold for v in scores)
    assert result.summary.novel_pairs == count
    assert result.summary.not_novel_pairs == len(scores) - count
    assert result.summary.novel_percentage == pytest.approx(count / len(scores) * 100)
    assert result.summary.mean_anomaly_score == pytest.approx(sum(scores) / len(scores))
    assert len(result.flagged_intervals) == intervals
    assert result.explanation.signal_scope == (
        "flagged_pairs" if count else "all_evaluated_pairs"
    )
    assert f"of {len(scores)} evaluated window pairs" in result.explanation.summary
    assert "not" in result.explanation.limitations
    for interval in result.flagged_intervals:
        targets = [
            p.next_window for p in result.predictions if p.pair_id in interval.pair_ids
        ]
        assert interval.start_seconds == targets[0].start_seconds
        assert interval.end_seconds == targets[-1].end_seconds
        assert interval.end_seconds - interval.start_seconds == 10 * len(targets)
        assert interval.peak_anomaly_score == max(
            p.anomaly_score
            for p in result.predictions
            if p.pair_id in interval.pair_ids
        )
    if not any(scores):
        assert result.explanation.strongest_signal_deviations == []
        assert "zero" in result.explanation.signal_summary


def test_tie_order_dimensionless_errors_and_display_names(genuine):
    result = build_analysis(*controlled(genuine, [9.0, 10.0]))
    assert [s.name for s in result.signals] == list(SIGNALS)
    assert [s.unit for s in result.signals] == [
        "°C",
        "kPa",
        "RPM",
        "km/h",
        "°C",
        "g/s",
        "%",
        "°C",
        "%",
        "%",
    ]
    for values in [
        result.explanation.strongest_signal_deviations,
        *[p.top_signal_deviations for p in result.predictions],
    ]:
        assert [v.signal for v in values] == list(SIGNALS[:3])
        assert "unit" not in values[0].model_dump()
    assert "Engine coolant temperature" in result.explanation.signal_summary
    assert "not a probability" in result.explanation.score_definition
    assert "score > threshold" in result.explanation.threshold_definition


@pytest.mark.parametrize(
    "scores", [[1e308, 1e308], [5e-324, 5e-324], [0.0, 0.0], [1e-10, 1e-9]]
)
def test_finite_scores_do_not_overflow_summary(genuine, scores):
    result = build_analysis(*controlled(genuine, scores))
    assert math.isfinite(result.summary.mean_anomaly_score)
    expected = scores[0] if scores[0] == scores[1] else sum(scores) / 2
    assert result.summary.mean_anomaly_score == pytest.approx(
        expected, abs=0, rel=1e-14
    )
    json.dumps(result.model_dump(mode="json"), allow_nan=False)


def test_strict_threshold_equality_and_float_precision(genuine):
    threshold = genuine["response"]["threshold"]
    result = build_analysis(
        *controlled(genuine, [threshold, math.nextafter(threshold, math.inf)])
    )
    assert [p.is_novel for p in result.predictions] == [False, True]


@pytest.mark.parametrize(
    "boundary", ["segment", "recording", "date", "split", "gap", "backwards"]
)
def test_graphs_intervals_and_pairs_respect_timelines(genuine, boundary):
    original = load_sample("kit-20180320-normal").windows[:5]
    first = original[:3]
    edits = {"segment_id": 1}
    if boundary == "recording":
        edits = {"recording_id": "other"}
    if boundary == "date":
        edits = {"recording_date": "2018-03-21"}
    if boundary == "split":
        edits = {"split": "validation"}
    if boundary == "gap":
        edits = {"start_seconds": first[-1].start_seconds + 20}
    if boundary == "backwards":
        edits = {"segment_id": 1, "start_seconds": 100}
    if boundary != "gap":
        start = edits.pop("start_seconds", first[-1].start_seconds + 10)
    else:
        start = edits.pop("start_seconds")
    last = tuple(
        replace(w, start_seconds=start + i * 10, **edits)
        for i, w in enumerate(original[3:])
    )
    result = build_analysis(*controlled(genuine, [9.0, 10.0, 11.0], first + last))
    assert len(result.flagged_intervals) == 2
    assert [p.window for p in result.score_series] == [
        p.next_window for p in result.predictions
    ]
    assert [p.window.start_seconds for p in result.telemetry] == [
        w.start_seconds for w in first + last
    ]
    assert result.telemetry[3].window.relative_start_seconds == (
        40 if boundary == "gap" else 0
    )


def test_missing_measurements_and_valid_zero_are_distinct(genuine):
    windows, _pairs, inference = controlled(genuine, [0.0, 0.0])
    windows = copy.deepcopy(windows)
    # Isolate the missingness policy from the original recording's partial gaps.
    for window in windows:
        for signal in SIGNALS:
            window.features[f"{signal}__missing_fraction"] = 0.0
    windows[0].features["speed_kmph__median"] = 0.0
    windows[0].features["coolant_temp_c__missing_fraction"] = 0.25
    result = build_analysis(windows, make_window_pairs(windows), inference)
    assert result.telemetry[0].medians["speed_kmph"] == 0
    assert result.telemetry[0].missing_fractions == {"coolant_temp_c": 0.25}
    assert result.telemetry[1].missing_fractions == {}
    windows[0].features["coolant_temp_c__missing_fraction"] = 1.0
    with pytest.raises(ValueError):
        build_analysis(windows, make_window_pairs(windows), inference)


@pytest.mark.parametrize(
    "bad", ["flag", "error", "threshold", "id", "order", "missing", "features"]
)
def test_aggregation_rejects_mutated_invalid_inputs(genuine, bad):
    windows, pairs, inference = controlled(genuine, [9.0, 10.0])
    if bad == "flag":
        inference.results[0].is_novel = False
    if bad == "error":
        inference.results[0].normalized_signal_errors["engine_rpm"] = float("nan")
    if bad == "threshold":
        inference.results[0].threshold += 1
    if bad == "id":
        inference.results[0].pair_id = "unexpected"
    if bad == "order":
        windows = tuple(reversed(windows))
    if bad == "missing":
        pairs = pairs[:-1]
    if bad == "features":
        pairs = copy.deepcopy(pairs)
        pairs[0].current.features["engine_rpm__median"] += 1
    with pytest.raises((ValueError, ValidationError)):
        build_analysis(windows, pairs, inference)


def test_additive_schema_and_sample_source_contract(harness):
    response = harness.client.post(ANALYZE, headers=AUTH)
    data = response.json()
    assert data["source_type"] == "packaged_sample"
    assert "source" not in data and "sample" in data
    assert data["schema_version"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert (
        SampleAnalysis.model_validate_json(response.content).model_dump(mode="json")
        == data
    )
    assert set(data) >= {
        "model",
        "sample",
        "summary",
        "predictions",
        "score_series",
        "flagged_intervals",
        "telemetry",
        "signals",
        "limitations",
        "persisted",
    }
    schema = harness.client.get("/openapi.json").json()["components"]["schemas"]
    assert "explanation" in schema["SampleAnalysis"]["properties"]
    assert "explanation" in schema["UploadedAnalysis"]["properties"]


def test_explanation_ranks_actual_flagged_errors_only(harness):
    data = harness.client.post(ANALYZE, headers=AUTH).json()
    flagged = [p for p in data["predictions"] if p["is_novel"]]
    maxima = {
        s: max(p["normalized_signal_errors"][s] for p in flagged) for s in SIGNALS
    }
    ranked = sorted(SIGNALS, key=lambda s: -maxima[s])[:3]
    explanation = data["explanation"]
    assert explanation["strongest_signal_deviations"] == [
        {"signal": s, "normalized_error": maxima[s]} for s in ranked
    ]
    assert explanation["signal_scope"] == "flagged_pairs"
    labels = {s["name"]: s["display_name"] for s in data["signals"]}
    assert all(labels[s] in explanation["signal_summary"] for s in ranked)


def test_boundary_windows_remain_clock_time_without_utc(genuine):
    windows = load_sample("kit-20180320-normal").windows[:2]
    windows = tuple(
        replace(w, start_seconds=86380 + i * 10) for i, w in enumerate(windows)
    )
    result = build_analysis(*controlled(genuine, [9.0], windows))
    assert result.flagged_intervals[0].end_seconds == 86400
    assert result.score_series[0].window.start_seconds == 86390
    assert "timezone unknown" in result.time_basis
    assert not any(key in result.model_dump() for key in ("utc", "timestamp"))
