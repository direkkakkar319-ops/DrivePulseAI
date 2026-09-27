"""EDA for the AI4I failure-classification data.

Usage:
    python ml/notebooks/eda_ai4i.py [--csv PATH] [--no-show]

AI4I is an industrial benchmark, not vehicle data, so read this as technique
validation. The checked-in CSV uses short headers ('Torque', ...) while
load_ai4i() expects long ones ('Torque [Nm]', ...), so _col() accepts both.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
ML_DIR = THIS_FILE.parents[1]
for candidate in (ML_DIR, REPO_ROOT / "ml"):
    if (candidate / "src" / "data" / "loaders.py").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from src.data.loaders import load_ai4i
from src.data.preprocessing import PreProcessing

DEFAULT_CSV = (
    REPO_ROOT / "data" / "failure_classification" / "raw" / "predictive_maintenance.csv"
)
FIG_DIR = REPO_ROOT / "ml" / "reports" / "figures" / "ai4i"

COLUMN_ALIASES: dict[str, list[str]] = {
    "engine_rpm": ["engine_rpm", "Rotational speed [rpm]", "Rotational speed"],
    "engine_load": ["engine_load_pct", "Torque [Nm]", "Torque"],
    "coolant_temp": [
        "coolant_temp_c",
        "Process temperature [K]",
        "Process temperature",
    ],
    "intake_air_temp": ["intake_air_temp_c", "Air temperature [K]", "Air temperature"],
    "vibration": ["vibration", "Tool wear [min]", "Tool wear"],
    "failure": ["failure", "Machine failure"],
    "machine_type": ["machine_type", "Type"],
}
FAILURE_MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]

SENSORS = ("engine_rpm", "engine_load", "coolant_temp", "intake_air_temp", "vibration")


def _col(df: pd.DataFrame, canonical: str) -> str:
    for alias in COLUMN_ALIASES[canonical]:
        if alias in df.columns:
            return alias
    raise KeyError(f"No variant of {canonical!r} found. Columns: {list(df.columns)}")


def _savefig(name: str, no_show: bool = True) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(FIG_DIR / name, dpi=150)
    if not no_show:
        plt.show()
    plt.close()


def _sensors(df: pd.DataFrame) -> list[str]:
    return [_col(df, c) for c in SENSORS]


def load_and_profile(csv_path: Path) -> pd.DataFrame:
    df = load_ai4i(csv_path)
    print(
        f"[load] rows={len(df)} cols={len(df.columns)} "
        f"source={df['source'].unique().tolist()}"
    )
    print("\n--- dtypes ---")
    print(df.dtypes.to_string())
    print("\n--- head ---")
    print(df.head(5).to_string())
    print("\n--- missing values ---")
    missing = df.isnull().sum()
    print(missing.to_string() if missing.sum() else "none")
    print(f"\n--- duplicated rows: {int(df.duplicated().sum())} ---")
    print("\n--- describe (numeric) ---")
    print(df.describe(include=[np.number]).T.to_string())
    return df


def clean_and_verify(df: pd.DataFrame) -> pd.DataFrame:
    # Targets are left out of imputation so labels never get fabricated.
    cleaned, stats = PreProcessing.clean(df, return_imputer_stats=True)
    print(
        f"\n[clean] rows {len(df)} -> {len(cleaned)} "
        f"| imputer stats: {stats or 'none needed'}"
    )
    assert len(cleaned) == len(df.drop_duplicates()), "Unexpected row loss in clean()"
    return cleaned


def analyse_target(df: pd.DataFrame) -> None:
    fail = _col(df, "failure")
    rate = float(df[fail].mean())
    print(f"\n[target] failure rate = {rate:.4f} ({int(df[fail].sum())}/{len(df)})")

    modes = [m for m in FAILURE_MODES if m in df.columns]
    if modes:
        print("\n--- failure-mode counts (share of all failures) ---")
        n_fail = max(int(df[fail].sum()), 1)
        for m in modes:
            print(f"{m}: {int(df[m].sum())} ({df[m].sum() / n_fail:.1%} of failures)")
        # Modes reconstruct the label, so they must stay out of the features.
        union = df[modes].max(axis=1)
        print(
            f"[leakage] P(union(modes) == failure) = {(union == df[fail]).mean():.4f}"
        )

    try:
        tcol = _col(df, "machine_type")
        ct = pd.crosstab(df[tcol], df[fail], normalize="index")
        print("\n--- failure rate by machine Type ---")
        print(ct.to_string())
        ax = ct.plot(kind="bar", rot=0, title="Failure rate by machine Type")
        ax.set_ylabel("share")
        _savefig("03_failure_by_type.png")
    except KeyError:
        print("[target] no machine-Type column; skipping Type breakdown.")


def plot_target_bars(df: pd.DataFrame) -> None:
    fail = _col(df, "failure")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    df[fail].value_counts().sort_index().plot(kind="bar", rot=0, ax=axes[0])
    axes[0].set_title("Class balance (0=ok, 1=failure)")
    axes[0].set_ylabel("count")

    modes = [m for m in FAILURE_MODES if m in df.columns]
    if modes:
        df[modes].sum().plot(kind="bar", rot=0, ax=axes[1], logy=True)
        axes[1].set_title("Failure-mode counts (log scale)")
    fig.suptitle("AI4I target distribution")
    _savefig("01_target_balance.png")


def plot_univariate(df: pd.DataFrame) -> None:
    sensors = _sensors(df)
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, col in zip(axes.flat, sensors):
        df[col].hist(bins=50, ax=ax)
        ax.set_title(col)
        ax.set_ylabel("count")
    axes.flat[-1].axis("off")
    fig.suptitle("Sensor distributions (raw units)")
    _savefig("02_univariate_hist.png")

    print("\n--- skew / kurtosis ---")
    print(df[sensors].agg(["skew", "kurtosis"]).T.to_string())


def plot_by_class(df: pd.DataFrame) -> None:
    fail = _col(df, "failure")
    sensors = _sensors(df)
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, col in zip(axes.flat, sensors):
        data = [df.loc[df[fail] == 0, col], df.loc[df[fail] == 1, col]]
        ax.boxplot(data, tick_labels=["ok", "fail"], showfliers=False)
        ax.set_title(f"{col} by class")
    axes.flat[-1].axis("off")
    fig.suptitle("Sensor separation between ok vs failure")
    _savefig("04_box_by_class.png")

    print("\n--- mean sensor value: ok vs failure ---")
    print(df.groupby(fail)[sensors].mean().T.to_string())


def plot_correlation(df: pd.DataFrame) -> None:
    sensors = _sensors(df)
    fail = _col(df, "failure")
    corr = df[sensors + [fail]].corr(numeric_only=True)

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(corr.columns)), corr.columns)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(
                j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=8
            )
    ax.set_title("Pearson correlation (sensors + failure)")
    fig.colorbar(im, ax=ax, label="r")
    _savefig("05_correlation.png")
    print("\n--- correlation with failure (ranked) ---")
    print(corr[fail].drop(fail).sort_values(key=np.abs, ascending=False).to_string())


def prototype_features(df: pd.DataFrame) -> pd.DataFrame:
    rpm = _col(df, "engine_rpm")
    load = _col(df, "engine_load")
    proc = _col(df, "coolant_temp")
    air = _col(df, "intake_air_temp")
    wear = _col(df, "vibration")
    fail = _col(df, "failure")

    feats = pd.DataFrame(index=df.index)
    feats["temp_diff"] = df[proc] - df[air]
    feats["power_proxy"] = df[rpm] * df[load]
    feats["wear"] = df[wear]
    feats["failure"] = df[fail].values

    print("\n--- candidate feature separation (mean ok vs failure) ---")
    print(feats.groupby("failure").mean().T.to_string())

    _fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(
        feats.loc[feats.failure == 0, "power_proxy"],
        feats.loc[feats.failure == 0, "temp_diff"],
        s=4,
        alpha=0.3,
        label="ok",
    )
    ax.scatter(
        feats.loc[feats.failure == 1, "power_proxy"],
        feats.loc[feats.failure == 1, "temp_diff"],
        s=10,
        alpha=0.8,
        label="fail",
    )
    ax.set_xlabel("power_proxy (rpm * torque)")
    ax.set_ylabel("temp_diff (process - air)")
    ax.set_title("Derived space: power vs temperature rise")
    ax.legend()
    _savefig("06_derived_scatter.png")

    # Failure rate jumps past ~195 min wear, flat below it.
    feats["wear_bin"] = pd.qcut(feats["wear"], q=10, duplicates="drop")
    rate_by_wear = feats.groupby("wear_bin", observed=True)["failure"].mean()
    _fig2, ax2 = plt.subplots(figsize=(8, 4))
    rate_by_wear.plot(kind="bar", ax=ax2)
    ax2.set_title("Failure rate by tool-wear decile")
    ax2.set_ylabel("failure rate")
    _savefig("07_wear_binned_rate.png")
    print("\n--- failure rate by wear decile ---")
    print(rate_by_wear.to_string())
    return feats


def screen_outliers(df: pd.DataFrame) -> None:
    sensors = _sensors(df)
    print("\n--- IQR outlier share per sensor ---")
    for col in sensors:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        share = ((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).mean()
        print(f"{col}: {share:.3%}")


def print_recommendations() -> None:
    print(
        """
