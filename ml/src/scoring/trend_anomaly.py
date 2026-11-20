"""Rolling Z-score trend anomaly and parameter drift detector for EV battery telemetry."""

from __future__ import annotations

import math
from typing import ClassVar

import numpy as np
import pandas as pd


class BatteryTrendAnomalyDetector:
    """Detect multi-day temporal drift and gradual degradation anomalies in EV telemetry.

    Unlike row-level point anomaly detectors (e.g. Isolation Forest) which inspect
    instantaneous telemetry vectors without temporal context, this detector tracks
    rolling baselines across days to catch slow physical drifts:
      1. Battery pack temperature spread widening (cooling obstruction or cell imbalance)
      2. Pack temperature rise over ambient (thermal dissipation degradation)
      3. Accelerated SOH decline rate (sudden capacity fade)
      4. Excessive pack average temperature drift
    """

    MONITORED_SIGNALS: ClassVar[dict[str, dict]] = {
        "pack_temp_spread": {
            "label": "Battery Pack Temperature Spread",
            "unit": "°C",
            "min_std": 0.1,
            "min_baseline_mean": 0.0,
            "high_is_bad": True,
            "description": "Temperature difference between hottest and coldest battery modules.",
        },
        "pack_temp_rise": {
            "label": "Pack Temperature Rise Over Ambient",
            "unit": "°C",
            "min_std": 0.2,
            "min_baseline_mean": None,
            "high_is_bad": True,
            "description": "Thermal delta between average battery pack and ambient air temperature.",
        },
        "soh_decline_rate_per_kkm": {
            "label": "SOH Degradation Rate",
            "unit": "%/1,000km",
            "min_std": 0.02,
            "min_baseline_mean": 0.0,
            "high_is_bad": True,
            "description": "Rate of battery State of Health loss per 1,000 km driven.",
        },
        "pack_avg_temp": {
            "label": "Pack Average Temperature",
            "unit": "°C",
            "min_std": 0.5,
            "min_baseline_mean": None,
            "high_is_bad": True,
            "description": "Overall mean battery pack operating temperature.",
        },
    }

    def __init__(
        self,
        window_size: int = 14,
        min_history_points: int = 7,
        warning_z: float = 2.5,
        critical_z: float = 3.5,
        consecutive_points: int = 2,
    ) -> None:
        if window_size < 3:
            raise ValueError("window_size must be at least 3")
        if min_history_points < 3 or min_history_points > window_size:
            raise ValueError(
                "min_history_points must be at least 3 and <= window_size"
            )
        if warning_z <= 0 or critical_z <= warning_z:
            raise ValueError("warning_z must be positive and critical_z > warning_z")
        if consecutive_points < 1:
            raise ValueError("consecutive_points must be at least 1")

        self.window_size = int(window_size)
        self.min_history_points = int(min_history_points)
        self.warning_z = float(warning_z)
        self.critical_z = float(critical_z)
        self.consecutive_points = int(consecutive_points)

    def _prepare_daily(self, observations: pd.DataFrame) -> pd.DataFrame:
        frame = observations.copy()
        for col in frame.columns:
            if col != "date":
                frame[col] = pd.to_numeric(frame[col], errors="coerce")

        if "Timestamp" in frame.columns and frame["Timestamp"].notna().any():
            frame = frame.loc[frame["Timestamp"].notna() & frame["Timestamp"].ge(0)].copy()
            frame["date"] = pd.to_datetime(frame["Timestamp"], unit="us", utc=True).dt.floor("D")
            agg_rules: dict[str, str] = {}
            for col in frame.columns:
                if col in {"Timestamp", "date"}:
                    continue
                if col in {"SOH", "Odometer"}:
                    agg_rules[col] = "median"
                else:
                    agg_rules[col] = "mean"
            daily = frame.groupby("date", as_index=False).agg(agg_rules).sort_values("date")
        else:
            daily = frame.copy().reset_index(drop=True)

        return daily

    def analyze(self, observations: pd.DataFrame) -> dict:
        """Run rolling Z-score trend analysis across battery telemetry channels."""
        if observations.empty:
            return {
                "status": "empty_input",
                "is_drift_detected": False,
                "drift_alerts_count": 0,
                "alerts": [],
                "signal_details": {},
            }

        daily = self._prepare_daily(observations)
        n_days = len(daily)

        if n_days < self.min_history_points + 1:
            return {
                "status": "insufficient_history",
                "days_available": n_days,
                "min_days_required": self.min_history_points + 1,
                "is_drift_detected": False,
                "drift_alerts_count": 0,
                "alerts": [],
                "signal_details": {},
            }

        # Derive candidate signals
        signals_to_evaluate: dict[str, pd.Series] = {}

        # 1. Pack Temperature Spread
        pack_cols = [c for c in ["Pack_1_C_Temp", "Pack_2_C_Temp", "Pack_4_C_Temp"] if c in daily.columns]
        if len(pack_cols) >= 2:
            spread = daily[pack_cols].max(axis=1) - daily[pack_cols].min(axis=1)
            signals_to_evaluate["pack_temp_spread"] = spread

        # 2. Pack Temperature Rise Over Ambient
        if "Pack_Avg_C_Temp" in daily.columns and "Ambient_C_Temp" in daily.columns:
            rise = daily["Pack_Avg_C_Temp"] - daily["Ambient_C_Temp"]
            signals_to_evaluate["pack_temp_rise"] = rise
        elif "Pack_Avg_C_Temp" in daily.columns:
            signals_to_evaluate["pack_avg_temp"] = daily["Pack_Avg_C_Temp"]

        # 3. SOH Decline Rate per 1,000 km
        if "SOH" in daily.columns and "Odometer" in daily.columns:
            delta_soh = -daily["SOH"].diff()
            delta_odo = daily["Odometer"].diff() / 1000.0  # per 1000 km
            valid_odo = delta_odo.gt(0.01)
            rate = pd.Series(np.nan, index=daily.index)
            rate.loc[valid_odo] = delta_soh.loc[valid_odo] / delta_odo.loc[valid_odo]
            # Replace negative degradation (calibration jumps) with zero for rate monitoring
            rate = rate.clip(lower=0.0)
            signals_to_evaluate["soh_decline_rate_per_kkm"] = rate

        alerts: list[dict] = []
        signal_details: dict[str, dict] = {}

        for sig_name, series in signals_to_evaluate.items():
            meta = self.MONITORED_SIGNALS.get(sig_name, {
                "label": sig_name,
                "unit": "",
                "min_std": 0.01,
                "min_baseline_mean": None,
                "high_is_bad": True,
                "description": "",
            })

            vals = series.to_numpy(dtype=float)
            current_val = float(vals[-1])
            if not math.isfinite(current_val):
                signal_details[sig_name] = {
                    "status": "non_finite_current_reading",
                    "label": meta["label"],
                }
                continue

            # Prior rolling window (strictly excluding the current point)
            history_vals = vals[:-1]
            valid_history = history_vals[np.isfinite(history_vals)]
            window_slice = valid_history[-self.window_size :]

            if len(window_slice) < self.min_history_points:
                signal_details[sig_name] = {
                    "status": "insufficient_baseline_points",
                    "baseline_points_available": len(window_slice),
                    "baseline_points_required": self.min_history_points,
                    "label": meta["label"],
                }
                continue

            mu = float(np.mean(window_slice))
            sigma = max(float(np.std(window_slice, ddof=1)), meta["min_std"])
            z = (current_val - mu) / sigma

            # Check persistence across recent consecutive points
            consec = 0
            for i in range(1, min(len(vals), self.consecutive_points + 3)):
                val_i = vals[-i]
                if not math.isfinite(val_i):
                    break
                hist_i = vals[: -i]
                valid_hist_i = hist_i[np.isfinite(hist_i)]
                slice_i = valid_hist_i[-self.window_size :]
                if len(slice_i) >= self.min_history_points:
                    mu_i = float(np.mean(slice_i))
                    sigma_i = max(float(np.std(slice_i, ddof=1)), meta["min_std"])
                    z_i = (val_i - mu_i) / sigma_i
                    if (z_i >= self.warning_z if meta["high_is_bad"] else abs(z_i) >= self.warning_z):
                        consec += 1
                    else:
                        break

            is_alert = (
                (z >= self.warning_z if meta["high_is_bad"] else abs(z) >= self.warning_z)
                and consec >= self.consecutive_points
            )

            severity = "normal"
            if is_alert:
                severity = "critical" if abs(z) >= self.critical_z else "warning"

            info = {
                "label": meta["label"],
                "unit": meta["unit"],
                "current_value": round(current_val, 4),
                "baseline_mean": round(mu, 4),
                "baseline_std": round(sigma, 4),
                "z_score": round(z, 2),
                "consecutive_abnormal_days": consec,
                "status": severity,
                "baseline_window_days": len(window_slice),
            }
            signal_details[sig_name] = info

            if is_alert:
                direction = "above" if z > 0 else "below"
                explanation = (
                    f"{meta['label']} is {current_val:.2f}{meta['unit']}, which is "
                    f"{abs(z):.1f} standard deviations {direction} the {len(window_slice)}-day "
                    f"baseline mean of {mu:.2f}{meta['unit']} (std: {sigma:.2f}{meta['unit']}). "
                    f"Abnormal pattern persisted for {consec} consecutive days."
                )
                alerts.append({
                    "signal": sig_name,
                    "label": meta["label"],
                    "severity": severity,
                    "z_score": round(z, 2),
                    "current_value": round(current_val, 4),
                    "baseline_mean": round(mu, 4),
                    "baseline_std": round(sigma, 4),
                    "unit": meta["unit"],
                    "consecutive_days": consec,
                    "explanation": explanation,
                })

        return {
            "status": "ok",
            "is_drift_detected": len(alerts) > 0,
            "drift_alerts_count": len(alerts),
            "days_evaluated": n_days,
            "window_size_days": self.window_size,
            "warning_z_threshold": self.warning_z,
            "critical_z_threshold": self.critical_z,
            "alerts": alerts,
            "signal_details": signal_details,
        }
