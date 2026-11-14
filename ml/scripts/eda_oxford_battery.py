"""Audit the Oxford cell-cycle preprocessing output for RUL method development.

Run from the repository root with ``python3 ml/scripts/eda_oxford_battery.py``.
This reports target coverage and trajectory properties; it does not train a model.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = (
    ROOT / "data/automotive_prognostics/oxford_battery_degradation/v1/processed/"
    "cell_cycle_features.csv"
)
REPORT_PATH = ROOT / "ml/reports/eda/oxford_battery_eda.json"
RUL_COLUMN = "rul_drive_cycles_threshold_derived"


def audit_cell(cell_id: str, rows: pd.DataFrame) -> dict:
    """Summarize one cell's observed capacity trajectory and derived RUL labels."""
    rows = rows.sort_values("characterization_cycle")
    cycles = rows["characterization_cycle"].to_numpy(dtype=float)
    capacity = rows["capacity_1c_discharge_mah"].to_numpy(dtype=float)
    soh = rows["soh_relative_to_first_capacity"].to_numpy(dtype=float)
    gaps = np.diff(cycles)
    increases = np.diff(capacity)
    crossing_rows = rows.loc[
        rows["capacity_1c_discharge_mah"] <= rows["eol_threshold_capacity_mah"]
    ]
    crossing_cycle = (
        None
        if crossing_rows.empty
        else int(crossing_rows.iloc[0]["characterization_cycle"])
    )
    crossing_row = crossing_rows.iloc[0] if not crossing_rows.empty else None
    post_crossing = (
        rows.loc[rows["characterization_cycle"] > crossing_cycle]
        if crossing_cycle is not None
        else rows.iloc[0:0]
    )
    from_crossing = (
        rows.loc[rows["characterization_cycle"] >= crossing_cycle]
        if crossing_cycle is not None
        else rows.iloc[0:0]
    )
    below_at_start = (
        from_crossing["capacity_1c_discharge_mah"].to_numpy()
        <= from_crossing["eol_threshold_capacity_mah"].to_numpy()
    )
    consecutive_below = 0
    for is_below in below_at_start:
        if not is_below:
            break
        consecutive_below += 1
    rul = rows[RUL_COLUMN].dropna().to_numpy(dtype=float)
    positive_increases = increases[increases > 0]
    return {
        "cell_id": cell_id,
        "records": len(rows),
        "first_cycle": int(cycles[0]),
        "last_cycle": int(cycles[-1]),
        "median_cycle_gap": float(np.median(gaps)) if len(gaps) else None,
        "min_cycle_gap": float(np.min(gaps)) if len(gaps) else None,
        "max_cycle_gap": float(np.max(gaps)) if len(gaps) else None,
        "gaps_over_100_cycles": int(np.count_nonzero(gaps > 100)),
        "baseline_capacity_mah": float(capacity[0]),
        "last_capacity_mah": float(capacity[-1]),
        "last_soh": float(soh[-1]),
        "minimum_soh": float(np.min(soh)),
        "capacity_increases_between_records": int(np.count_nonzero(increases > 0)),
        "largest_capacity_increase_mah": (
            float(np.max(positive_increases)) if len(positive_increases) else 0.0
        ),
        "eol_threshold_fraction": float(rows["eol_threshold_fraction"].iloc[0]),
        "first_observed_threshold_crossing_cycle": crossing_cycle,
        "first_crossing_capacity_mah": (
            float(crossing_row["capacity_1c_discharge_mah"])
            if crossing_row is not None
            else None
        ),
        "first_crossing_soh": (
            float(crossing_row["soh_relative_to_first_capacity"])
            if crossing_row is not None
            else None
        ),
        "post_crossing_records": len(post_crossing),
        "post_crossing_records_above_threshold": int(
            np.count_nonzero(
                post_crossing["capacity_1c_discharge_mah"].to_numpy()
                > post_crossing["eol_threshold_capacity_mah"].to_numpy()
            )
        ),
        "post_crossing_soh_values": [
            float(value) for value in post_crossing["soh_relative_to_first_capacity"]
        ],
        "consecutive_below_threshold_records_from_first_crossing": consecutive_below,
        "crossing_recovered_above_threshold": bool(
            not post_crossing.empty
            and (
                post_crossing["capacity_1c_discharge_mah"]
                > post_crossing["eol_threshold_capacity_mah"]
            ).any()
        ),
        "right_censored": crossing_cycle is None,
        "rows_with_derived_rul": len(rul),
        "derived_rul_min_cycles": float(np.min(rul)) if len(rul) else None,
        "derived_rul_max_cycles": float(np.max(rul)) if len(rul) else None,
        "derived_rul_median_cycles": float(np.median(rul)) if len(rul) else None,
    }


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(
            f"Oxford processed table not found at {DATA_PATH}; "
            "run ml/scripts/preprocess_oxford_battery.py first"
        )
    frame = pd.read_csv(DATA_PATH)
    required = {
        "cell_id",
        "characterization_cycle",
        "capacity_1c_discharge_mah",
        "soh_relative_to_first_capacity",
        "eol_threshold_fraction",
        "eol_threshold_capacity_mah",
        RUL_COLUMN,
        "right_censored_at_last_observation",
    }
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise ValueError(f"processed table lacks required columns: {missing_columns}")
    if frame[["cell_id", "characterization_cycle"]].duplicated().any():
        raise ValueError("duplicate cell/cycle rows found")

    cells = [audit_cell(cell_id, rows) for cell_id, rows in frame.groupby("cell_id")]
    events = [cell for cell in cells if not cell["right_censored"]]
    censored = [cell for cell in cells if cell["right_censored"]]
    numeric = frame.select_dtypes(include=[np.number])
    report = {
        "dataset": "Oxford Battery Degradation Dataset 1",
        "source_doi": "10.5287/bodleian:KO2kdmYGg",
        "input": str(DATA_PATH.relative_to(ROOT)),
        "rows": len(frame),
        "cells": int(frame["cell_id"].nunique()),
        "duplicate_cell_cycle_rows": 0,
        "missing_numeric_values_by_column": {
            name: int(count)
            for name, count in numeric.isna().sum().items()
            if count > 0
        },
        "threshold_fraction": float(frame["eol_threshold_fraction"].iloc[0]),
        "cells_with_observed_threshold_crossing": [cell["cell_id"] for cell in events],
        "right_censored_cells": [cell["cell_id"] for cell in censored],
        "rows_with_observed_threshold_rul": int(frame[RUL_COLUMN].notna().sum()),
        "cells_with_two_consecutive_below_threshold_records": [
            cell["cell_id"]
            for cell in cells
            if cell["consecutive_below_threshold_records_from_first_crossing"] >= 2
        ],
        "total_characterization_cycles": {
            "minimum": int(frame["characterization_cycle"].min()),
            "maximum": int(frame["characterization_cycle"].max()),
        },
        "cell_audit": cells,
        "interpretation": [
            "The 75% capacity threshold is an exploratory convention, not an Oxford-provided EOL definition.",
            "A crossing is observed only at characterization checkpoints; the exact crossing time between checkpoints is unknown.",
            "Only two cells cross the chosen threshold, while six are right-censored.",
            "Rows within a cell are repeated observations and must not be randomly split across train and evaluation.",
            "A cell-disjoint RUL train/validation/test evaluation is unsupported with only two event cells.",
            "No model was trained by this EDA script.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
