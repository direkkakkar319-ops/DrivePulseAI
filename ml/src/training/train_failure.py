"""Train failure classifiers on Scania APS (logreg, rf, xgb).

Usage:
    python ml/src/training/train_failure.py [--data-dir PATH]

Official test split stays untouched until final evaluation; the decision
threshold is tuned on a stratified validation slice of train with
recall >= 0.90, because a missed APS failure costs more than a false alarm.
Metrics and thresholds are printed and written to
ml/reports/figures/aps/output.md. Models go to ml/src/models/.
"""

from __future__ import annotations

import argparse
import functools
import sys
import time
import traceback
from functools import partial
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[3]
ML_DIR = THIS_FILE.parents[2]
for candidate in (ML_DIR, REPO_ROOT / "ml"):
    if (candidate / "src" / "data" / "loaders.py").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

import joblib
import numpy as np
import pandas as pd
from hyperactive.experiment.integrations import SklearnCvExperiment
from hyperactive.opt.gfo import BayesianOptimizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

from src.data.feature_engineering import FeatureEngineering
from src.data.loaders import load_aps
from src.data.preprocessing import PreProcessing

DEFAULT_DATA_DIR = REPO_ROOT / "data" / "automotive_failure" / "scania_aps" / "raw"
MODEL_DIR = REPO_ROOT / "ml" / "src" / "models" / "failure_classification"
OUT_DIR = REPO_ROOT / "ml" / "reports" / "figures" / "aps"

MIN_RECALL = 0.90
OUTPUT_LINES: list[str] = []


def log(line: str = "") -> None:
    print(line)
    OUTPUT_LINES.append(line)


