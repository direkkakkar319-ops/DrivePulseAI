"""Validate inputs, fit training-only forests and aggregate timestamp-aware alerts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["HV_Bat_Voltage", "Pack_1_C_Temp", "SOC"]


def validate_inputs(features: pd.DataFrame, metadata: pd.DataFrame, split: str) -> None:
    """Reject schema, lineage and chronological violations before scoring."""
    if features.columns.tolist() != FEATURES or features.shape[1] != 3:
        raise ValueError("Exact feature order required")
    if not np.isfinite(features.to_numpy()).all():
        raise ValueError("Nonfinite input")
    if len(features) != len(metadata) or len(features) == 0:
        raise ValueError("Feature/metadata dimensions")
    if not metadata.split.eq(split).all():
        raise ValueError("Split scope")
    if (
        metadata.source_row.duplicated().any()
        or not metadata.source_row.is_monotonic_increasing
    ):
        raise ValueError("Source lineage")
    if (
        not metadata.Timestamp.is_monotonic_increasing
        or metadata.Timestamp.duplicated().any()
    ):
        raise ValueError("Timestamp ordering")
    if metadata.battery_blocking_flags.ne(0).any():
        raise ValueError("Battery eligibility")


def fit_forest(
    features: pd.DataFrame, metadata: pd.DataFrame, parameters: dict
) -> IsolationForest:
    """Use every retained training observation; never accept held-out rows."""
    validate_inputs(features, metadata, "train")
    return IsolationForest(**parameters).fit(features)


def score_with_evidence(
    model: IsolationForest, features: pd.DataFrame, batch: int = 100000
) -> pd.DataFrame:
    """Return scores with training-IQR deviations, not causal attributions."""
    if (
        features.columns.tolist() != FEATURES
        or not np.isfinite(features.to_numpy()).all()
    ):
        raise ValueError("Invalid scoring features")
    scores = np.concatenate(
        [
            model.score_samples(features.iloc[start : start + batch])
            for start in range(0, len(features), batch)
        ]
    )
    out = pd.DataFrame(
        {"score_samples": scores, "decision_function": scores - model.offset_}
    )
    # Inputs already are deviations from frozen training medians in IQR units.
    # These explain observed feature extremeness, not isolation-tree contributions.
    for name in FEATURES:
        out[f"training_iqr_deviation_{name}"] = features[name].to_numpy()
    return out


def thresholds(scores: np.ndarray, split: str, budgets: list[float]) -> dict:
    """Training quantiles define operational budgets, never fault prevalence."""
    if split != "train":
        raise ValueError("Thresholds require training scores")
    if not np.isfinite(scores).all() or not all(0 < q < 0.5 for q in budgets):
        raise ValueError("Invalid threshold inputs")
    return {str(q): float(np.quantile(scores, q)) for q in budgets}


def temporal_edges(frame: pd.DataFrame, gap: float) -> np.ndarray:
    """Seconds covered by adjacent eligible source rows; no extrapolated time."""
    delta = frame.Timestamp.diff().to_numpy() / 1e6
    safe = (
        frame.Trip.eq(frame.Trip.shift())
        & frame.segment_id.eq(frame.segment_id.shift())
        & frame.source_row.diff().eq(1)
        & pd.Series(delta, index=frame.index).gt(0)
        & pd.Series(delta, index=frame.index).le(gap)
    ).to_numpy()
    return np.where(safe, delta, 0.0)


def intervals(frame: pd.DataFrame, threshold: float, policy: dict) -> pd.DataFrame:
    """Group consecutive flagged observations; retain short events as point candidates."""
    flagged = frame.score_samples.to_numpy() < threshold
    safe = temporal_edges(frame, policy["max_gap_seconds"]) > 0
    previous = np.r_[False, flagged[:-1]]
    group = np.cumsum(~(safe & previous & flagged))
    points = frame.loc[flagged].copy()
    points["event"] = group[flagged]
    out = (
        points.groupby("event", sort=True)
        .agg(
            Trip=("Trip", "first"),
            segment_id=("segment_id", "first"),
            split=("split", "first"),
            start_us=("Timestamp", "first"),
            end_us=("Timestamp", "last"),
            start_row=("source_row", "first"),
            end_row=("source_row", "last"),
            row_count=("source_row", "size"),
            score_min=("score_samples", "min"),
            score_mean=("score_samples", "mean"),
            score_max=("score_samples", "max"),
        )
        .reset_index(drop=True)
    )
    out["duration_seconds"] = (out.end_us - out.start_us) / 1e6
    out["persistent"] = out.duration_seconds.ge(policy["minimum_duration_seconds"])
    out["start_utc"] = pd.to_datetime(out.start_us, unit="us", utc=True)
    out["end_utc"] = pd.to_datetime(out.end_us, unit="us", utc=True)
    return out


def diagnostics(
    frame: pd.DataFrame, threshold: float, policy: dict
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Describe alert volume using eligible observed time, never fault metrics."""
    frame = frame.copy()
    frame["flagged"] = frame.score_samples.lt(threshold)
    frame["recorded_seconds"] = temporal_edges(frame, policy["max_gap_seconds"])
    frame["date"] = pd.to_datetime(frame.Timestamp, unit="us", utc=True).dt.strftime(
        "%Y-%m-%d"
    )
    events = intervals(frame, threshold, policy)
    persistent = events[events.persistent]
    tables = []
    for key in ["Trip", "date"]:
        table = frame.groupby(key).agg(
            rows=("source_row", "size"),
            flagged=("flagged", "sum"),
            recorded_seconds=("recorded_seconds", "sum"),
            score_median=("score_samples", "median"),
            score_min=("score_samples", "min"),
        )
        counts = persistent.groupby(
            "Trip" if key == "Trip" else persistent.start_utc.dt.strftime("%Y-%m-%d")
        ).size()
        table["alert_intervals"] = counts.reindex(table.index, fill_value=0)
        table["flagged_pct"] = 100 * table.flagged / table.rows
        table["alerts_per_recorded_hour"] = table.alert_intervals / (
            table.recorded_seconds / 3600
        ).replace(0, np.nan)
        tables.append(table.reset_index())
    hours = float(frame.recorded_seconds.sum() / 3600)
    trips = frame.Trip.nunique()
    result = {
        "scored_rows": len(frame),
        "flagged_rows": int(frame.flagged.sum()),
        "flagged_pct": float(100 * frame.flagged.mean()),
        "all_candidate_intervals": len(events),
        "persistent_alert_intervals": len(persistent),
        "point_or_short_intervals": int((~events.persistent).sum()),
        "recorded_hours": hours,
        "alerts_per_recorded_hour": len(persistent) / hours if hours else None,
        "trips": int(trips),
        "trips_with_alerts": int(persistent.Trip.nunique()),
        "trips_with_alerts_pct": float(100 * persistent.Trip.nunique() / trips),
        "alerts_per_trip": len(persistent) / trips,
        "score_quantiles": {
            str(q): float(frame.score_samples.quantile(q))
            for q in [0, 0.001, 0.005, 0.01, 0.25, 0.5, 0.75, 0.99, 1]
        },
    }
    return result, events, tables[0], tables[1]
