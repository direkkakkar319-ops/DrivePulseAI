"""Exploratory Leaf RUL projection in distance to a configurable SOH threshold with bootstrap confidence intervals."""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pandas as pd
from sklearn.linear_model import TheilSenRegressor

from ml.src.scoring.health_score import battery_health_score


class NissanLeafRUL:
    """Project kilometers to threshold from daily SOH/odometer history.

    Context fields are summarized for interpretation. They are not used as
    degradation multipliers because this single-vehicle dataset cannot identify
    their independent causal effects.

    Quantifies uncertainty via bootstrap resampling across historical daily
    observations to provide p10, p50, and p90 confidence intervals on RUL.
    """

    REQUIRED: ClassVar[set[str]] = {"Timestamp", "Odometer", "SOH"}
    CONTEXT: ClassVar[list[str]] = [
        "Pack_Avg_C_Temp",
        "Pack_1_C_Temp",
        "Pack_2_C_Temp",
        "Pack_4_C_Temp",
        "HV_Bat_Current_2",
        "SOC",
        "HV_Bat_Voltage",
    ]

    def __init__(
        self,
        eol_threshold_soh_pct: float = 80.0,
        lookback_days: int = 365,
        min_daily_observations: int = 30,
        min_history_span_days: int = 90,
        n_bootstrap: int = 100,
        confidence_level_pct: float = 80.0,
    ) -> None:
        if not 0 < eol_threshold_soh_pct < 100:
            raise ValueError("eol_threshold_soh_pct must be between 0 and 100")
        if (
            lookback_days <= 0
            or min_daily_observations < 3
            or min_history_span_days <= 0
        ):
            raise ValueError(
                "lookback_days and minimum span must be positive; minimum observations >= 3"
            )
        if n_bootstrap < 0:
            raise ValueError("n_bootstrap must be nonnegative")
        if not 0 < confidence_level_pct < 100:
            raise ValueError("confidence_level_pct must be between 0 and 100")

        self.eol_threshold_soh_pct = float(eol_threshold_soh_pct)
        self.lookback_days = int(lookback_days)
        self.min_daily_observations = int(min_daily_observations)
        self.min_history_span_days = int(min_history_span_days)
        self.n_bootstrap = int(n_bootstrap)
        self.confidence_level_pct = float(confidence_level_pct)

    def estimate(self, observations: pd.DataFrame) -> dict:
        missing = sorted(self.REQUIRED - set(observations.columns))
        if missing:
            raise ValueError(f"observations are missing required columns: {missing}")

        frame = observations.copy()
        for column in self.REQUIRED | (set(self.CONTEXT) & set(frame.columns)):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        valid = np.isfinite(frame[["Timestamp", "Odometer", "SOH"]].to_numpy()).all(
            axis=1
        )
        valid &= frame.SOH.between(0, 100) & frame.Odometer.ge(0)
        frame = frame.loc[valid].copy()
        if frame.empty:
            return {"status": "no_valid_history", "rul_km": None}

        frame["date"] = pd.to_datetime(frame.Timestamp, unit="us", utc=True).dt.floor(
            "D"
        )
        daily_agg = {"SOH": "median", "Odometer": "median"}
        for column in self.CONTEXT:
            if column in frame:
                daily_agg[column] = "mean"
        daily = frame.groupby("date", as_index=False).agg(daily_agg).sort_values("date")
        cutoff = daily.date.max() - pd.Timedelta(days=self.lookback_days)
        history = daily.loc[daily.date >= cutoff].copy()
        current = daily.iloc[-1]
        current_soh = float(current.SOH)
        current_odo = float(current.Odometer)
        health = battery_health_score(current_soh)
        base = {
            "status": "ok",
            "current_soh_pct": current_soh,
            "current_odometer_km": current_odo,
            "health_score": health["health_score"],
            "health_label": health["label"],
            "eol_threshold_soh_pct": self.eol_threshold_soh_pct,
            "daily_observations_used": len(history),
            "history_span_days": int((history.date.max() - history.date.min()).days)
            if len(history) > 1
            else 0,
            "minimum_history_span_days": self.min_history_span_days,
            "context_summary": {
                column: float(history[column].mean())
                for column in self.CONTEXT
                if column in history and history[column].notna().any()
            },
            "context_use": "reported for interpretation; not used to alter the SOH decline slope",
        }
        if current_soh <= self.eol_threshold_soh_pct:
            return {
                **base,
                "status": "threshold_reached",
                "rul_km": 0.0,
                "rul_km_p10": 0.0,
                "rul_km_p50": 0.0,
                "rul_km_p90": 0.0,
                "confidence_interval": {
                    "level_pct": self.confidence_level_pct,
                    "rul_km_p10": 0.0,
                    "rul_km_p50": 0.0,
                    "rul_km_p90": 0.0,
                    "estimated_days_p10": 0.0,
                    "estimated_days_p50": 0.0,
                    "estimated_days_p90": 0.0,
                    "bootstrap_iterations_valid": 0,
                },
            }
        span_days = int((history.date.max() - history.date.min()).days)
        if (
            len(history) < self.min_daily_observations
            or span_days < self.min_history_span_days
        ):
            return {**base, "status": "insufficient_history", "rul_km": None}

        history_start_date = history.date.iloc[0]
        history_end_date = history.date.iloc[-1]
        history_start_odometer = float(history.Odometer.iloc[0])
        history_end_odometer = float(history.Odometer.iloc[-1])
        history = history.dropna(subset=["Odometer", "SOH"])
        history = history.groupby("Odometer", as_index=False).SOH.median()
        if len(history) < self.min_daily_observations:
            return {**base, "status": "insufficient_odometer_variation", "rul_km": None}
        x = history.Odometer.to_numpy(dtype=float).reshape(-1, 1)
        y = history.SOH.to_numpy(dtype=float)
        model = TheilSenRegressor(random_state=42).fit(x, y)
        slope = float(model.coef_[0])
        base["soh_slope_pct_per_1000_km"] = slope * 1000
        if slope >= 0:
            return {**base, "status": "non_declining_trend", "rul_km": None}

        distance = (current_soh - self.eol_threshold_soh_pct) / -slope
        # Use net odometer change over elapsed calendar days so days without
        # driving are included in the daily rate.
        elapsed_days = int((history_end_date - history_start_date).days)
        odometer_change = history_end_odometer - history_start_odometer
        km_per_day = odometer_change / elapsed_days if elapsed_days > 0 else 0.0

        # Bootstrap confidence intervals
        ci_result = None
        rul_p10 = None
        rul_p50 = None
        rul_p90 = None
        days_p10 = None
        days_p50 = None
        days_p90 = None

        if self.n_bootstrap > 0 and len(history) >= 3:
            rng = np.random.default_rng(42)
            n_samples = len(x)
            valid_distances: list[float] = []
            for b in range(self.n_bootstrap):
                b_idx = rng.choice(n_samples, size=n_samples, replace=True)
                if len(np.unique(x[b_idx])) < 2:
                    continue
                b_model = TheilSenRegressor(
                    random_state=42 + b, max_subpopulation=500
                ).fit(x[b_idx], y[b_idx])
                b_slope = float(b_model.coef_[0])
                if b_slope < 0:
                    b_dist = (current_soh - self.eol_threshold_soh_pct) / -b_slope
                    if np.isfinite(b_dist) and b_dist > 0:
                        valid_distances.append(b_dist)

            if len(valid_distances) >= 10:
                alpha = (100.0 - self.confidence_level_pct) / 2.0
                rul_p10 = float(np.percentile(valid_distances, alpha))
                rul_p50 = float(np.percentile(valid_distances, 50.0))
                rul_p90 = float(np.percentile(valid_distances, 100.0 - alpha))
                if km_per_day > 0:
                    days_p10 = float(rul_p10 / km_per_day)
                    days_p50 = float(rul_p50 / km_per_day)
                    days_p90 = float(rul_p90 / km_per_day)

                ci_result = {
                    "level_pct": self.confidence_level_pct,
                    "rul_km_p10": rul_p10,
                    "rul_km_p50": rul_p50,
                    "rul_km_p90": rul_p90,
                    "estimated_days_p10": days_p10,
                    "estimated_days_p50": days_p50,
                    "estimated_days_p90": days_p90,
                    "bootstrap_iterations_valid": len(valid_distances),
                    "interpretation": (
                        f"{self.confidence_level_pct:.0f}% bootstrap confidence interval "
                        "reflecting uncertainty from finite historical samples and SOH measurement noise."
                    ),
                }

        return {
            **base,
            "rul_km": float(distance),
            "rul_km_p10": rul_p10,
            "rul_km_p50": rul_p50,
            "rul_km_p90": rul_p90,
            "estimated_days_to_threshold": float(distance / km_per_day)
            if km_per_day > 0
            else None,
            "estimated_days_to_threshold_p10": days_p10,
            "estimated_days_to_threshold_p50": days_p50,
            "estimated_days_to_threshold_p90": days_p90,
            "average_calendar_distance_km_per_day": km_per_day
            if km_per_day > 0
            else None,
            "confidence_interval": ci_result,
            "validation_status": "unvalidated_extrapolation_single_vehicle_no_threshold_crossing",
        }
