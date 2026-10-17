"""Test battery baseline scope, scoring, alert timing and immutable experiment guards."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/src"))
from nissan_leaf_isolation.core import (
    FEATURES,
    diagnostics,
    fit_forest,
    intervals,
    score_with_evidence,
    temporal_edges,
    thresholds,
    validate_inputs,
)
from nissan_leaf_isolation.pipeline import load_split, verify_preparation
from nissan_leaf_isolation.pipeline import test_once as run_test_once
from nissan_leaf_preparation.core import digest


@pytest.fixture
def small() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(42)
    x = pd.DataFrame(rng.normal(size=(300, 3)), columns=FEATURES).astype("float32")
    meta = pd.DataFrame(
        {
            "source_row": np.arange(300),
            "Timestamp": np.arange(300) * 250000 + 1_600_000_000_000_000,
            "Trip": 1,
            "segment_id": 1,
            "split": "train",
            "battery_blocking_flags": 0,
        }
    )
    return x, meta


@pytest.fixture
def parameters() -> dict:
    return {
        "n_estimators": 30,
        "max_samples": "auto",
        "max_features": 1.0,
        "bootstrap": False,
        "random_state": 42,
        "n_jobs": 1,
        "contamination": "auto",
    }


def test_load_alignment_and_actual_counts(tmp_path: Path, small: tuple) -> None:
    x, meta = small
    x.to_parquet(tmp_path / "features_train.parquet")
    meta.to_parquet(tmp_path / "metadata_train.parquet")
    pd.DataFrame({"Trip": [1], "split": ["train"]}).to_csv(
        tmp_path / "trip_splits.csv", index=False
    )
    prepared = {
        "splits": [{"split": "train", "feature_rows": len(x), "retained_trips": 1}]
    }
    a, b = load_split(tmp_path, prepared, "train")
    pd.testing.assert_frame_equal(a, x)
    pd.testing.assert_frame_equal(b, meta)
    prepared["splits"][0]["feature_rows"] += 1
    with pytest.raises(ValueError, match="counts"):
        load_split(tmp_path, prepared, "train")


@pytest.mark.parametrize(
    "problem",
    [
        "order",
        "dimension",
        "nan",
        "infinity",
        "metadata",
        "split",
        "row",
        "time",
        "quality",
    ],
)
def test_input_rejection(small: tuple, problem: str) -> None:
    x, meta = small
    if problem == "order":
        x = x[FEATURES[::-1]]
    elif problem == "dimension":
        x = x.iloc[:, :2]
    elif problem in ["nan", "infinity"]:
        x.iloc[0, 0] = np.nan if problem == "nan" else np.inf
    elif problem == "metadata":
        meta = meta.iloc[:-1]
    elif problem == "split":
        meta.loc[0, "split"] = "test"
    elif problem == "row":
        meta.loc[1, "source_row"] = 0
    elif problem == "time":
        meta.loc[1, "Timestamp"] = meta.Timestamp.iloc[0]
    else:
        meta.loc[0, "battery_blocking_flags"] = 1
    with pytest.raises(ValueError):
        validate_inputs(x, meta, "train")


def test_training_only_and_deterministic_internal_sampling(
    small: tuple, parameters: dict, tmp_path: Path
) -> None:
    x, meta = small
    first, second = fit_forest(x, meta, parameters), fit_forest(x, meta, parameters)
    for a, b in zip(first.estimators_samples_, second.estimators_samples_, strict=True):
        np.testing.assert_array_equal(a, b)
        assert len(a) == 256 and len(set(a)) == 256
        assert a.min() >= 0 and a.max() < len(x)
    joblib.dump(first, tmp_path / "a")
    joblib.dump(second, tmp_path / "b")
    assert digest(tmp_path / "a") == digest(tmp_path / "b")
    pd.testing.assert_frame_equal(
        score_with_evidence(first, x, 17), score_with_evidence(second, x, 31)
    )
    with pytest.raises(ValueError, match="Split scope"):
        fit_forest(x, meta.assign(split="validation"), parameters)


def test_score_direction_and_explanatory_evidence(
    small: tuple, parameters: dict
) -> None:
    x, meta = small
    model = fit_forest(x, meta, parameters)
    probes = pd.DataFrame([[0.0, 0.0, 0.0], [100.0, 100.0, 100.0]], columns=FEATURES)
    scored = score_with_evidence(model, probes)
    assert scored.score_samples.iloc[1] < scored.score_samples.iloc[0]
    np.testing.assert_array_equal(
        scored.decision_function, model.decision_function(probes)
    )
    assert scored["training_iqr_deviation_SOC"].tolist() == [0.0, 100.0]


def test_threshold_scope_and_ties() -> None:
    scores = np.array([-1.0, -0.5, -0.5, -0.5, -0.1])
    found = thresholds(scores, "train", [0.1])
    assert found["0.1"] == pytest.approx(-0.8)
    assert int((scores < found["0.1"]).sum()) == 1
    for split in ["validation", "test"]:
        with pytest.raises(ValueError, match="training"):
            thresholds(scores, split, [0.1])


def test_irregular_edges_and_trip_gap_isolation() -> None:
    frame = pd.DataFrame(
        {
            "source_row": [0, 1, 2, 3, 4, 5, 6, 8],
            "Timestamp": np.array([0.0, 0.25, 1.0, 1.5, 3.0, 3.25, 3.5, 3.75]) * 1e6,
            "Trip": [1, 1, 1, 2, 2, 2, 2, 2],
            "segment_id": [1, 1, 1, 2, 2, 3, 3, 3],
            "split": "validation",
            "score_samples": -0.8,
        }
    )
    policy = {"max_gap_seconds": 1.0, "minimum_duration_seconds": 0.5}
    np.testing.assert_array_equal(
        temporal_edges(frame, 1.0), [0, 0.25, 0.75, 0, 0, 0, 0.25, 0]
    )
    events = intervals(frame, -0.7, policy)
    assert events.row_count.tolist() == [3, 1, 1, 2, 1]
    assert events.duration_seconds.tolist() == [1.0, 0.0, 0.0, 0.25, 0.0]
    assert events.persistent.sum() == 1
    assert events.row_count.sum() == len(frame)
    assert events.score_min.eq(-0.8).all()
    metrics, _, trips, dates = diagnostics(frame, -0.7, policy)
    assert metrics["recorded_hours"] == pytest.approx(1.25 / 3600)
    assert metrics["trips_with_alerts"] == 1
    assert len(trips) == 2 and len(dates) == 1


def test_unflagged_rows_break_events(small: tuple) -> None:
    _, frame = small
    frame["score_samples"] = -0.8
    frame.loc[2, "score_samples"] = -0.1
    events = intervals(
        frame, -0.7, {"max_gap_seconds": 1.0, "minimum_duration_seconds": 2.0}
    )
    assert len(events) == 2
    assert events.row_count.tolist() == [2, 297]
    empty = intervals(
        frame, -2.0, {"max_gap_seconds": 1.0, "minimum_duration_seconds": 2.0}
    )
    assert empty.empty


def test_test_repeat_and_changed_identity_rejected(tmp_path: Path) -> None:
    (tmp_path / "development.json").write_text(
        json.dumps({"identity": {"code": "frozen"}, "development_outputs": {}})
    )
    with pytest.raises(ValueError, match="changed after freeze"):
        run_test_once({}, tmp_path, {}, {}, tmp_path, {"code": "new"})
    (tmp_path / "test_started.json").write_text("{}")
    with pytest.raises(ValueError, match="already started"):
        run_test_once({}, tmp_path, {}, {}, tmp_path, {"code": "frozen"})


def test_preparation_preserved() -> None:
    config = json.loads(
        (
            ROOT / "ml/notebooks/nissan_leaf_2018/config/isolation_forest.json"
        ).read_text()
    )
    directory, prepared, hashes = verify_preparation(config)
    assert prepared["config"]["features"] == FEATURES
    assert directory.name == config["preparation_run_id"]
    assert len(hashes) > len(prepared["outputs"])


def test_completed_report_accounting_if_present() -> None:
    base = ROOT / "ml/reports/nissan_leaf_2018/tables/isolation_forest"
    if not base.exists():
        pytest.skip("Full experiment not run yet")
    for summary in base.glob("*/experiment_summary.json"):
        data = json.loads(summary.read_text())
        dev = data["development"]
        assert dev["fit_rows"] == dev["results"]["train"]["scored_rows"]
        assert dev["reproducibility"]["same_seed_model_bytes"]
        for metrics in [*dev["results"].values(), data["test"]["results"]]:
            assert metrics["flagged_rows"] <= metrics["scored_rows"]
            assert (
                metrics["persistent_alert_intervals"]
                + metrics["point_or_short_intervals"]
                == metrics["all_candidate_intervals"]
            )
