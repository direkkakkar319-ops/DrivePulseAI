"""Data preprocessing, cleaning, scaling, windowing, and partitioning."""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

DEFAULT_TARGET_COLS: list[str] = ["failure", "rul"]
DEFAULT_META_COLS: list[str] = ["vehicle_id", "source", "timestamp"]


class PreProcessing:
    """Data preprocessing and transformation utilities."""

    @staticmethod
    def clean(
        df: pd.DataFrame,
        drop_duplicates: bool = True,
        fill_dropouts: bool = True,
        fill_remaining_numeric: str | float | None = "median",
        feature_cols: list[str] | None = None,
        exclude_cols: list[str] | None = None,
        impute_targets: bool = False,
        imputer_stats: dict[str, float] | None = None,
        return_imputer_stats: bool = False,
    ) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, float]]:
        """Clean telemetry and predictive maintenance datasets.

        Applies duplicate removal, time-series dropout imputation (ffill/bfill),
        and residual numeric imputation without leaking or corrupting supervised targets.

        Args:
            df: Input DataFrame with telemetry or maintenance features.
            drop_duplicates: Whether to drop duplicate rows.
            fill_dropouts: Whether to forward/backward fill sensor dropouts.
            fill_remaining_numeric: Strategy for residual numeric nulls ('median', 'mean',
                int/float constant, or None).
            feature_cols: Specific columns to impute. If None, derives from non-excluded columns.
            exclude_cols: Columns to exclude from imputation. Defaults to metadata and
                targets unless impute_targets is True.
            impute_targets: Whether to allow imputation on target columns ('failure', 'rul').
                Defaults to False to prevent label fabrication.
            imputer_stats: Pre-computed statistics dict for residual filling (e.g. from train).
            return_imputer_stats: If True, returns a tuple of (cleaned_df, computed_stats).

        Returns:
            pd.DataFrame or tuple[pd.DataFrame, dict[str, float]]:
                Cleaned DataFrame (and optional imputer stats dict).
        """
        if df.empty:
            return (df.copy(), {}) if return_imputer_stats else df.copy()

        cleaned = df.copy()

        if drop_duplicates:
            cleaned = cleaned.drop_duplicates()

        # Telemetry can arrive out of chronological order; sort before forward/backward filling
        # to ensure causal continuity per vehicle.
        if "timestamp" in cleaned.columns:
            if "vehicle_id" in cleaned.columns:
                cleaned = cleaned.sort_values(
                    by=["vehicle_id", "timestamp"]
                ).reset_index(drop=True)
            else:
                cleaned = cleaned.sort_values(by="timestamp").reset_index(drop=True)
        else:
            cleaned = cleaned.reset_index(drop=True)

        # Exclude targets by default so supervised failure/RUL labels are never fabricated.
        if feature_cols is not None:
            impute_cols = [c for c in feature_cols if c in cleaned.columns]
        else:
            if exclude_cols is not None:
                excl = set(exclude_cols)
            else:
                excl = set(DEFAULT_META_COLS)
                if not impute_targets:
                    excl.update(DEFAULT_TARGET_COLS)
            impute_cols = [c for c in cleaned.columns if c not in excl]

        # Impute sensor dropouts: ffill preserves causality across communication drops,
        # followed by bfill for leading missing values before the first valid sensor broadcast.
        if fill_dropouts and impute_cols:
            if "vehicle_id" in cleaned.columns:
                cleaned[impute_cols] = (
                    cleaned.groupby("vehicle_id")[impute_cols].ffill().bfill()
                )
            else:
                cleaned[impute_cols] = cleaned[impute_cols].ffill().bfill()

        computed_stats: dict[str, float] = {}

        if fill_remaining_numeric is not None:
            valid_strategies = ("median", "mean")
            is_valid_numeric_constant = isinstance(
                fill_remaining_numeric, (int, float)
            ) and not isinstance(fill_remaining_numeric, bool)
            if (
                fill_remaining_numeric not in valid_strategies
                and not is_valid_numeric_constant
            ):
                raise ValueError(
                    f"Unsupported fill_remaining_numeric strategy: {fill_remaining_numeric!r}. "
                    "Supported strategies are 'median', 'mean', numeric constants (int/float), or None."
                )

            numeric_impute_cols = [
                c for c in impute_cols if np.issubdtype(cleaned[c].dtype, np.number)
            ]

            for col in numeric_impute_cols:
                if imputer_stats is not None and col in imputer_stats:
                    fill_val = imputer_stats[col]
                elif fill_remaining_numeric == "median":
                    non_null = cleaned[col].dropna()
                    fill_val = float(non_null.median()) if not non_null.empty else 0.0
                elif fill_remaining_numeric == "mean":
                    non_null = cleaned[col].dropna()
                    fill_val = float(non_null.mean()) if not non_null.empty else 0.0
                else:
                    fill_val = float(fill_remaining_numeric)

                computed_stats[col] = fill_val

                if cleaned[col].isnull().any():
                    cleaned[col] = cleaned[col].fillna(fill_val)

        if return_imputer_stats:
            return cleaned, computed_stats
        return cleaned

    @staticmethod
    def scale(
        df: pd.DataFrame,
        scaler: Any = None,
        feature_cols: list[str] | None = None,
        exclude_cols: list[str] | None = None,
    ) -> tuple[pd.DataFrame, Any]:
        """Scale numeric features using StandardScaler.

        Fits a new scaler if none is provided (for training data).
        Reuses the provided scaler for validation/test sets (preventing data leakage).
        Label targets ('failure', 'rul') and metadata are excluded by default.

        Args:
            df: Input DataFrame to scale.
            scaler: A fitted scikit-learn scaler. If None, a new StandardScaler is fitted.
            feature_cols: Optional explicit list of feature columns to scale.
            exclude_cols: Optional columns to exclude from scaling.

        Returns:
            tuple[pd.DataFrame, Any]: Scaled DataFrame and fitted/used scaler.
        """
        if df.empty:
            return df.copy(), scaler

        scaled = df.copy()

        if feature_cols is not None:
            cols_to_scale = [
                col
                for col in feature_cols
                if col in scaled.columns and np.issubdtype(scaled[col].dtype, np.number)
            ]
        else:
            if exclude_cols is not None:
                excl = set(exclude_cols)
            else:
                excl = set(DEFAULT_META_COLS + DEFAULT_TARGET_COLS)

            numeric_cols = scaled.select_dtypes(include=[np.number]).columns
            cols_to_scale = [col for col in numeric_cols if col not in excl]

        if not cols_to_scale:
            return scaled, scaler

        # Scaler must only be fit on training data; val/test must strictly reuse fitted scaler
        # to avoid distribution leakage.
        if scaler is None:
            scaler = StandardScaler()
            scaled[cols_to_scale] = scaler.fit_transform(scaled[cols_to_scale])
        else:
            scaled[cols_to_scale] = scaler.transform(scaled[cols_to_scale])

        return scaled, scaler

    @staticmethod
    def make_time_windows(
        df: pd.DataFrame,
        window_size: int,
        step: int = 1,
        feature_cols: list[str] | None = None,
        exclude_cols: list[str] | None = None,
    ) -> np.ndarray:
        """Create overlapping time windows for sequential data (e.g. C-MAPSS sequences).

        Ensures windows do not cross vehicle boundaries and sorts chronologically.
        Only sensor features are windowed; targets and metadata are excluded by default.

        Args:
            df: Input DataFrame.
            window_size: Number of timesteps in each window.
            step: Timesteps to advance for next window.
            feature_cols: Explicit list of feature column names to include in window tensor.
            exclude_cols: Columns to exclude from windows.

        Returns:
            np.ndarray: A 3D numpy array of shape (num_windows, window_size, num_features).
        """
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")
        if step < 1:
            raise ValueError(f"step must be >= 1, got {step}")

        if feature_cols is not None:
            active_cols = [
                c
                for c in feature_cols
                if c in df.columns and np.issubdtype(df[c].dtype, np.number)
            ]
        else:
            if exclude_cols is not None:
                excl = set(exclude_cols)
            else:
                excl = set(DEFAULT_META_COLS + DEFAULT_TARGET_COLS)

            numeric_cols = df.select_dtypes(include=[np.number]).columns
            active_cols = [c for c in numeric_cols if c not in excl]

        n_features = len(active_cols)
        if df.empty or n_features == 0:
            return np.empty((0, window_size, n_features), dtype=np.float64)

        windows: list[np.ndarray] = []

        if "vehicle_id" in df.columns:
            for _, group in df.groupby("vehicle_id", sort=False):
                if "timestamp" in group.columns:
                    group = group.sort_values("timestamp")
                group_data = group[active_cols].to_numpy(dtype=np.float64)
                for i in range(0, len(group_data) - window_size + 1, step):
                    windows.append(group_data[i : i + window_size])
        else:
            ordered_df = (
                df.sort_values("timestamp") if "timestamp" in df.columns else df
            )
            group_data = ordered_df[active_cols].to_numpy(dtype=np.float64)
            for i in range(0, len(group_data) - window_size + 1, step):
                windows.append(group_data[i : i + window_size])

        # Preserve the documented 3D contract shape (num_windows, window_size, num_features)
        # even when no full window fits the sequences.
        if not windows:
            return np.empty((0, window_size, n_features), dtype=np.float64)

        return np.array(windows, dtype=np.float64)

    @staticmethod
    def train_val_test_split(
        df: pd.DataFrame,
        val_frac: float = 0.15,
        test_frac: float = 0.15,
        time_ordered: bool = True,
        timestamp_col: str = "timestamp",
        group_by_vehicle: bool = True,
        assume_sorted: bool = False,
        random_state: int = 42,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split the DataFrame into train, validation, and test sets.

        Defaults to time_ordered=True to prevent future data leakage in sequential telemetry.

        Args:
            df: Input DataFrame.
            val_frac: Fraction of data for validation.
            test_frac: Fraction of data for testing.
            time_ordered: If True, performs chronological sequential split.
            timestamp_col: Column name containing timestamp information.
            group_by_vehicle: If True and 'vehicle_id' present, splits each vehicle's
                timeline chronologically to prevent cross-vehicle temporal confounding.
            assume_sorted: If True and timestamp_col is missing, accepts input row order.
            random_state: Seed for random splits when time_ordered=False.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: (train, val, test) DataFrames.
        """
        if val_frac < 0.0 or test_frac < 0.0 or (val_frac + test_frac >= 1.0):
            raise ValueError(
                f"val_frac ({val_frac}) and test_frac ({test_frac}) must be non-negative "
                "and their sum strictly less than 1.0"
            )

        if df.empty:
            return df.copy(), df.copy(), df.copy()

        if time_ordered:
            has_timestamp = timestamp_col in df.columns
            if not has_timestamp and not assume_sorted:
                raise ValueError(
                    f"time_ordered=True requires '{timestamp_col}' column to enforce chronological "
                    "order. Pass assume_sorted=True only if rows are already verified to be chronological."
                )

            if "vehicle_id" in df.columns and group_by_vehicle:
                train_parts, val_parts, test_parts = [], [], []
                for _, group in df.groupby("vehicle_id", sort=False):
                    if has_timestamp:
                        group = group.sort_values(by=timestamp_col)
                    n = len(group)
                    n_train = int(n * (1.0 - val_frac - test_frac))
                    n_val = int(n * val_frac)

                    train_parts.append(group.iloc[:n_train])
                    val_parts.append(group.iloc[n_train : n_train + n_val])
                    test_parts.append(group.iloc[n_train + n_val :])

                train_df = (
                    pd.concat(train_parts, ignore_index=True)
                    if train_parts
                    else df.iloc[0:0].copy()
                )
                val_df = (
                    pd.concat(val_parts, ignore_index=True)
                    if val_parts
                    else df.iloc[0:0].copy()
                )
                test_df = (
                    pd.concat(test_parts, ignore_index=True)
                    if test_parts
                    else df.iloc[0:0].copy()
                )
            else:
                sorted_df = (
                    df.sort_values(by=timestamp_col).reset_index(drop=True)
                    if has_timestamp
                    else df.reset_index(drop=True)
                )
                n_total = len(sorted_df)
                n_train = int(n_total * (1.0 - val_frac - test_frac))
                n_val = int(n_total * val_frac)

                train_df = sorted_df.iloc[:n_train].copy()
                val_df = sorted_df.iloc[n_train : n_train + n_val].copy()
                test_df = sorted_df.iloc[n_train + n_val :].copy()
        else:
            from sklearn.model_selection import train_test_split

            train_df, temp_df = train_test_split(
                df,
                test_size=(val_frac + test_frac),
                shuffle=True,
                random_state=random_state,
            )

            val_ratio = val_frac / (val_frac + test_frac)
            val_df, test_df = train_test_split(
                temp_df, train_size=val_ratio, shuffle=True, random_state=random_state
            )

            train_df = train_df.reset_index(drop=True)
            val_df = val_df.reset_index(drop=True)
            test_df = test_df.reset_index(drop=True)

        return train_df, val_df, test_df
