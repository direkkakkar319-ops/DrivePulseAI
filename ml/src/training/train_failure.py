from __future__ import annotations

import sys
from pathlib import Path

_file_path = Path(__file__).resolve()
_models_dir = _file_path.parent
_src_dir = _file_path.parents[1]
_ml_dir = _file_path.parents[2]
_repo_dir = _file_path.parents[3]
_data_dir = _src_dir / "data"

for _p in [_ml_dir, _repo_dir, _src_dir, _data_dir]:
    _p_str = str(_p)
    if _p_str not in sys.path:
        sys.path.insert(0, _p_str)

import joblib
import pandas as pd
import numpy as np


from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import StratifiedKFold
from hyperactive.experiment.integrations import SklearnCvExperiment
from hyperactive.opt.gfo import BayesianOptimizer

from xgboost import XGBClassifier


class FailureClassifier:
    MODELS = ("logreg", "rf", "xgb")

    def __init__(self,model:str, threshold:float=0.3, random_state:int=42, **params)->None:
        if model not in self.MODELS:
            raise ValueError(f"model not in {self.MODELS}")
        self.model_name = model
        self.threshold = threshold

        if self.model!="xgb":
            self.model=self._build(model, random_state, params)
        else:
            self.model = None

    @staticmethod
    def _build(model:str, random_state:int, params:dict)->object:
        if model == "logreg":
            defaults = {"class_weight": "balanced", "max_iter": 1000}
            return LogesticRegression(**{**defaults, **params})

        if model == "rf":
            defaults = {
                "n_estimators": 200,
                "scale_pos_weight": DEFAULT_SCALE_POS_WEIGHT,
                "random_state": random_state,
            }
            return RandomForestClassifier(**{**defaults, **params})

    @staticmethod
    def _build_xgb(X, y, random_state: int, n_iter: int, params: dict, beta: float=2.0):
        search_space = {
            "n_estimators": [100, 200, 300, 500],
            "max_depth": [3, 4, 5, 6, 8],
            "learning_rate": list(np.logspace(-3, -0.5, 10)),
            "subsample": list(np.arange(0.6, 1.01, 0.1)),
            "colsample_bytree": list(np.arange(0.6, 1.01, 0.1)),
        }

        xgb_exp = SklearnCvExperiment(
            estimator=XGBClassifier(eval_metric="logloss", random_state=random_state),
            scoring=partial(f1_score, beta=beta, zero_division=0),
            cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state),
            X=X,
            y=y,
        )

        optimizer = BayesianOptimizer(search_space=search_space, n_iter=n_iter, experiment=xgb_exp)
        best_params = optimizer.solve()

        return XGBClassifier(eval_metric="logloss", random_state=random_state, **{**best_params, **params})

    def fit(self, X: pd.DataFrame, y: pd.Series) -> FailureClassifier:
        if model=="xgb":
            self.model._build_xgb(X, y, self.random_state, self.n_iter, self.params)

        self.model.fit(X, y)
        return self

    def predict_proba(self, X:pd.DataFrame)->pd.Series:
        return pd.Series(self.model.predict_proba(X)[:, 1], index=X.index, name="failure_proba")

    def predict(self, X:pd.DataFrame)->pd.Series:
        return (self.predict_proba(X)>=self.threshold).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
        pred = self.predict(X)
        scores = {
            "accuracy": float(accuracy_score(y, pred)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
        }

        print(f"[{self.model_name}] threshold={self.threshold:.3f}")
        for name, value in scores.items():
            print(f"  {name}: {value:.4f}")

        return scores

    def pr_table(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        precision, recall, thresholds = precision_recall_curve(y, self.predict_proba(X))
        return pd.DataFrame(
            {
                "threshold": [*thresholds, 1.0],
                "precision": precision,
                "recall": recall,
            }
        )

    def suggest_threshold(self, X: pd.DataFrame, y: pd.Series, min_recall: float = 0.85) -> float:
        table = self.pr_table(X, y)
        ok = table[table["recall"] >= min_recall]
        if len(ok) > 0:
            return float(ok["threshold"].max())
        return 0.0

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        joblib.dump(
            {
                "model_name": self.model_name,
                "threshold": self.threshold,
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
        clf.random_state = 42
        clf.model = bundle["model"]
        return clf


if __name__ == "__main__":
    try:
        from src.data.feature_engineering import FeatureEngineering
        from src.data.loaders import load_ai4i
        from src.data.preprocessing import PreProcessing
    except ModuleNotFoundError:
        from feature_engineering import FeatureEngineering
        from loaders import load_ai4i
        from preprocessing import PreProcessing

    csv_path = (
        _repo_dir
        / "data"
        / "failure_classification"
        / "raw"
        / "predictive_maintenance.csv"
    )
    if csv_path.exists():
        print(f"Loading dataset from {csv_path}...")
        df_raw = load_ai4i(csv_path)
        print(f"Loaded the dataset from {csv_path}")
    else:
        print(f"Error: Dataset not found at {csv_path}")
        sys.exit(1)

    df_preprocessed = PreProcessing.clean(df_raw)
    df_feat = FeatureEngineering.add_ai4i_features(df_preprocessed, drop_leakage=True) 
    feature_cols = FeatureEngineering.ai4i_model_columns(df_feat)
    print("="*40)
    print(df_raw.head())
    print("="*40)
    print(df_preprocessed.head())
    print("="*40)
    print(df_feat.head())
    print("="*40)
    print(feature_cols)