"""Generate current Leaf SOH score and threshold-distance projection."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.src.models.nissan_leaf_rul import NissanLeafRUL

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = (
    ROOT
    / "data/automotive_prognostics/nissan_leaf_2018/v1/processed/Dataset_Preprocessed.csv"
)
OUTPUT_PATH = ROOT / "ml/reports/modeling/nissan_leaf_rul_projection.json"
INPUT_COLUMNS = [
    "Timestamp",
    "Odometer",
    "SOH",
    "Pack_Avg_C_Temp",
    "SOC",
    "HV_Bat_Voltage",
]


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Preprocessed Leaf dataset not found: {DATA_PATH}")
    frame = pd.read_csv(DATA_PATH, usecols=INPUT_COLUMNS)
    result = NissanLeafRUL(eol_threshold_soh_pct=80.0).estimate(frame)
    report = {
        "dataset": str(DATA_PATH.relative_to(ROOT)),
        "rul_definition": "estimated kilometers until reported SOH reaches configurable 80% threshold",
        **result,
        "limitations": [
            "One vehicle only; estimates do not establish fleet generalization.",
            "The dataset has no observed crossing of the selected threshold; RUL is long-range extrapolation.",
            "Context statistics are descriptive and do not causally adjust the degradation slope.",
            "This is not remaining driving range on the current charge.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
