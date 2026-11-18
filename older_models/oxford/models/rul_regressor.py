"""Exploratory battery RUL estimation from observed capacity trends."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import TheilSenRegressor


class TheilSenCapacityTrendRUL:
    """Extrapolate a cell's recent capacity fade to its configured EOL threshold."""

    def __init__(
        self,
        lookback_cycles: int = 1000,
        min_observations: int = 4,
        random_state: int = 42,
    ) -> None:
        """Set the history window and minimum points for a robust local trend."""
        if lookback_cycles <= 0:
            raise ValueError("lookback_cycles must be positive")
        if min_observations < 2:
            raise ValueError("min_observations must be at least two")
        self.lookback_cycles = lookback_cycles
        self.min_observations = min_observations
        self.random_state = random_state

    def estimate(self, observations: pd.DataFrame, as_of_cycle: int) -> dict:
        """Estimate remaining drive cycles using only records at or before cutoff."""
        required = {
            "characterization_cycle",
            "capacity_1c_discharge_mah",
            "eol_threshold_capacity_mah",
        }
        missing = sorted(required - set(observations.columns))
        if missing:
            raise ValueError(f"observations are missing required columns: {missing}")

        history = observations.loc[
            observations["characterization_cycle"] <= as_of_cycle
        ].copy()
        history = history.dropna(
            subset=["characterization_cycle", "capacity_1c_discharge_mah"]
        ).sort_values("characterization_cycle")
        if history.empty:
            return {"status": "no_history", "rul_cycles": None}

        history = history.loc[
            history["characterization_cycle"] >= as_of_cycle - self.lookback_cycles
        ]
        if len(history) < self.min_observations:
            return {
                "status": "insufficient_history",
                "rul_cycles": None,
                "observations_used": len(history),
            }

        cycles = history["characterization_cycle"].to_numpy(dtype=float)
        capacity = history["capacity_1c_discharge_mah"].to_numpy(dtype=float)
        threshold = float(history["eol_threshold_capacity_mah"].iloc[-1])
        current_cycle = float(cycles[-1])
        current_capacity = float(capacity[-1])
        model = TheilSenRegressor(random_state=self.random_state)
        model.fit(cycles.reshape(-1, 1), capacity)
        slope = float(model.coef_[0])

        result = {
            "status": "ok",
            "as_of_cycle": int(as_of_cycle),
            "current_cycle": current_cycle,
            "current_capacity_mah": current_capacity,
            "threshold_capacity_mah": threshold,
            "capacity_slope_mah_per_cycle": slope,
            "observations_used": len(history),
        }
        if current_capacity <= threshold:
            return {**result, "status": "threshold_already_crossed", "rul_cycles": 0.0}
        if slope >= 0:
            return {**result, "status": "non_declining_trend", "rul_cycles": None}

        rul_cycles = (current_capacity - threshold) / -slope
        return {**result, "rul_cycles": float(rul_cycles)}


class ExponentialCapacityTrendRUL:
    """Experimental exponential capacity-fade extrapolation for proxy RUL work."""

    def __init__(self, lookback_cycles: int = 2000, min_observations: int = 4) -> None:
        """Set the recent-history window and minimum points used for the fit."""
        if lookback_cycles <= 0:
            raise ValueError("lookback_cycles must be positive")
        if min_observations < 2:
            raise ValueError("min_observations must be at least two")
        self.lookback_cycles = lookback_cycles
        self.min_observations = min_observations

    def estimate(self, observations: pd.DataFrame, as_of_cycle: int) -> dict:
        """Fit log-capacity against past cycles and project to the EOL threshold."""
        required = {
            "characterization_cycle",
            "capacity_1c_discharge_mah",
            "eol_threshold_capacity_mah",
        }
        missing = sorted(required - set(observations.columns))
        if missing:
            raise ValueError(f"observations are missing required columns: {missing}")

        history = observations.loc[
            observations["characterization_cycle"] <= as_of_cycle
        ].copy()
        history = history.dropna(
            subset=["characterization_cycle", "capacity_1c_discharge_mah"]
        ).sort_values("characterization_cycle")
        history = history.loc[
            history["characterization_cycle"] >= as_of_cycle - self.lookback_cycles
        ]
        if len(history) < self.min_observations:
            return {
                "status": "insufficient_history",
                "rul_cycles": None,
                "observations_used": len(history),
            }

        cycles = history["characterization_cycle"].to_numpy(dtype=float)
        capacity = history["capacity_1c_discharge_mah"].to_numpy(dtype=float)
        threshold = float(history["eol_threshold_capacity_mah"].iloc[-1])
        current_cycle = float(cycles[-1])
        current_capacity = float(capacity[-1])
        result = {
            "status": "ok",
            "as_of_cycle": int(as_of_cycle),
            "current_cycle": current_cycle,
            "current_capacity_mah": current_capacity,
            "threshold_capacity_mah": threshold,
            "observations_used": len(history),
        }
        if current_capacity <= threshold:
            return {**result, "status": "threshold_already_crossed", "rul_cycles": 0.0}
        if np.any(capacity <= 0):
            return {**result, "status": "invalid_capacity", "rul_cycles": None}

        x = cycles - current_cycle
        log_slope = float(np.polyfit(x, np.log(capacity), deg=1)[0])
        if log_slope >= 0:
            return {**result, "status": "non_declining_trend", "rul_cycles": None}

        rul_cycles = np.log(threshold / current_capacity) / log_slope
        return {**result, "rul_cycles": float(rul_cycles)}
