"""Derived features for DrivePulse AI datasets."""

from __future__ import annotations

import pandas as pd


class FeatureEngineering:
    """Derived features. Inputs are never mutated."""

    @staticmethod
    def add_aps_features(df: pd.DataFrame) -> pd.DataFrame:
        """Adds per-row missing count plus sum/mean/max per prefix group.

        Takes the loaded frame WITH NaNs: n_missing needs the pre-imputation
        state (APS positives miss ~29 cells/row vs ~14 for negatives).
        Group aggregates skip NaN; min_count=1 keeps fully-missing groups
        NaN for PreProcessing.clean to impute.
        """
        out = df.copy()
        meta = ("class", "failure", "vehicle_id", "source")
        feats = [c for c in out.columns if c not in meta]
        out["n_missing"] = out[feats].isna().sum(axis=1)
        groups: dict[str, list[str]] = {}
        for c in feats:
            groups.setdefault(c.split("_")[0], []).append(c)
        for prefix, cols in sorted(groups.items()):
            if len(cols) < 2:
                continue
            g = out[cols]
            out[f"{prefix}_sum"] = g.sum(axis=1, min_count=1)
            out[f"{prefix}_mean"] = g.mean(axis=1, skipna=True)
            out[f"{prefix}_max"] = g.max(axis=1, skipna=True)
        return out

    @staticmethod
    def aps_model_columns(df: pd.DataFrame) -> list[str]:
        """Numeric classifier inputs. Call after add_aps_features."""
        exclude = {"class", "failure", "rul", "vehicle_id", "source"}
        return [
            c
            for c in df.columns
            if c not in exclude and pd.api.types.is_numeric_dtype(df[c])
        ]
