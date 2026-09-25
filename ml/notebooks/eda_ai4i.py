"""EDA for the AI4I predictive-maintenance dataset (failure classification).

Run from the repo root:
    python ml/notebooks/01_eda_ai4i.py [--csv PATH] [--no-show]

What this script does:
  1. Loads data through the production loader `load_ai4i()` (ml/src/data/loaders.py).
  2. Cleans it through `PreProcessing.clean()` (ml/src/data/preprocessing.py).
  3. Profiles shape, dtypes, missing values, duplicates, and class imbalance.
  4. Analyses the target (`failure`) and its failure-mode sub-labels.
  5. Plots univariate + bivariate distributions and a correlation matrix.
  6. Prototypes candidate automotive features and checks leakage/outliers.
  7. Prints concrete feature recommendations for the XGBoost classifier,
     Isolation Forest detector, and health-score weights.

NOTE (data honesty): AI4I is an industrial milling-machine benchmark, NOT real
vehicle telemetry. Column names below keep the loader's automotive aliases, but
conclusions transfer as *technique validation* only (per .agents/CONTEXT.md).

NOTE (loader mismatch, flagged not hidden): the checked-in CSV at
data/failure_classification/raw/predictive_maintenance.csv uses short headers
('Rotational speed', 'Torque', ...) while `load_ai4i()` maps long headers
('Rotational speed [rpm]', ...). Only 'Machine failure' -> 'failure' matches,
so this script resolves both naming variants via `_col()` instead of assuming
the rename happened. Fix the loader mapping separately; EDA must not silently
depend on whichever variant is present.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend: script must run headless/CI-safe.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --- Resolve imports so the script runs from repo root OR ml/ (no hardcoded abs paths). ---
THIS_FILE = Path(__file__).resolve()
REPO_ROOT = (
    THIS_FILE.parents[2]
    if THIS_FILE.parents[2].name != "notebooks"
    else THIS_FILE.parents[2]
)
# Layout is <root>/ml/notebooks/01_eda_ai4i.py -> ml dir is parent of notebooks.
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

# Canonical sensor columns in both naming variants (loader alias -> raw CSV header).
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
FAILURE_MODES = ["TWF", "HDF", "PWF", "OSF", "RNF"]  # Sub-labels present in raw CSV.


def _col(df: pd.DataFrame, canonical: str) -> str:
    """Return the actual column name present in df for a canonical sensor."""
    for alias in COLUMN_ALIASES[canonical]:
        if alias in df.columns:
            return alias
    raise KeyError(f"No variant of {canonical!r} found. Columns: {list(df.columns)}")


def _savefig(name: str, no_show: bool = True) -> None:
    """Save current figure to the reports dir; optionally also display."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(FIG_DIR / name, dpi=150)
    if not no_show:
        plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# 1. Load + initial profile
