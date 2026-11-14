"""Forecasting-based novelty scoring for unlabeled telemetry windows."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor


class XGBoostForecastAnomalyDetector:
    """Forecast the next telemetry window and flag unusually large errors as novel.

    Novelty scores are not verified fault diagnoses.
    """

    def __init__(
        self,
        target_names: list[str],
        threshold_quantile: float = 0.99,
        random_state: int = 42,
    ) -> None:
        """Set XGBoost options, target signals, and the novelty threshold percentile."""
        if not target_names:
            raise ValueError("target_names must contain at least one signal")
        if not 0 < threshold_quantile < 1:
            raise ValueError("threshold_quantile must be between 0 and 1")
        self.target_names = list(target_names)
        self.threshold_quantile = threshold_quantile
        self.random_state = random_state
        base = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=random_state,
            n_jobs=4,
        )
        self.model = MultiOutputRegressor(base, n_jobs=1)
        self.feature_names: list[str] | None = None
        self.residual_scale: np.ndarray | None = None
        self.threshold: float | None = None

    @staticmethod
    def _features(features: pd.DataFrame | np.ndarray) -> pd.DataFrame:
        """Convert inputs to a finite numeric DataFrame or raise a clear error."""
        frame = (
            features.copy()
            if isinstance(features, pd.DataFrame)
            else pd.DataFrame(features)
        )
        if frame.empty or frame.shape[1] == 0:
            raise ValueError("features must contain at least one row and one column")
        try:
            frame = frame.astype(float)
        except (TypeError, ValueError) as exc:
            raise ValueError("forecast features must be numeric") from exc
        if not np.isfinite(frame.to_numpy()).all():
            raise ValueError("forecast features must be finite")
        return frame

    def fit(
        self, features: pd.DataFrame, targets: pd.DataFrame
    ) -> XGBoostForecastAnomalyDetector:
        """Train on current-window features and the next-window signal targets."""
        x = self._features(features)
        y = self._features(targets)
        if len(x) != len(y) or len(x) < 2:
            raise ValueError(
                "features and targets need matching lengths of at least two"
            )
        if list(y.columns) != self.target_names:
            raise ValueError("target columns must match target_names in the same order")
        self.feature_names = [str(name) for name in x.columns]
        self.model.fit(x, y)
        return self

    def _residuals(self, features: pd.DataFrame, targets: pd.DataFrame) -> np.ndarray:
        """Calculate per-signal differences between observed and forecast values."""
        if self.feature_names is None:
            raise RuntimeError("fit must be called before scoring")
        x = self._features(features)
        y = self._features(targets)
        if [str(name) for name in x.columns] != self.feature_names:
            raise ValueError("feature columns and order must match the fitted model")
        if list(y.columns) != self.target_names:
            raise ValueError("target columns must match target_names in the same order")
        if len(x) != len(y):
            raise ValueError("features and targets need matching lengths")
        return y.to_numpy() - self.model.predict(x)

    def score(self, features: pd.DataFrame, targets: pd.DataFrame) -> np.ndarray:
        """Return one scale-normalized forecast-error novelty score per row."""
        if self.residual_scale is None:
            raise RuntimeError("fit must be called before scoring")
        residuals = self._residuals(features, targets)
        scaled = residuals / self.residual_scale
        return np.sqrt(np.mean(np.square(scaled), axis=1))

    def calibrate(self, features: pd.DataFrame, targets: pd.DataFrame) -> np.ndarray:
        """Learn per-signal error scales and set the threshold from calibration rows."""
        residuals = self._residuals(features, targets)
        scale = np.sqrt(np.mean(np.square(residuals), axis=0))
        self.residual_scale = np.where(scale > 1e-12, scale, 1.0)
        scores = np.sqrt(np.mean(np.square(residuals / self.residual_scale), axis=1))
        self.threshold = float(np.quantile(scores, self.threshold_quantile))
        return scores

    def predict(self, features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
        """Return each row's novelty score and whether it exceeds the threshold."""
        if self.threshold is None:
            raise RuntimeError("fit and calibrate must be called before prediction")
        scores = self.score(features, targets)
        return pd.DataFrame(
            {"anomaly_score": scores, "is_novel": scores > self.threshold},
            index=features.index,
        )

    def save(self, path: str | Path) -> None:
        """Save the fitted and calibrated detector as a joblib artifact."""
        if self.threshold is None or self.feature_names is None:
            raise RuntimeError("fit and calibrate must be called before saving")
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> XGBoostForecastAnomalyDetector:
        """Load a saved detector and verify the artifact has the expected type."""
        detector = joblib.load(path)
        if not isinstance(detector, cls):
            raise TypeError(
                f"artifact at {path} is not an XGBoostForecastAnomalyDetector"
            )
        return detector
