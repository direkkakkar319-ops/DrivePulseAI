"""Compare simple Oxford capacity-trend methods against the proxy RUL target.

Selection uses earlier within-cell origins; later origins are a temporal
holdout. Because only two cells have unconfirmed first-crossing labels, this
experiment is method development, not cell-generalization validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import TheilSenRegressor

from older_models.oxford.models.rul_regressor import ExponentialCapacityTrendRUL

ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = (
    ROOT / "older_models/oxford/data/oxford_battery_degradation/v1/processed/"
    "cell_cycle_features.csv"
)
REPORT_PATH = ROOT / "older_models/oxford/models/oxford_rul_method_comparison.json"
RUL_COLUMN = "rul_drive_cycles_threshold_derived"
LOOKBACKS = (500, 1000, 2000, None)
FAMILIES = ("ols", "theil_sen", "weighted_ols", "exponential")
MIN_OBSERVATIONS = 4
DEVELOPMENT_FRACTION = 0.60
MIN_SELECTION_COVERAGE = 0.75


def estimate_rul(history: pd.DataFrame, threshold: float, family: str) -> float | None:
    """Project the observed capacity slope to threshold using past data only."""
    if len(history) < MIN_OBSERVATIONS:
        return None
    cycle = history["characterization_cycle"].to_numpy(dtype=float)
    capacity = history["capacity_1c_discharge_mah"].to_numpy(dtype=float)
    current_cycle = cycle[-1]
    current_capacity = capacity[-1]
    x = cycle - current_cycle

    if family == "theil_sen":
        model = TheilSenRegressor(random_state=42)
        model.fit(x.reshape(-1, 1), capacity)
        slope = float(model.coef_[0])
        if slope >= 0:
            return None
        return float((current_capacity - threshold) / -slope)

    if family == "exponential":
        model = ExponentialCapacityTrendRUL(
            lookback_cycles=max(1, int(current_cycle - cycle[0]))
        )
        result = model.estimate(history, int(current_cycle))
        return result["rul_cycles"]

    weights = None
    if family == "weighted_ols":
        ages = current_cycle - cycle
        weights = np.sqrt(np.exp(-np.log(2.0) * ages / 1000.0))
    elif family != "ols":
        raise ValueError(f"unknown trend family: {family}")

    slope = float(np.polyfit(x, capacity, deg=1, w=weights)[0])
    if slope >= 0:
        return None
    return float((current_capacity - threshold) / -slope)


def error_metrics(rows: list[dict], penalty_missing: bool = False) -> dict:
    """Summarize errors; optional missed origins count as zero-RUL predictions."""
    if not rows:
        return {"origins": 0, "mae_cycles": None, "rmse_cycles": None}
    errors = []
    for row in rows:
        prediction = row.get("predicted_rul_cycles")
        if prediction is None and penalty_missing:
            prediction = 0.0
        if prediction is not None:
            errors.append(prediction - row["observed_rul_cycles"])
    if not errors:
        return {"origins": 0, "mae_cycles": None, "rmse_cycles": None}
    values = np.asarray(errors, dtype=float)
    return {
        "scored_origins": len(values),
        "mae_cycles": float(np.mean(np.abs(values))),
        "rmse_cycles": float(np.sqrt(np.mean(np.square(values)))),
        "median_absolute_error_cycles": float(np.median(np.abs(values))),
        "mean_error_cycles": float(np.mean(values)),
    }


def candidate_name(family: str, lookback: int | None) -> str:
    return f"{family}_lookback_{lookback or 'all'}"


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(
            f"Oxford processed table missing at {DATA_PATH}; "
            "run ml/scripts/preprocess_oxford_battery.py first"
        )
    frame = pd.read_csv(DATA_PATH)
    predictions: dict[str, list[dict]] = {}
    cell_summary = {}

    for cell_id, cell in frame.groupby("cell_id", sort=True):
        cell = cell.sort_values("characterization_cycle").reset_index(drop=True)
        crossing_rows = cell.loc[cell[RUL_COLUMN].notna()]
        if crossing_rows.empty:
            cell_summary[cell_id] = {"status": "right_censored", "origins": 0}
            continue
        crossing_cycle = int(
            cell.loc[
                cell["capacity_1c_discharge_mah"] <= cell["eol_threshold_capacity_mah"],
                "characterization_cycle",
            ].iloc[0]
        )
        threshold = float(cell["eol_threshold_capacity_mah"].iloc[0])
        cell_origins = 0
        eligible_origins = cell.loc[
            cell["characterization_cycle"] < crossing_cycle,
            "characterization_cycle",
        ].iloc[MIN_OBSERVATIONS - 1 :]
        for as_of in eligible_origins:
            history_all = cell.loc[cell["characterization_cycle"] <= as_of]
            observed_rul = float(crossing_cycle - as_of)
            split = (
                "development"
                if as_of / crossing_cycle <= DEVELOPMENT_FRACTION
                else "temporal_holdout"
            )
            cell_origins += 1
            for family in FAMILIES:
                for lookback in LOOKBACKS:
                    history = history_all
                    if lookback is not None:
                        history = history.loc[
                            history["characterization_cycle"] >= as_of - lookback
                        ]
                    pred = estimate_rul(history, threshold, family)
                    key = candidate_name(family, lookback)
                    predictions.setdefault(key, []).append(
                        {
                            "cell_id": cell_id,
                            "as_of_cycle": int(as_of),
                            "split": split,
                            "observed_rul_cycles": observed_rul,
                            "predicted_rul_cycles": pred,
                        }
                    )
        cell_summary[cell_id] = {
            "status": "first_crossing_proxy_only",
            "crossing_cycle": crossing_cycle,
            "candidate_origins": cell_origins,
        }

    candidate_results = {}
    for key, rows in predictions.items():
        dev = [row for row in rows if row["split"] == "development"]
        holdout = [row for row in rows if row["split"] == "temporal_holdout"]
        predictions_available = [
            row for row in dev if row["predicted_rul_cycles"] is not None
        ]
        coverage = len(predictions_available) / len(dev) if dev else 0.0
        per_cell_selection = []
        for cell_id in sorted({row["cell_id"] for row in dev}):
            cell_rows = [row for row in dev if row["cell_id"] == cell_id]
            metrics = error_metrics(cell_rows, penalty_missing=True)
            if metrics.get("mae_cycles") is not None:
                per_cell_selection.append(metrics["mae_cycles"])
        candidate_results[key] = {
            "family": key.rsplit("_lookback_", 1)[0],
            "lookback_cycles": key.rsplit("_lookback_", 1)[1],
            "development_coverage": coverage,
            "selection_score_macro_cell_mae_cycles": (
                float(np.mean(per_cell_selection)) if per_cell_selection else None
            ),
            "development_metrics": error_metrics(dev, penalty_missing=True),
            "temporal_holdout_coverage": (
                sum(row["predicted_rul_cycles"] is not None for row in holdout)
                / len(holdout)
                if holdout
                else 0.0
            ),
            "temporal_holdout_metrics": error_metrics(holdout),
            "temporal_holdout_by_cell": {
                cell_id: error_metrics(
                    [row for row in holdout if row["cell_id"] == cell_id]
                )
                for cell_id in sorted({row["cell_id"] for row in holdout})
            },
        }

    eligible = {
        name: result
        for name, result in candidate_results.items()
        if result["development_coverage"] >= MIN_SELECTION_COVERAGE
        and result["selection_score_macro_cell_mae_cycles"] is not None
    }
    if not eligible:
        raise RuntimeError("no method met the development coverage requirement")
    selected = min(
        eligible,
        key=lambda name: eligible[name]["selection_score_macro_cell_mae_cycles"],
    )

    report = {
        "dataset": "Oxford Battery Degradation Dataset 1",
        "source_doi": "10.5287/bodleian:KO2kdmYGg",
        "target": "unconfirmed first-observed 75% capacity crossing proxy",
        "protocol": {
            "development_cutoffs": f"as_of_cycle / proxy_crossing_cycle <= {DEVELOPMENT_FRACTION}",
            "holdout_cutoffs": f"as_of_cycle / proxy_crossing_cycle > {DEVELOPMENT_FRACTION}",
            "minimum_history_observations": MIN_OBSERVATIONS,
            "selection_metric": "mean of per-cell development MAE, missing predictions penalized as zero RUL",
            "minimum_development_coverage": MIN_SELECTION_COVERAGE,
            "predictions_use_future_features": False,
            "holdout_is_cell_disjoint": False,
        },
        "cells": cell_summary,
        "selected_method": selected,
        "selected_method_reason": "lowest macro-cell development MAE among methods with at least 75% development coverage",
        "selected_temporal_holdout": candidate_results[selected][
            "temporal_holdout_metrics"
        ],
        "selected_temporal_holdout_by_cell": candidate_results[selected][
            "temporal_holdout_by_cell"
        ],
        "candidates": candidate_results,
        "limitations": [
            "All candidate metrics use the unconfirmed first-crossing proxy, not confirmed EOL labels.",
            "Only two cells provide proxy crossings; temporal holdout origins are not independent cells.",
            "The two-reading 75% screen confirms no EOL events in this release.",
            "Selection/holdout measure within-cell temporal behavior only and do not establish new-cell generalization.",
            "No passenger-EV field-RUL or service-life claim is supported.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
