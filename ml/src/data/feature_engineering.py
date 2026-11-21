"""Model-specific Nissan Leaf input selection and validation."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

NISSAN_LEAF_ANOMALY_FEATURES = (
    "HV_Bat_Voltage",
    "Pack_1_C_Temp",
    "SOC",
    "HV_Bat_Current_2",
    "Pack_2_C_Temp",
    "Pack_4_C_Temp",
)
NISSAN_LEAF_RUL_FEATURES = ("Timestamp", "Odometer", "SOH")
NISSAN_LEAF_RUL_CONTEXT = (
    "Pack_Avg_C_Temp",
    "Pack_1_C_Temp",
    "Pack_2_C_Temp",
    "Pack_4_C_Temp",
    "HV_Bat_Current_2",
    "SOC",
    "HV_Bat_Voltage",
)


def _numeric_columns(
    frame: pd.DataFrame, columns: Sequence[str], *, task: str
) -> pd.DataFrame:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{task} input is missing columns: {missing}")
    result = frame.loc[:, list(columns)].copy()
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    values = result.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{task} input contains missing or non-finite values")
    return result


def nissan_leaf_anomaly_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Select the three measured features expected by the fitted Isolation Forest.

    No derived or synthetic columns are added. Invalid rows raise an error;
    this helper never silently shrinks the caller's dataset.
    """
    result = _numeric_columns(frame, NISSAN_LEAF_ANOMALY_FEATURES, task="anomaly")
    if not result.SOC.between(0, 100).all():
        raise ValueError("anomaly SOC values must be within [0, 100]")
    if not result.HV_Bat_Voltage.between(0, 500, inclusive="right").all():
        raise ValueError("anomaly battery voltage must be within (0, 500]")
    return result


def nissan_leaf_rul_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Select RUL history and available context without changing the measurements."""
    result = _numeric_columns(frame, NISSAN_LEAF_RUL_FEATURES, task="RUL")
    for column in NISSAN_LEAF_RUL_CONTEXT:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            if np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).any():
                raise ValueError(f"RUL context {column} contains infinite values")
            result[column] = values
    if (result.Timestamp < 0).any() or (result.Odometer < 0).any():
        raise ValueError("RUL timestamps and odometer values must be nonnegative")
    if not result.SOH.between(0, 100).all():
        raise ValueError("RUL SOH values must be within [0, 100]")
    return result
