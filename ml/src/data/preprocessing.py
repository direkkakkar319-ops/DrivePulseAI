from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from loaders import load_ai4i, load_cmapss, load_simulated


class PreProcessing:
    """Data preprocessing and transformation utilities."""

    @staticmethod
    def clean(
        df: pd.DataFrame,
        drop_duplicates: bool = True,
        fill_dropouts: bool = True,
        fill_remaining_numeric: str | float | int | None = "median",
    ) -> pd.DataFrame:
        """
        Clean telemetry and predictive maintenance datasets.
        -----------------------------------------------------------------------
        1. Duplicate Removal
        2. Sensor Dropout Imputation (Time-Series Continuity)
        3. Boundary Null Imputation (Leading Dropouts)
        4. Residual Null Imputation

        Args:
            df: Input DataFrame with telemetry or maintenance features.
            drop_duplicates: Whether to drop duplicate rows (default: True).
            fill_dropouts: Whether to forward/backward fill sensor dropouts (default: True).
            fill_remaining_numeric: Strategy for residual numeric nulls ('median', 'mean', 0, or None).

        Returns:
            pd.DataFrame: Cleaned DataFrame with duplicates dropped, nulls resolved, and a reset continuous index.
        """
        if df.empty:
            return df.copy()

        cleaned = df.copy()

        # Drop duplicate rows
        if drop_duplicates:
            cleaned = cleaned.drop_duplicates()

        cleaned = cleaned.reset_index(drop=True)

        # Impute sensor dropouts (ffill + bfill)
        if fill_dropouts:
            fill_cols = [c for c in cleaned.columns if c not in ["vehicle_id", "source"]]
            if fill_cols:
                if "vehicle_id" in cleaned.columns:
                    cleaned[fill_cols] = (
                        cleaned.groupby("vehicle_id")[fill_cols]
                        .ffill()
                        .bfill()
                    )
                else:
                    cleaned[fill_cols] = cleaned[fill_cols].ffill().bfill()

        # Impute any residual numeric nulls
        if fill_remaining_numeric is not None:
            numeric_cols = cleaned.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if cleaned[col].isnull().any():
                    if fill_remaining_numeric == "median":
                        fill_val = cleaned[col].median()
                    elif fill_remaining_numeric == "mean":
                        fill_val = cleaned[col].mean()
                    elif isinstance(fill_remaining_numeric, (int, float)):
                        fill_val = fill_remaining_numeric
                    else:
                        fill_val = None

                    if pd.notnull(fill_val):
                        cleaned[col] = cleaned[col].fillna(fill_val)

        return cleaned

    # def scale(df, scaler=None)-> (pd.DataFrame, scaler):
    

    # def make_time_windows(df, window_size, step) -> np.ndarray:


    # def train_val_test_split(df, val_frac, test_frac, time_ordered=False):


# clean = PreProcessing.clean

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ai4i_path = PROJECT_ROOT / "data" / "failure_classification" / "raw" / "predictive_maintenance.csv"
cmapss_path = PROJECT_ROOT / "data" / "RUL_score" / "raw"
simulated_path = PROJECT_ROOT / "data" / "anomly_detection" / "raw"
