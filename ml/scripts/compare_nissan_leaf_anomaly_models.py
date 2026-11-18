"""Compare unsupervised detectors and finalize a Leaf battery novelty baseline.

No fault labels are present, so this is a descriptive model-selection experiment,
not a measured fault-detection benchmark.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = (
    ROOT
    / "data/automotive_prognostics/nissan_leaf_2018/v1/processed/Dataset_Preprocessed.csv"
)
ARTIFACT_PATH = ROOT / "ml/artifacts/nissan_leaf_2018/anomaly_detector.joblib"
REPORT_PATH = ROOT / "ml/reports/modeling/nissan_leaf_anomaly_model_comparison.json"
FEATURES = ["HV_Bat_Voltage", "Pack_1_C_Temp", "SOC"]
THRESHOLD_QUANTILE = 0.005
SEED = 42


def score_summary(scores: np.ndarray, threshold: float) -> dict:
    return {
        "rows": int(len(scores)),
        "flagged_rows": int(np.count_nonzero(scores < threshold)),
        "flagged_pct": float(100 * np.mean(scores < threshold)),
        "score_p01": float(np.quantile(scores, 0.01)),
        "score_median": float(np.median(scores)),
        "score_p99": float(np.quantile(scores, 0.99)),
    }


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Preprocessed Nissan Leaf CSV not found: {DATA_PATH}")
    frame = pd.read_csv(DATA_PATH, usecols=["Timestamp", *FEATURES])
    source_rows = len(frame)
    frame["Timestamp"] = pd.to_numeric(frame["Timestamp"], errors="coerce")
    frame[FEATURES] = frame[FEATURES].apply(pd.to_numeric, errors="coerce")
    finite = np.isfinite(frame[["Timestamp", *FEATURES]].to_numpy()).all(axis=1)
    valid = finite & frame.SOC.between(0, 100) & frame.HV_Bat_Voltage.gt(0)
    valid &= frame.HV_Bat_Voltage.le(500)
    frame = frame.loc[valid].sort_values("Timestamp", kind="stable").reset_index(drop=True)
    x = frame[FEATURES]
    n = len(x)
    train_end, val_end = int(n * 0.70), int(n * 0.85)
    train, validation, test = x.iloc[:train_end], x.iloc[train_end:val_end], x.iloc[val_end:]

    # Small chronological sample keeps quadratic/dense alternatives tractable.
    sample_n = min(20_000, len(train))
    train_sample = train.iloc[np.linspace(0, len(train) - 1, sample_n, dtype=int)]
    validation_sample = validation.iloc[np.linspace(0, len(validation) - 1, min(20_000, len(validation)), dtype=int)]
    test_sample = test.iloc[np.linspace(0, len(test) - 1, min(20_000, len(test)), dtype=int)]
    candidates = {
        "isolation_forest": IsolationForest(
            n_estimators=200,
            max_samples="auto",
            max_features=1.0,
            bootstrap=False,
            random_state=SEED,
            n_jobs=-1,
            contamination="auto",
        ),
        "local_outlier_factor": LocalOutlierFactor(
            n_neighbors=35, novelty=True, contamination="auto", n_jobs=-1
        ),
        "one_class_svm_rbf": OneClassSVM(kernel="rbf", gamma="scale", nu=0.005),
    }
    comparison = {}
    for name, estimator in candidates.items():
        started = time.perf_counter()
        estimator.fit(train_sample)
        fit_seconds = time.perf_counter() - started
        train_scores = estimator.score_samples(train_sample)
        threshold = float(np.quantile(train_scores, THRESHOLD_QUANTILE))
        started = time.perf_counter()
        validation_scores = estimator.score_samples(validation_sample)
        test_scores = estimator.score_samples(test_sample)
        score_seconds = time.perf_counter() - started
        comparison[name] = {
            "fit_rows": len(train_sample),
            "fit_seconds": fit_seconds,
            "score_seconds_for_40k_holdout_rows": score_seconds,
            "threshold": threshold,
            "threshold_quantile": THRESHOLD_QUANTILE,
            "validation": score_summary(validation_scores, threshold),
            "test": score_summary(test_scores, threshold),
        }

    # Isolation Forest is selected for its scalable tree-based scoring and broad
    # support for multimodal telemetry. Labels are unavailable to rank accuracy.
    final_model = IsolationForest(
        n_estimators=200,
        max_samples="auto",
        max_features=1.0,
        bootstrap=False,
        random_state=SEED,
        n_jobs=-1,
        contamination="auto",
    )
    final_model.fit(train)
    train_scores = final_model.score_samples(train)
    threshold = float(np.quantile(train_scores, THRESHOLD_QUANTILE))
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": final_model,
            "features": FEATURES,
            "threshold": threshold,
            "threshold_quantile": THRESHOLD_QUANTILE,
            "threshold_direction": "score_samples below threshold is flagged",
            "source": str(DATA_PATH.relative_to(ROOT)),
            "split_policy": "chronological 70/15/15 after timestamp sorting",
            "label_status": "no verified fault labels; exploratory novelty score only",
        },
        ARTIFACT_PATH,
    )
    report = {
        "dataset": "Nissan Leaf 2018 publisher-preprocessed telemetry",
        "source": str(DATA_PATH.relative_to(ROOT)),
        "source_rows": source_rows,
        "retained_rows": n,
        "excluded_rows": source_rows - n,
        "retained_pct": 100 * n / source_rows,
        "features": FEATURES,
        "split_policy": "chronological 70/15/15 after timestamp sorting",
        "candidate_evaluation": "20k evenly spaced training rows; up to 20k rows from each chronological holdout; training-only 0.5th percentile threshold",
        "candidate_results": comparison,
        "selected_model": "isolation_forest",
        "selection_reason": "Best practical fit for this large, potentially multimodal telemetry table: scalable tree-based scoring. No labels exist to establish fault-detection accuracy or rank models by accuracy.",
        "final_fit_rows": len(train),
        "final_threshold": threshold,
        "final_threshold_quantile": THRESHOLD_QUANTILE,
        "final_validation": score_summary(final_model.score_samples(validation), threshold),
        "final_test": score_summary(final_model.score_samples(test), threshold),
        "label_status": "Unsupervised flags identify unusual telemetry only; they do not confirm vehicle faults.",
        "artifact": str(ARTIFACT_PATH.relative_to(ROOT)),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