=== FEATURE RECOMMENDATIONS (AI4I -> DrivePulse) ===
1. Classifier inputs: temp_diff, power_proxy, Tool wear, Torque,
   Rotational speed, both temperatures, one-hot(Type). Keep TWF/HDF/PWF/
   OSF/RNF out of the features, they are the label split apart.
2. 3.4% positive, so use scale_pos_weight ~= 28 and judge on
   precision/recall/F1, not accuracy. A missed failure costs more
   than a false alarm.
3. Anomaly detector: fit Isolation Forest on ok-only rows, standardize
   with PreProcessing.scale fitted on train.
4. Health score: weight Tool wear and temp_diff highest. Show each
   sensor deduction next to the score.
5. Loader still needs its header mapping fixed to the short CSV names.
   Re-run this after that fix.
6. AI4I rows are snapshots, not a time series, so no rolling features
   here. Those belong to the C-MAPSS/simulator side.
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EDA for AI4I failure-classification data."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Path to predictive_maintenance.csv",
    )
    parser.add_argument(
        "--no-show", action="store_true", help="Only save figures (default behaviour)."
    )
    args = parser.parse_args()

    if not args.csv.exists():
        sys.exit(f"CSV not found: {args.csv} (pass --csv PATH)")

    df = load_and_profile(args.csv)
    df = clean_and_verify(df)
    plot_target_bars(df)
    analyse_target(df)
    plot_univariate(df)
    plot_by_class(df)
    plot_correlation(df)
    prototype_features(df)
    screen_outliers(df)
    print_recommendations()
    print(f"\n[done] figures saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
