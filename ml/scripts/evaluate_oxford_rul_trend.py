"""Run a rolling-origin Oxford RUL baseline backtest without cross-cell claims.

Run from the repository root with
``python3 -m ml.scripts.evaluate_oxford_rul_trend``. It evaluates a Theil-Sen
capacity-trend extrapolator against the exploratory first-crossing target.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.src.models.rul_regressor import TheilSenCapacityTrendRUL

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = (
    ROOT / "data/automotive_prognostics/oxford_battery_degradation/v1/processed/"
    "cell_cycle_features.csv"
)
OUTPUT_PATH = ROOT / "ml/reports/modeling/oxford_rul_trend_baseline.json"
RUL_COLUMN = "rul_drive_cycles_threshold_derived"


def error_summary(rows: list[dict]) -> dict:
    """Summarize rolling-origin errors without treating origins as independent cells."""
    if not rows:
        return {"origins": 0, "mae_cycles": None, "rmse_cycles": None}
    errors = np.array(
        [row["predicted_rul_cycles"] - row["observed_rul_cycles"] for row in rows],
        dtype=float,
    )
    return {
        "origins": len(rows),
        "mae_cycles": float(np.mean(np.abs(errors))),
        "rmse_cycles": float(np.sqrt(np.mean(np.square(errors)))),
        "median_absolute_error_cycles": float(np.median(np.abs(errors))),
        "mean_error_cycles": float(np.mean(errors)),
    }


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(
            f"Oxford processed table not found at {DATA_PATH}; "
            "run ml/scripts/preprocess_oxford_battery.py first"
        )
    data = pd.read_csv(DATA_PATH)
    model = TheilSenCapacityTrendRUL(
        lookback_cycles=1000, min_observations=4, random_state=42
    )
    per_cell = {}
    all_predictions = []
    for cell_id, cell in data.groupby("cell_id", sort=True):
        cell = cell.sort_values("characterization_cycle").reset_index(drop=True)
        threshold = cell["eol_threshold_capacity_mah"].iloc[0]
        crossing = cell.loc[
            cell["capacity_1c_discharge_mah"] <= threshold,
            "characterization_cycle",
        ]
        if crossing.empty:
            per_cell[cell_id] = {
                "status": "right_censored_at_75_percent_threshold",
                "usable_rolling_origins": 0,
            }
            continue

        crossing_cycle = int(crossing.iloc[0])
        rows = []
        skipped = {}
        for as_of_cycle in cell.loc[
            cell["characterization_cycle"] < crossing_cycle,
            "characterization_cycle",
        ]:
            estimate = model.estimate(cell, int(as_of_cycle))
            if estimate.get("rul_cycles") is None:
                status = estimate["status"]
                skipped[status] = skipped.get(status, 0) + 1
                continue
            observed_rul = float(crossing_cycle - as_of_cycle)
            result = {
                "cell_id": cell_id,
                "as_of_cycle": int(as_of_cycle),
                "observed_rul_cycles": observed_rul,
                "predicted_rul_cycles": estimate["rul_cycles"],
                "capacity_slope_mah_per_cycle": estimate[
                    "capacity_slope_mah_per_cycle"
                ],
                "observations_used": estimate["observations_used"],
            }
            rows.append(result)
            all_predictions.append(result)

        per_cell[cell_id] = {
            "status": "first_observed_threshold_crossing",
            "crossing_cycle": crossing_cycle,
            "threshold_capacity_mah": float(threshold),
            "rolling_origin_metrics": error_summary(rows),
            "skipped_origins_by_reason": skipped,
            "latest_predictions": rows[-5:],
        }

    report = {
        "dataset": "Oxford Battery Degradation Dataset 1",
        "source_doi": "10.5287/bodleian:KO2kdmYGg",
        "method": "Theil-Sen local linear trend extrapolation of measured 1C discharge capacity",
        "target_definition": "cycles remaining to the first observed characterization at or below 75% of each cell's first measured capacity",
        "lookback_cycles": model.lookback_cycles,
        "minimum_observations": model.min_observations,
        "prediction_origins_are_independent": False,
        "pooled_rolling_origin_metrics": error_summary(all_predictions),
        "per_cell": per_cell,
        "limitations": [
            "75% is an exploratory threshold, not an Oxford-defined EOL rule.",
            "Cell2's first below-threshold measurement rebounds above threshold in the next two records.",
            "Cell5 crosses only at the final record and has no post-crossing confirmation.",
            "Only two cells have first-crossing targets; six are right-censored.",
            "Rolling origins from the same cell are correlated and do not measure generalization to a new cell.",
            "No meaningful cell-disjoint train/validation/test evaluation is available.",
            "This lab-cell baseline does not support passenger-EV fleet RUL claims.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
