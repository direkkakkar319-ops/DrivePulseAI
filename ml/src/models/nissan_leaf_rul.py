"""Exploratory Leaf RUL projection in distance to a configurable SOH threshold."""

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
    """

    REQUIRED: ClassVar[set[str]] = {"Timestamp", "Odometer", "SOH"}
    CONTEXT: ClassVar[list[str]] = ["Pack_Avg_C_Temp", "SOC", "HV_Bat_Voltage"]

    def __init__(
        self,
        eol_threshold_soh_pct: float = 80.0,
        lookback_days: int = 365,
        min_daily_observations: int = 8,
    ) -> None:
        if not 0 < eol_threshold_soh_pct < 100:
            raise ValueError("eol_threshold_soh_pct must be between 0 and 100")
        if lookback_days <= 0 or min_daily_observations < 3:
            raise ValueError(
                "lookback_days must be positive and minimum observations >= 3"
            )
        self.eol_threshold_soh_pct = float(eol_threshold_soh_pct)
        self.lookback_days = int(lookback_days)
        self.min_daily_observations = int(min_daily_observations)

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
            "context_summary": {
                column: float(history[column].mean())
                for column in self.CONTEXT
                if column in history and history[column].notna().any()
            },
            "context_use": "reported for interpretation; not used to alter the SOH decline slope",
        }
        if current_soh <= self.eol_threshold_soh_pct:
            return {**base, "status": "threshold_reached", "rul_km": 0.0}
        if len(history) < self.min_daily_observations:
            return {**base, "status": "insufficient_history", "rul_km": None}

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
        daily_distance = np.diff(history.Odometer.to_numpy(dtype=float))
        daily_distance = daily_distance[daily_distance > 0]
        km_per_day = float(np.median(daily_distance)) if len(daily_distance) else 0.0
        return {
            **base,
            "rul_km": float(distance),
            "estimated_days_to_threshold": float(distance / km_per_day)
            if km_per_day > 0
            else None,
            "median_daily_distance_km": km_per_day if km_per_day > 0 else None,
            "validation_status": "unvalidated_extrapolation_single_vehicle_no_threshold_crossing",
        }