class FailureClassifier:
    MODELS = ("logreg", "rf", "xgb")

    def __init__(
        self,
        model: str,
        threshold: float = 0.3,
        random_state: int = 42,
        n_iter: int = 50,
        beta: float = 2.0,
        **params,
    ) -> None:
        if model not in self.MODELS:
            raise ValueError(f"model not in {self.MODELS}")
        self.model_name = model
        self.threshold = threshold
        self.beta = beta
        self.random_state = random_state
        self.n_iter = n_iter
        self.params = params
        self.features: list[str] = []
        self.scaler = None
        self.model = None if model == "xgb" else self._build(model, random_state, params)

    @staticmethod
    def _build(model: str, random_state: int, params: dict) -> object:
        if model == "logreg":
            defaults = {"class_weight": "balanced", "max_iter": 1000}
            return LogisticRegression(**{**defaults, **params})
        defaults = {
            "n_estimators": 200,
            "class_weight": "balanced",
            "random_state": random_state,
        }
        return RandomForestClassifier(**{**defaults, **params})

    @staticmethod
    def _build_xgb(X, y, random_state: int, n_iter: int, params: dict, beta: float = 2.0):
        search_space = {
            "n_estimators": [100, 200, 300, 500],
            "max_depth": [3, 4, 5, 6, 8],
            "learning_rate": list(np.logspace(-3, -0.5, 10)),
            "subsample": list(np.arange(0.6, 1.01, 0.1)),
            "colsample_bytree": list(np.arange(0.6, 1.01, 0.1)),
        }
        xgb_exp = SklearnCvExperiment(
            estimator=XGBClassifier(eval_metric="logloss", random_state=random_state),
            scoring=partial(fbeta_score, beta=beta, zero_division=0),
            cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state),
            X=X,
            y=y,
        )
        optimizer = BayesianOptimizer(
            search_space=search_space, n_iter=n_iter, experiment=xgb_exp
        )
        best_params = optimizer.solve()
        return XGBClassifier(
            eval_metric="logloss",
            random_state=random_state,
            **{**best_params, **params},
        )

    def fit(self, X: pd.DataFrame, y: pd.Series) -> FailureClassifier:
        if self.model_name == "xgb":
            self.model = self._build_xgb(
                X, y, self.random_state, self.n_iter, self.params, self.beta
            )
        self.model.fit(X, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> pd.Series:
        return pd.Series(
            self.model.predict_proba(X)[:, 1], index=X.index, name="failure_proba"
        )

    def predict(self, X: pd.DataFrame) -> pd.Series:
        return (self.predict_proba(X) >= self.threshold).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
        pred = self.predict(X)
        tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
        scores = {
            "accuracy": float(accuracy_score(y, pred)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            f"f{self.beta:g}_score": float(
                fbeta_score(y, pred, beta=self.beta, zero_division=0)
            ),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
        }
        log(f"[{self.model_name}] threshold={self.threshold:.3f}")
        for name, value in scores.items():
            log(f"  {name}: {value:.4f}" if isinstance(value, float) else f"  {name}: {value}")
        return scores

    def suggest_threshold(
        self, X: pd.DataFrame, y: pd.Series, min_recall: float = MIN_RECALL
    ) -> float:
        precision, recall, thresholds = precision_recall_curve(y, self.predict_proba(X))
        table = pd.DataFrame(
            {"threshold": [*thresholds, 1.0], "precision": precision, "recall": recall}
        )
        ok = table[table["recall"] >= min_recall]
        if len(ok) > 0:
            return float(ok["threshold"].max())
        return 0.0

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model_name": self.model_name,
                "threshold": self.threshold,
                "features": self.features,
                "scaler": self.scaler,
                "model": self.model,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> FailureClassifier:
        bundle = joblib.load(path)
        clf = cls.__new__(cls)
        clf.model_name = bundle["model_name"]
        clf.threshold = bundle["threshold"]
        clf.features = bundle.get("features", [])
        clf.scaler = bundle.get("scaler")
        clf.random_state = 42
        clf.model = bundle["model"]
        return clf


def track_model_run(func):
    """Log results, time execution, keep one model's failure off the others."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        name = func.__name__
        log(f"\n{'=' * 50}\nRunning {name}...\n{'=' * 50}")
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            elapsed = time.perf_counter() - start
            log(f"[FAILED] {name} raised {type(e).__name__}: {e}")
            log(f"  time elapsed: {elapsed:.2f}s")
            traceback.print_exc()
            return None
        elapsed = time.perf_counter() - start
        log(f"[OK] {name} finished in {elapsed:.2f}s")
        if isinstance(result, dict):
            for k, v in result.items():
                log(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")
        return result

    return wrapper


def load_features(data_dir: Path):
    tr = load_aps(data_dir, split="train")
    te = load_aps(data_dir, split="test")
    tr = FeatureEngineering.add_aps_features(tr)
    te = FeatureEngineering.add_aps_features(te)
    feats = FeatureEngineering.aps_model_columns(tr)
    tr, stats = PreProcessing.clean(tr, return_imputer_stats=True)
    te = PreProcessing.clean(te, imputer_stats=stats)
    return tr[feats], tr["failure"], te[feats], te["failure"]


def scaled_split(
    X_tr: pd.DataFrame, X_val: pd.DataFrame, X_test: pd.DataFrame, feats: list[str]
):
    """Standardize for logreg only: scaler fit on train, reused on val/test."""
    X_tr_s, scaler = PreProcessing.scale(X_tr, feature_cols=feats)
    X_val_s, _ = PreProcessing.scale(X_val, scaler=scaler, feature_cols=feats)
    X_te_s, _ = PreProcessing.scale(X_test, scaler=scaler, feature_cols=feats)
    return X_tr_s, X_val_s, X_te_s, scaler


def main() -> None:
    parser = argparse.ArgumentParser(description="Train APS failure classifiers.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--n-iter", type=int, default=50,
                        help="Bayesianopt iterations for xgb.")
    args = parser.parse_args()

    if not Path(args.data_dir).exists():
        sys.exit(f"Data dir not found: {args.data_dir} (pass --data-dir PATH)")

    X, y, X_test, y_test = load_features(args.data_dir)
    log(f"[data] train={X.shape} pos={int(y.sum())} | "
        f"test={X_test.shape} pos={int(y_test.sum())}")
    X_tr, X_val, y_tr, y_val = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=42
    )

    @track_model_run
    def logreg_model():
        X_tr_s, X_val_s, X_te_s, scaler = scaled_split(X_tr, X_val, X_test,
                                                       X.columns.tolist())
        clf = FailureClassifier(model="logreg")
        clf.features = X.columns.tolist()
        clf.scaler = scaler
        clf.fit(X_tr_s, y_tr)
        clf.threshold = clf.suggest_threshold(X_val_s, y_val)
        out = clf.evaluate(X_te_s, y_test)
        clf.save(MODEL_DIR / "logreg_aps.joblib")
        return out

    @track_model_run
    def rf_model():
        clf = FailureClassifier(model="rf")
        clf.features = X.columns.tolist()
        clf.fit(X_tr, y_tr)
        clf.threshold = clf.suggest_threshold(X_val, y_val)
        out = clf.evaluate(X_test, y_test)
        clf.save(MODEL_DIR / "rf_aps.joblib")
        return out

    @track_model_run
    def xgb_model():
        clf = FailureClassifier(model="xgb", n_iter=args.n_iter)
        clf.features = X.columns.tolist()
        clf.fit(X_tr, y_tr)
        clf.threshold = clf.suggest_threshold(X_val, y_val)
        out = clf.evaluate(X_test, y_test)
        clf.save(MODEL_DIR / "xgb_aps.joblib")
        return out

    logreg_model()
    rf_model()
    xgb_model()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "output.md").write_text(
        "# Failure-classification training output (Scania APS)\n\n"
        "Logreg (standardized) / RF / XGB (raw levels) on 170 signals plus "
        "engineered n_missing and per-group sum/mean/max, median-imputed "
        "with train-fit stats. Thresholds tuned on a stratified "
        "15% validation slice for recall >= 0.90; official test evaluated once. "
        "pos = APS failure, neg = other-component failure.\n\n"
        + "\n".join(OUTPUT_LINES)
        + "\n",
        encoding="utf-8",
    )
    log(f"\n[done] output.md saved to {OUT_DIR / 'output.md'}")


if __name__ == "__main__":
    main()
