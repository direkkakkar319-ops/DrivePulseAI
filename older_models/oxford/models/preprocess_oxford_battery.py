"""Extract cell-level Oxford capacity/SOH and exploratory threshold-RUL rows.

Run from the repository root with ``python3 ml/scripts/preprocess_oxford_battery.py``.
Outputs are local-only; this small eight-cell laboratory dataset is not a fleet
training benchmark. The threshold-derived RUL column is explicitly censored.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[3]
RAW_FILE = (
    ROOT / "older_models/oxford/data/oxford_battery_degradation/v1/raw/"
    "Oxford_Battery_Degradation_Dataset_1.mat"
)
OUTPUT_DIR = ROOT / "older_models/oxford/data/oxford_battery_degradation/v1/processed"
EOL_FRACTION = 0.75
EOL_CONFIRMATION_RECORDS = 2
CYCLE_PATTERN = re.compile(r"^cyc(\d+)$")


def generated_ev_context(cell_id: str, cycle: int) -> dict[str, float]:
    """Create deterministic EV-operating-context columns for prototyping.

    Oxford Dataset 1 contains controlled cell characterization data, not vehicle
    telemetry.  These values are generated scenario inputs that make the local
    table compatible with multivariate EV-model experiments; they are not source
    measurements and must not be used for real-world performance claims.
    """
    cell_number = int(cell_id.removeprefix("Cell"))
    phase = cell_number * 0.71
    seasonal = math.sin((2 * math.pi * cycle / 2400) + phase)
    daily = math.sin((2 * math.pi * cycle / 340) + (phase * 1.7))

    ambient_temperature_c = 16.0 + (7.5 * seasonal) + (1.5 * daily)
    average_speed_kph = 43.0 + (8.0 * math.sin((2 * math.pi * cycle / 900) + phase))
    energy_consumption_wh_per_km = (
        157.0
        + (1.7 * max(ambient_temperature_c - 20.0, 0.0))
        + (2.3 * max(15.0 - ambient_temperature_c, 0.0))
        + (0.55 * (average_speed_kph - 43.0))
    )
    dc_fast_charge_share_pct = 14.0 + (
        9.0 * math.sin((2 * math.pi * cycle / 1500) + phase)
    )
    charge_power_kw = 7.2 + (0.35 * dc_fast_charge_share_pct)
    state_of_charge_pct = 62.0 + (18.0 * math.sin((2 * math.pi * cycle / 470) + phase))
    pack_temperature_c = ambient_temperature_c + 9.0 + (0.045 * average_speed_kph)
    estimated_odometer_km = cycle * (30.0 + (cell_number * 0.8))

    return {
        "ambient_temperature_c": round(ambient_temperature_c, 3),
        "battery_pack_temperature_c": round(pack_temperature_c, 3),
        "state_of_charge_pct": round(state_of_charge_pct, 3),
        "average_speed_kph": round(average_speed_kph, 3),
        "energy_consumption_wh_per_km": round(energy_consumption_wh_per_km, 3),
        "dc_fast_charge_share_pct": round(dc_fast_charge_share_pct, 3),
        "charge_power_kw": round(charge_power_kw, 3),
        "estimated_odometer_km": round(estimated_odometer_km, 3),
    }


def curve_summary(curve) -> dict[str, float]:
    """Summarize the measured 1C discharge curve without using charge as a feature."""
    voltage = np.asarray(curve.v, dtype=float).reshape(-1)
    temperature = np.asarray(curve.T, dtype=float).reshape(-1)
    time_days = np.asarray(curve.t, dtype=float).reshape(-1)
    charge = np.asarray(curve.q, dtype=float).reshape(-1)
    if not (len(voltage) == len(temperature) == len(time_days) == len(charge)):
        raise ValueError("Oxford C1dc vectors have inconsistent lengths")
    if not len(voltage) or not np.isfinite(voltage).all():
        raise ValueError("Oxford C1dc contains empty or non-finite voltage data")
    if not np.isfinite(temperature).all() or not np.isfinite(time_days).all():
        raise ValueError("Oxford C1dc contains non-finite time or temperature data")
    capacity = abs(float(charge[-1] - charge[0]))
    if not np.isfinite(capacity) or capacity <= 0:
        raise ValueError("Oxford C1dc has invalid integrated discharge capacity")
    elapsed_seconds = float((time_days[-1] - time_days[0]) * 86400)
    quantiles = np.quantile(voltage, [0.1, 0.5, 0.9])
    return {
        "capacity_1c_discharge_mah": capacity,
        "discharge_duration_seconds": elapsed_seconds,
        "voltage_min_v": float(np.min(voltage)),
        "voltage_p10_v": float(quantiles[0]),
        "voltage_median_v": float(quantiles[1]),
        "voltage_p90_v": float(quantiles[2]),
        "voltage_max_v": float(np.max(voltage)),
        "temperature_mean_c": float(np.mean(temperature)),
        "temperature_max_c": float(np.max(temperature)),
    }


def build_rows(mat: dict) -> tuple[list[dict], dict]:
    rows = []
    cell_audit = {}
    for cell_id in sorted(key for key in mat if re.fullmatch(r"Cell\d+", key)):
        cell = mat[cell_id]
        observations = []
        for field in cell._fieldnames:
            match = CYCLE_PATTERN.fullmatch(field)
            if match is None:
                continue
            cycle = int(match.group(1))
            record = getattr(cell, field)
            if not hasattr(record, "C1dc"):
                raise ValueError(f"{cell_id}.{field} has no C1dc characterization")
            observations.append((cycle, curve_summary(record.C1dc)))
        observations.sort(key=lambda item: item[0])
        if not observations:
            raise ValueError(f"No cycle observations found for {cell_id}")

        baseline = observations[0][1]["capacity_1c_discharge_mah"]
        threshold = baseline * EOL_FRACTION
        crossing = next(
            (
                cycle
                for cycle, values in observations
                if values["capacity_1c_discharge_mah"] <= threshold
            ),
            None,
        )
        persistent_crossing_index = next(
            (
                index
                for index in range(len(observations) - EOL_CONFIRMATION_RECORDS + 1)
                if all(
                    values["capacity_1c_discharge_mah"] <= threshold
                    for _, values in observations[
                        index : index + EOL_CONFIRMATION_RECORDS
                    ]
                )
            ),
            None,
        )
        persistent_crossing = (
            observations[persistent_crossing_index][0]
            if persistent_crossing_index is not None
            else None
        )
        for cycle, values in observations:
            rul = (
                crossing - cycle if crossing is not None and cycle <= crossing else None
            )
            persistent_rul = (
                persistent_crossing - cycle
                if persistent_crossing is not None and cycle <= persistent_crossing
                else None
            )
            rows.append(
                {
                    "cell_id": cell_id,
                    "characterization_cycle": cycle,
                    **values,
                    **generated_ev_context(cell_id, cycle),
                    "soh_relative_to_first_capacity": (
                        values["capacity_1c_discharge_mah"] / baseline
                    ),
                    "eol_threshold_fraction": EOL_FRACTION,
                    "eol_threshold_capacity_mah": threshold,
                    "rul_drive_cycles_threshold_derived": rul,
                    "rul_observed_under_threshold": crossing is not None,
                    "rul_drive_cycles_persistent_75pct": persistent_rul,
                    "persistent_eol_confirmed": persistent_crossing is not None,
                    "right_censored_at_last_observation": crossing is None,
                }
            )
        cell_audit[cell_id] = {
            "characterization_records": len(observations),
            "first_cycle": observations[0][0],
            "last_cycle": observations[-1][0],
            "baseline_capacity_mah": baseline,
            "eol_threshold_capacity_mah": threshold,
            "first_threshold_crossing_cycle": crossing,
            "persistent_threshold_event_cycle": persistent_crossing,
            "persistent_threshold_confirmed": persistent_crossing is not None,
            "right_censored": crossing is None,
        }
    return rows, cell_audit


def main() -> None:
    if not RAW_FILE.is_file():
        raise FileNotFoundError(f"Oxford source file is missing: {RAW_FILE}")
    mat = loadmat(RAW_FILE, squeeze_me=True, struct_as_record=False)
    rows, cell_audit = build_rows(mat)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "cell_cycle_features.csv"
    with output_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "dataset": "Oxford Battery Degradation Dataset 1",
        "source_doi": "10.5287/bodleian:KO2kdmYGg",
        "source_citation": (
            "Christoph R. Birkl, Diagnosis and Prognosis of Degradation in "
            "Lithium-Ion Batteries, University of Oxford PhD thesis, 2017"
        ),
        "derived_targets": {
            "soh": "1C discharge capacity divided by each cell's first recorded 1C discharge capacity",
            "rul": (
                f"characterization cycle minus first observed cycle at or below "
                f"{EOL_FRACTION:.0%} of baseline capacity; cycle units are drive cycles"
            ),
            "rul_persistent_screen": (
                f"cycle distance to the first of {EOL_CONFIRMATION_RECORDS} consecutive "
                f"characterizations at or below {EOL_FRACTION:.0%} of baseline capacity; "
                "this is a project screening convention, not an Oxford-provided EOL rule"
            ),
        },
        "generated_ev_context_columns": {
            "ambient_temperature_c": "generated ambient scenario temperature",
            "battery_pack_temperature_c": "generated pack-temperature scenario",
            "state_of_charge_pct": "generated state-of-charge scenario",
            "average_speed_kph": "generated trip-average speed scenario",
            "energy_consumption_wh_per_km": "generated energy-use scenario",
            "dc_fast_charge_share_pct": "generated share of charging from DC fast charging",
            "charge_power_kw": "generated representative charging-power scenario",
            "estimated_odometer_km": "generated cumulative-distance scenario",
        },
        "limitations": [
            "75% is an explicit exploratory convention, not an official source EOL rule.",
            "Only threshold-crossing cells receive RUL values; other cells are right-censored.",
            "Persistent RUL labels require two consecutive below-threshold records; this rule is a conservative project convention, not a validated standard.",
            "Only eight laboratory cells are available; do not claim robust EV-fleet RUL performance.",
            "Only two cells cross the threshold, so a meaningful cell-disjoint RUL train/validation/test evaluation is unsupported.",
            "Rows are characterization observations, not independent samples; split by cell before modeling.",
            "EV context columns are generated, deterministic scenarios rather than Oxford source measurements.",
            "Do not use capacity_1c_discharge_mah as a predictor when predicting SOH derived from that same capacity.",
            "No failure-classification labels are available.",
        ],
        "cell_count": len(cell_audit),
        "record_count": len(rows),
        "cell_audit": cell_audit,
    }
    (OUTPUT_DIR / "preprocessing_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT_DIR),
                "cells": len(cell_audit),
                "records": len(rows),
                "threshold_crossing_cells": [
                    cell
                    for cell, audit in cell_audit.items()
                    if audit["first_threshold_crossing_cycle"] is not None
                ],
                "right_censored_cells": [
                    cell
                    for cell, audit in cell_audit.items()
                    if audit["right_censored"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
