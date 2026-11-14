"""Train an exploratory XGBoost next-window novelty model on KIT OBD data.

Run from the repository root with ``python3 -m ml.scripts.train_kit_xgb_forecast``.
The experiment has no fault labels and makes no fault-detection claim.
"""

from __future__ import annotations

import gzip
import json
import math
from itertools import pairwise
from pathlib import Path

import numpy as np
import pandas as pd
from ml.src.models.anomaly_detector import XGBoostForecastAnomalyDetector

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data/automotive_obd/kit_obd/processed/windows_10s.csv.gz"
ARTIFACT_PATH = ROOT / "ml/artifacts/kit_xgb_forecast.joblib"
REPORT_PATH = ROOT / "ml/reports/modeling/kit_xgb_forecast_baseline.json"
METADATA_COLUMNS = {
    "split",
    "recording_date",
    "recording_id",
    "segment_id",
    "window_start_seconds",
}


def make_next_window_pairs(
    windows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pair consecutive windows without crossing recordings, segments, or splits."""
    feature_columns = [
        column for column in windows.columns if column not in METADATA_COLUMNS
    ]
    target_columns = [
        column for column in feature_columns if column.endswith("__median")
    ]
    if not feature_columns or not target_columns:
        raise ValueError("processed KIT data is missing numeric window features")

    groups = windows.groupby(["recording_id", "segment_id"], sort=False)
    feature_rows: list[pd.Series] = []
    target_rows: list[pd.Series] = []
    metadata_rows: list[dict] = []
    for (_, _), group in groups:
        group = group.sort_values("window_start_seconds")
        records = group.to_dict("records")
        for current, following in pairwise(records):
            if current["split"] != following["split"]:
                continue
            if (
                following["window_start_seconds"] - current["window_start_seconds"]
                != 10
            ):
                continue
            feature_rows.append(
                pd.Series({name: current[name] for name in feature_columns})
            )
            target_rows.append(
                pd.Series({name: following[name] for name in target_columns})
            )
            metadata_rows.append(
                {
                    "split": current["split"],
                    "recording_date": current["recording_date"],
                    "recording_id": current["recording_id"],
                    "window_start_seconds": following["window_start_seconds"],
                }
            )
    if not feature_rows:
        raise ValueError("no consecutive 10-second KIT windows were found")
    return (
        pd.DataFrame(feature_rows).reset_index(drop=True),
        pd.DataFrame(target_rows).reset_index(drop=True),
        pd.DataFrame(metadata_rows),
    )


def summarize(scores: np.ndarray, threshold: float) -> dict:
    return {
        "rows": len(scores),
        "novel_rows": int(np.count_nonzero(scores > threshold)),
        "novel_rate": float(np.mean(scores > threshold)),
        "score_quantiles": {
            label: float(np.quantile(scores, quantile))
            for label, quantile in (
                ("p50", 0.50),
                ("p90", 0.90),
                ("p95", 0.95),
                ("p99", 0.99),
            )
        },
    }


def forecast_errors(
    model: XGBoostForecastAnomalyDetector,
    features: pd.DataFrame,
    targets: pd.DataFrame,
) -> dict:
    """Compare per-signal forecast errors with a last-window persistence baseline."""
    predictions = model.model.predict(features)
    persistence_columns = list(targets.columns)
    persistence = features[persistence_columns].to_numpy()
    observed = targets.to_numpy()
    result = {}
    for index, name in enumerate(persistence_columns):
        xgb_error = observed[:, index] - predictions[:, index]
        persistence_error = observed[:, index] - persistence[:, index]
        result[name.removesuffix("__median")] = {
            "xgboost_mae": float(np.mean(np.abs(xgb_error))),
            "persistence_mae": float(np.mean(np.abs(persistence_error))),
            "xgboost_rmse": float(np.sqrt(np.mean(np.square(xgb_error)))),
            "persistence_rmse": float(np.sqrt(np.mean(np.square(persistence_error)))),
        }
    return result


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(
            f"KIT windows not found at {DATA_PATH}; run ml/scripts/preprocess_kit_obd.py first"
        )
    with gzip.open(DATA_PATH, "rt", encoding="utf-8", newline="") as compressed:
        windows = pd.read_csv(compressed)
    features, targets, metadata = make_next_window_pairs(windows)

    train_dates = sorted(
        metadata.loc[metadata["split"] == "train", "recording_date"].unique()
    )
    if len(train_dates) < 3:
        raise ValueError(
            "at least three training dates are required for date-based calibration"
        )
    calibration_count = max(1, math.ceil(len(train_dates) * 0.20))
    calibration_dates = set(train_dates[-calibration_count:])
    fit_dates = set(train_dates[:-calibration_count])
    fit_mask = (metadata["split"] == "train") & metadata["recording_date"].isin(
        fit_dates
    )
    calibration_mask = (metadata["split"] == "train") & metadata["recording_date"].isin(
        calibration_dates
    )

    model = XGBoostForecastAnomalyDetector(
        target_names=list(targets.columns), threshold_quantile=0.99, random_state=42
    )
    model.fit(features.loc[fit_mask], targets.loc[fit_mask])
    calibration_scores = model.calibrate(
        features.loc[calibration_mask], targets.loc[calibration_mask]
    )
    if model.threshold is None:
        raise RuntimeError("calibration did not produce a novelty threshold")

    results = {
        "calibration": summarize(calibration_scores, model.threshold),
    }
    for split in ("validation", "test"):
        mask = metadata["split"] == split
        if mask.any():
            results[split] = summarize(
                model.score(features.loc[mask], targets.loc[mask]), model.threshold
            )
            results[split]["forecast_errors"] = forecast_errors(
                model, features.loc[mask], targets.loc[mask]
            )

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(ARTIFACT_PATH)
    report = {
        "dataset": "KIT Automotive OBD-II",
        "source_doi": "10.35097/1130",
        "method": "XGBoost next-window forecasting with residual novelty scores",
        "target": "median sensor values in the immediately following 10-second window",
        "input": "current window medians, population standard deviations, and missing fractions",
        "fit_date_count": len(fit_dates),
        "calibration_date_count": len(calibration_dates),
        "fit_dates": sorted(fit_dates),
        "calibration_dates": sorted(calibration_dates),
        "feature_count": int(features.shape[1]),
        "target_count": int(targets.shape[1]),
        "threshold_quantile": model.threshold_quantile,
        "threshold": model.threshold,
        "model_parameters": {
            "n_estimators": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": 4,
        },
        "results": results,
        "interpretation": (
            "Novelty flags mark windows whose forecast residual is large relative to the "
            "calibration dates. KIT has no verified fault labels; these are not fault diagnoses "
            "or fault-detection metrics."
        ),
        "limitations": [
            "Recording IDs are not verified vehicle IDs.",
            "Anomalous training/calibration windows may affect fit and threshold.",
            "The threshold is calibrated from a small chronological subset of training dates.",
            "A high novelty score can reflect normal context or operating-regime changes.",
            "No RUL, future-failure, or supervised fault claim is supported.",
        ],
        "artifact": str(ARTIFACT_PATH.relative_to(ROOT)),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT_PATH), **report["results"]}, indent=2))


if __name__ == "__main__":
    main()
