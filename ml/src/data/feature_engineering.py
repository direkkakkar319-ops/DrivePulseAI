"""Derived features for DrivePulse AI datasets."""

from __future__ import annotations

import pandas as pd

# Mode flags rebuild the label, so they stay out of classifier inputs.
AI4I_LEAKAGE_COLS: list[str] = ["TWF", "HDF", "PWF", "OSF", "RNF"]

# EDA wear cliff: ~2% failure below, ~13% above.
AI4I_WEAR_CLIFF: float = 195.0

# Short CSV headers and long loader-mapped names for the same sensor.
AI4I_COLUMN_ALIASES: dict[str, list[str]] = {
    "rpm": ["engine_rpm", "Rotational speed [rpm]", "Rotational speed"],
    "torque": ["engine_load_pct", "Torque [Nm]", "Torque"],
    "process_temp": ["coolant_temp_c", "Process temperature [K]", "Process temperature"],
    "air_temp": ["intake_air_temp_c", "Air temperature [K]", "Air temperature"],
    "wear": ["vibration", "Tool wear [min]", "Tool wear"],
    "failure": ["failure", "Machine failure"],
    "type": ["machine_type", "Type"],
}


class FeatureEngineering:
    """Derived features. Inputs are never mutated."""

    @staticmethod
    def _resolve(df: pd.DataFrame, canonical: str) -> str:
        for alias in AI4I_COLUMN_ALIASES[canonical]:
            if alias in df.columns:
                return alias
        raise KeyError(
            f"No variant of {canonical!r} found. Columns: {list(df.columns)}"
        )

    @staticmethod
    def add_ai4i_features(
        df: pd.DataFrame,
        drop_leakage: bool = True,
        one_hot_type: bool = True,
    ) -> pd.DataFrame:
        """Adds temp_diff, power_proxy, and a wear-cliff flag."""
        out = df.copy()
        rpm = FeatureEngineering._resolve(out, "rpm")
        torque = FeatureEngineering._resolve(out, "torque")
        proc = FeatureEngineering._resolve(out, "process_temp")
        air = FeatureEngineering._resolve(out, "air_temp")
        wear = FeatureEngineering._resolve(out, "wear")

        out["temp_diff"] = out[proc] - out[air]
        out["power_proxy"] = out[rpm] * out[torque]
        out["wear_critical"] = (out[wear] >= AI4I_WEAR_CLIFF).astype(int)

        if one_hot_type:
            try:
                tcol = FeatureEngineering._resolve(out, "type")
            except KeyError:
                tcol = None
            if tcol is not None:
                dummies = pd.get_dummies(out[tcol], prefix="type", dtype=int)
                out = pd.concat([out.drop(columns=[tcol]), dummies], axis=1)

        if drop_leakage:
            out = out.drop(
                columns=[c for c in AI4I_LEAKAGE_COLS if c in out.columns]
            )

        return out

    @staticmethod
    def ai4i_model_columns(df: pd.DataFrame) -> list[str]:
        """Numeric classifier inputs. Call after add_ai4i_features."""
        exclude = (
            set(AI4I_LEAKAGE_COLS)
            | {"failure", "Machine failure", "rul", "vehicle_id", "source"}
        )
        return [
            c
            for c in df.columns
            if c not in exclude and pd.api.types.is_numeric_dtype(df[c])
        ]