# ---------------------------------------------------------------------------
def load_and_profile(csv_path: Path) -> pd.DataFrame:
    """Load via production loader and print shape/dtypes/missing/duplicates."""
    # Use the production loader so EDA reflects what training will actually see.
    df = load_ai4i(csv_path)
    print(
        f"[load] rows={len(df)} cols={len(df.columns)} source={df['source'].unique().tolist()}"
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


# ---------------------------------------------------------------------------
# 2. Clean via production preprocessing + verify
# ---------------------------------------------------------------------------
def clean_and_verify(df: pd.DataFrame) -> pd.DataFrame:
    """Run PreProcessing.clean() and confirm no rows lost / NaNs introduced."""
    # clean() sorts by vehicle_id/timestamp and imputes sensor dropouts; targets
    # ('failure','rul') are excluded from imputation by default to avoid label fabrication.
    cleaned, stats = PreProcessing.clean(df, return_imputer_stats=True)
    print(
        f"\n[clean] rows {len(df)} -> {len(cleaned)} | imputer stats: {stats or 'none needed'}"
    )
    assert len(cleaned) == len(df.drop_duplicates()), "Unexpected row loss in clean()"
    return cleaned


# ---------------------------------------------------------------------------
# 3. Target + failure-mode analysis
# ---------------------------------------------------------------------------
def analyse_target(df: pd.DataFrame) -> None:
    """Quantify imbalance: overall failure rate, per-mode counts, Type breakdown."""
    fail = _col(df, "failure")
    rate = float(df[fail].mean())
    print(f"\n[target] failure rate = {rate:.4f} ({int(df[fail].sum())}/{len(df)})")
    # ~3.4% positive: accuracy is misleading; downstream classifier must report
    # precision/recall/F1 and use class_weight/scale_pos_weight (per AGENTS.md).

    # Failure-mode sub-labels: check whether they partition the positive class.
    modes = [m for m in FAILURE_MODES if m in df.columns]
    if modes:
        print("\n--- failure-mode counts (share of all failures) ---")
        n_fail = max(int(df[fail].sum()), 1)
        for m in modes:
            print(f"{m}: {int(df[m].sum())} ({df[m].sum() / n_fail:.1%} of failures)")
        # Leakage check: if OR(modes) == failure exactly, modes must be EXCLUDED
        # from classifier features (they are the label decomposed, not inputs).
        union = df[modes].max(axis=1)
        print(
            f"[leakage] P(union(modes) == failure) = {(union == df[fail]).mean():.4f}"
        )

    # Machine type (L/M/H) vs failure rate: categorical signal worth one-hot encoding.
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
    """Bar charts: overall imbalance + per-mode counts (log scale for rare modes)."""
    fail = _col(df, "failure")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    # Left: binary imbalance (the reason accuracy alone is untrustworthy here).
    df[fail].value_counts().sort_index().plot(kind="bar", rot=0, ax=axes[0])
    axes[0].set_title("Class balance (0=ok, 1=failure)")
    axes[0].set_ylabel("count")

    # Right: which physical failure mode dominates (guides per-mode recall goals).
    modes = [m for m in FAILURE_MODES if m in df.columns]
    if modes:
        df[modes].sum().plot(kind="bar", rot=0, ax=axes[1], logy=True)
        axes[1].set_title("Failure-mode counts (log scale)")
    fig.suptitle("AI4I target distribution")
    _savefig("01_target_balance.png")


# ---------------------------------------------------------------------------
# 4. Univariate sensor distributions
# ---------------------------------------------------------------------------
def plot_univariate(df: pd.DataFrame) -> None:
    """Histograms for each sensor: shape, skew, and candidate outliers."""
    sensors = [
        _col(df, c)
        for c in (
            "engine_rpm",
            "engine_load",
            "coolant_temp",
            "intake_air_temp",
            "vibration",
        )
    ]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, col in zip(axes.flat, sensors):
        # 50 bins is enough to reveal skew/bimodality at n=10k without noise.
        df[col].hist(bins=50, ax=ax)
        ax.set_title(col)
        ax.set_ylabel("count")
    axes.flat[-1].axis("off")
    fig.suptitle("Sensor distributions (raw units)")
    _savefig("02_univariate_hist.png")

    print("\n--- skew / kurtosis (guides scaling + transform choice) ---")
    print(df[sensors].agg(["skew", "kurtosis"]).T.to_string())


# ---------------------------------------------------------------------------
# 5. Bivariate: sensor behaviour split by failure + correlations
# ---------------------------------------------------------------------------
def plot_by_class(df: pd.DataFrame) -> None:
    """Boxplots per sensor split by failure: which sensors separate the classes."""
    fail = _col(df, "failure")
    sensors = [
        _col(df, c)
        for c in (
            "engine_rpm",
            "engine_load",
            "coolant_temp",
            "intake_air_temp",
            "vibration",
        )
    ]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, col in zip(axes.flat, sensors):
        # Boxplot per class directly shows median shift / spread change on failure.
        data = [df.loc[df[fail] == 0, col], df.loc[df[fail] == 1, col]]
        ax.boxplot(
            data, tick_labels=["ok", "fail"], showfliers=False
        )  # Hide fliers: dedicated outlier plot below.
        ax.set_title(f"{col} by class")
    axes.flat[-1].axis("off")
    fig.suptitle("Sensor separation between ok vs failure")
    _savefig("04_box_by_class.png")

    print("\n--- mean sensor value: ok vs failure (directional check for XAI) ---")
    print(df.groupby(fail)[sensors].mean().T.to_string())


def plot_correlation(df: pd.DataFrame) -> None:
    """Pearson correlation heatmap (matplotlib only): redundancy + leakage screen."""
    sensors = [
        _col(df, c)
        for c in (
            "engine_rpm",
            "engine_load",
            "coolant_temp",
            "intake_air_temp",
            "vibration",
        )
    ]
    fail = _col(df, "failure")
    corr = df[sensors + [fail]].corr(numeric_only=True)

    # |r| > 0.9 between two inputs => drop/merge one; |r| ~ 1.0 with `failure`
    # => suspected label leakage, investigate before training.
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


# ---------------------------------------------------------------------------
# 6. Candidate automotive features (prototype only -- NOT written to df)
# ---------------------------------------------------------------------------
def prototype_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build physics-motivated candidates and test their failure separation."""
    rpm = _col(df, "engine_rpm")
    load = _col(df, "engine_load")
    proc = _col(df, "coolant_temp")
    air = _col(df, "intake_air_temp")
    wear = _col(df, "vibration")
    fail = _col(df, "failure")

    feats = pd.DataFrame(index=df.index)
    # temp_diff: process-minus-ambient isolates self-heating from weather; the raw
    # AI4I set is known to separate failures on this derived channel.
    feats["temp_diff"] = df[proc] - df[air]
    # power_proxy: rpm * torque ~ mechanical power; strain indicator for OSF/PWF modes.
    feats["power_proxy"] = df[rpm] * df[load]
    # wear_rate proxy: tool wear accumulates per row; high absolute wear ~= end of life.
    feats["wear"] = df[wear]
    feats["failure"] = df[fail].values

    print("\n--- candidate feature separation (mean ok vs failure) ---")
    print(feats.groupby("failure").mean().T.to_string())

    # Scatter: temp_diff vs power coloured by class -- visual check that the
    # derived space separates failures better than any single raw sensor.
    fig, ax = plt.subplots(figsize=(7, 5))
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

    # Binned failure rate vs tool wear: monotonic rise justifies wear as the
    # strongest single predictor and a future RUL proxy.
    feats["wear_bin"] = pd.qcut(feats["wear"], q=10, duplicates="drop")
    rate_by_wear = feats.groupby("wear_bin", observed=True)["failure"].mean()
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    rate_by_wear.plot(kind="bar", ax=ax2)
    ax2.set_title("Failure rate by tool-wear decile")
    ax2.set_ylabel("failure rate")
    _savefig("07_wear_binned_rate.png")
    print("\n--- failure rate by wear decile ---")
    print(rate_by_wear.to_string())
    return feats


# ---------------------------------------------------------------------------
# 7. Outlier screen (IQR per sensor, reported not dropped)
# ---------------------------------------------------------------------------
def screen_outliers(df: pd.DataFrame) -> None:
    """Count IQR outliers per sensor; EDA reports them, training decides handling."""
    # IQR rule (not z-score): robust to the heavy skew seen in rpm/torque.
    sensors = [
        _col(df, c)
        for c in (
            "engine_rpm",
            "engine_load",
            "coolant_temp",
            "intake_air_temp",
            "vibration",
        )
    ]
    print("\n--- IQR outlier share per sensor (inform, do not drop yet) ---")
    for col in sensors:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        share = ((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).mean()
        print(f"{col}: {share:.3%}")


# ---------------------------------------------------------------------------
# 8. Recommendations (the actual output feature-engineering will consume)
# ---------------------------------------------------------------------------
def print_recommendations() -> None:
    print(
        """
=== FEATURE RECOMMENDATIONS (AI4I -> DrivePulse) ===
1. Classifier inputs (XGBoost, notebook 04): temp_diff, power_proxy, Tool wear,
   Torque, Rotational speed, both temperatures, one-hot(Type). EXCLUDE TWF/HDF/
   PWF/OSF/RNF (label decomposition = leakage) from features; keep for scoring.
2. Imbalance: ~3.4% positive -> scale_pos_weight ~= 28, stratified/time-ordered
   splits, report precision/recall/F1 (never accuracy alone); missed failure >>
   false alarm cost framing.
3. Anomaly detector (notebook 03): fit Isolation Forest on ok-only rows with the
   same numeric features standardised via PreProcessing.scale (fit on train only).
4. Health score: weight Tool wear + temp_diff highest (strongest failure
   separation); surface per-sensor deductions for the XAI panel.
5. Loader fix needed: align load_ai4i() mapping with short CSV headers so the
   automotive aliases actually apply; re-run this EDA after the fix.
6. Caveat: AI4I rows are i.i.d. machine snapshots, not vehicle time series --
   no rolling/rate-of-change features are valid here; those belong to C-MAPSS /
   simulator streams (notebook 02).
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

    df = load_and_profile(args.csv)  # Step 1: production loader + profile.
    df = clean_and_verify(df)  # Step 2: production cleaning + verify.
    plot_target_bars(df)  # Imbalance visualisation.
    analyse_target(df)  # Rates, modes, leakage check, Type split.
    plot_univariate(df)  # Per-sensor distributions.
    plot_by_class(df)  # Class-conditional separation.
    plot_correlation(df)  # Redundancy / leakage screen.
    prototype_features(df)  # Candidate features + separation proof.
    screen_outliers(df)  # IQR outlier census.
    print_recommendations()  # Actionable handoff to notebooks 03/04.
    print(f"\n[done] figures saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
