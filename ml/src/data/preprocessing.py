from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from loaders import load_ai4i, load_cmapss, load_simulated
from sklearn.preprocessing import StandardScaler


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

    @staticmethod
    def scale(df: pd.DataFrame, scaler: Any = None) -> tuple[pd.DataFrame, Any]:
        """
        Scale numeric features using StandardScaler.
        Fits a new scaler if none is provided (for training).
        Otherwise, uses the provided scaler (for validation/test - never fit on val/test).

        Args:
            df: Input DataFrame to scale.
            scaler: A fitted scikit-learn scaler. If None, a new StandardScaler is fitted.

        Returns:
            tuple[pd.DataFrame, Any]: The scaled DataFrame and the scaler used.
        """
        if df.empty:
            return df.copy(), scaler

        scaled = df.copy()

        exclude_cols = ["vehicle_id", "source", "timestamp"]
        numeric_cols = scaled.select_dtypes(include=[np.number]).columns
        cols_to_scale = [col for col in numeric_cols if col not in exclude_cols]

        if not cols_to_scale:
            return scaled, scaler

        if scaler is None:
            scaler = StandardScaler()
            scaled[cols_to_scale] = scaler.fit_transform(scaled[cols_to_scale])
        else:
            scaled[cols_to_scale] = scaler.transform(scaled[cols_to_scale])

        return scaled, scaler

    @staticmethod
    def make_time_windows(df: pd.DataFrame, window_size: int, step: int = 1) -> np.ndarray:
        """
        Create overlapping time windows for sequential data (e.g., C-MAPSS sequences).
        Ensures that windows do not cross the boundary of different 'vehicle_id's.

        Args:
            df: Input DataFrame.
            window_size: The number of timesteps in each window.
            step: The number of timesteps to advance for the next window.

        Returns:
            np.ndarray: A 3D numpy array of shape (num_windows, window_size, num_features).
        """
        exclude_cols = ["source", "timestamp"]
        feature_cols = [c for c in df.columns if c not in exclude_cols]
        
        windows = []
        
        if "vehicle_id" in df.columns:
            for _, group in df.groupby("vehicle_id"):
                group_data = group[feature_cols].drop(columns=["vehicle_id"], errors="ignore").values
                for i in range(0, len(group_data) - window_size + 1, step):
                    windows.append(group_data[i : i + window_size])
        else:
            group_data = df[feature_cols].values
            for i in range(0, len(group_data) - window_size + 1, step):
                windows.append(group_data[i : i + window_size])
                
        return np.array(windows)


    # def train_val_test_split(df, val_frac, test_frac, time_ordered=False):


# clean = PreProcessing.clean

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ai4i_path = PROJECT_ROOT / "data" / "failure_classification" / "raw" / "predictive_maintenance.csv"
cmapss_path = PROJECT_ROOT / "data" / "RUL_score" / "raw"
simulated_path = PROJECT_ROOT / "data" / "anomly_detection" / "raw"
