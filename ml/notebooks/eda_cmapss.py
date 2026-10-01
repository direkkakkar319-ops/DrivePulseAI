"""EDA for the C-MAPSS RUL-regression data (NASA turbofan degradation).

Usage:
    python ml/notebooks/eda_cmapss.py [--data-dir PATH] [--subset SUBSET] [--no-show]

Loads data through src.data.loaders.load_cmapss so the analysis matches exactly
what the RUL model will train on (mapped columns + ``rul`` label). Figures and
a markdown report are written to ml/reports/figures/cmapss/.

Only matplotlib is used for plots (seaborn is not a project dependency),
mirroring the style of ml/notebooks/eda_ai4i.py.
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

from src.data.loaders import SENSOR_NAMES, load_cmapss  # noqa: E402
from src.data.preprocessing import PreProcessing  # noqa: E402

from sklearn.linear_model import LinearRegression  # noqa: E402

DEFAULT_DATA_DIR = REPO_ROOT / "data" / "RUL_score" / "raw"
FIG_DIR = REPO_ROOT / "ml" / "reports" / "figures" / "cmapss"

SENSORS = list(SENSOR_NAMES.values())
SETTINGS = ["setting_1", "setting_2", "setting_3"]
NUMBERS = {v: k for k, v in SENSOR_NAMES.items()}


def _sensors(df: pd.DataFrame) -> list[str]:
    return [c for c in SENSORS if c in df.columns]


# Subset operating envelope (NASA docs): FD001/FD003 = 1 condition,
# FD002/FD004 = 6 conditions; FD003/FD004 have 2 fault modes vs 1.
SUBSET_INFO = {
    "FD001": "1 operating condition, 1 fault mode (HPC)",
    "FD002": "6 operating conditions, 1 fault mode (HPC)",
    "FD003": "1 operating condition, 2 fault modes (HPC + fan)",
    "FD004": "6 operating conditions, 2 fault modes (HPC + fan)",
}

REPORT_LINES: list[str] = []
SAVED_FIGS: set[str] = set()


def log(line: str = "") -> None:
    print(line)
    REPORT_LINES.append(line)


def _savefig(name: str, no_show: bool = True) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(FIG_DIR / name, dpi=150)
    if not no_show:
        plt.show()
    plt.close()
    SAVED_FIGS.add(name)


def load_and_profile(data_dir: Path, subset: str) -> pd.DataFrame:
    df = load_cmapss(data_dir, subset=subset)
    log(f"[load] rows={len(df)} cols={len(df.columns)} subset={subset}")
    log(f"[load] columns: {list(df.columns)}")
    log("\n--- dtypes ---")
    log(df.dtypes.to_string())
    log("\n--- head ---")
    log(df.head(5).to_string())
    log("\n--- missing values ---")
    missing = df.isnull().sum()
    log(missing.to_string() if missing.sum() else "none")
    log(f"\n--- duplicated rows: {int(df.duplicated().sum())} ---")
    log("\n--- describe (numeric) ---")
    log(df.describe(include=[np.number]).T.to_string())
    log("\n--- rows / engines per subset ---")
    log(
        df.groupby("subset")
        .agg(rows=("rul", "size"), engines=("vehicle_id", "nunique"))
        .to_string()
    )
    return df


def clean_and_verify(df: pd.DataFrame) -> pd.DataFrame:
    # RUL is the label: excluded from imputation so targets are never fabricated.
    cleaned, stats = PreProcessing.clean(df, return_imputer_stats=True)
    log(
        f"\n[clean] rows {len(df)} -> {len(cleaned)} "
        f"| imputer stats: {stats or 'none needed'}"
    )
    assert len(cleaned) == len(df.drop_duplicates()), "Unexpected row loss in clean()"
    return cleaned


def analyse_target(df: pd.DataFrame) -> None:
    log("\n--- RUL summary (all subsets) ---")
    log(df["rul"].describe().to_string())
    log("\n--- RUL summary by subset ---")
    log(df.groupby("subset")["rul"].describe().to_string())
    life = df.groupby(["subset", "vehicle_id"])["timestamp"].max()
    log("\n--- engine life length (cycles) by subset ---")
    log(life.groupby("subset").describe().to_string())

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    df["rul"].hist(bins=60, ax=axes[0])
    axes[0].set_title("RUL distribution (all subsets)")
    axes[0].set_xlabel("RUL (cycles)")
    axes[0].set_ylabel("count")
    life.groupby("subset").mean().plot(kind="bar", rot=0, ax=axes[1])
    axes[1].set_title("Mean engine life per subset")
    axes[1].set_ylabel("cycles")
    fig.suptitle("C-MAPSS target overview")
    _savefig("01_rul_overview.png")

    fig2, axes2 = plt.subplots(1, 2, figsize=(12, 4))
    life.hist(bins=40, ax=axes2[0])
    axes2[0].set_title("Engine life-length distribution")
    axes2[0].set_xlabel("max cycles per engine")
    df.boxplot(column="rul", by="subset", ax=axes2[1])
    axes2[1].set_title("RUL spread by subset")
    plt.suptitle("")  # drop pandas' default "rul by subset" suptitle
    _savefig("02_life_and_rul_by_subset.png")

    # Censoring check: every engine runs to failure, so RUL=0 exists per engine.
    n_zero = int((df["rul"] == 0).sum())
    n_eng = int(df["vehicle_id"].nunique())
    log(f"\n[censoring] rows with RUL=0: {n_zero} over {n_eng} engines "
        f"(expect one per engine if all run to failure)")


def plot_operating_conditions(df: pd.DataFrame) -> None:
    log("\n--- distinct operating-setting values per subset ---")
    for sub, g in df.groupby("subset"):
        nunique = {c: int(g[c].nunique()) for c in SETTINGS}
        log(f"{sub} ({SUBSET_INFO[sub]}): {nunique}")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, col in zip(axes, SETTINGS):
        for sub, g in sorted(df.groupby("subset")):
            g[col].hist(bins=40, ax=ax, alpha=0.5, label=sub, density=True)
        ax.set_title(col)
        ax.legend(fontsize=8)
    fig.suptitle("Operating-setting distributions per subset")
    _savefig("03_settings_hist.png")

    fig2, ax2 = plt.subplots(figsize=(6, 5))
    for sub, g in sorted(df.groupby("subset")):
        ax2.scatter(
            g["setting_1"].sample(min(3000, len(g)), random_state=0),
            g["setting_2"].sample(min(3000, len(g)), random_state=0),
            s=4, alpha=0.4, label=sub,
        )
    ax2.set_xlabel("setting_1")
    ax2.set_ylabel("setting_2")
    ax2.set_title("Operating envelope: setting_1 vs setting_2")
    ax2.legend()
    _savefig("04_settings_scatter.png")
    log("[conditions] FD002/FD004 spread over 6 clusters -> models must "
        "condition on settings (or normalise per condition); FD001/FD003 "
        "collapse to one point.")


def screen_sensor_variance(df: pd.DataFrame) -> None:
    sensors = _sensors(df)
    std_all = df[sensors].std()
    log("\n--- sensor std (all data, ranked) ---")
    log(std_all.sort_values().to_string())
    constant = std_all[std_all == 0.0].index.tolist()
    log(f"\n[constant] zero-variance sensors (all data): {constant or 'none'}")

    per_sub = df.groupby("subset")[sensors].std()
    log("\n--- zero-variance sensors per subset ---")
    for sub in per_sub.index:
        const = per_sub.columns[per_sub.loc[sub] == 0.0].tolist()
        log(f"{sub}: {const or 'none'}")
    # Near-constant: coefficient of variation ~ 0 (mean >> std).
    cv = (std_all / df[sensors].mean().abs()).sort_values()
    near_const = cv[cv < 1e-4].index.tolist()
    log("\n--- coefficient of variation (lowest 8) ---")
    log(cv.head(8).to_string())
    log(f"[near-constant] CV < 1e-4: {near_const or 'none'}")

    fig, ax = plt.subplots(figsize=(10, 4))
    std_all.sort_values().plot(kind="bar", ax=ax)
    ax.set_title("Sensor std (all data, ascending) — flat bars carry no signal")
    ax.set_ylabel("std")
    _savefig("05_variance_screen.png")


def plot_univariate(df: pd.DataFrame) -> None:
    sensors = _sensors(df)
    fig, axes = plt.subplots(4, 6, figsize=(15, 10))
    for ax, col in zip(axes.flat, sensors + SETTINGS):
        df[col].hist(bins=50, ax=ax)
        ax.set_title(col, fontsize=9)
    for ax in axes.flat[len(sensors) + len(SETTINGS):]:
        ax.axis("off")
    fig.suptitle("Raw sensor / setting distributions (all subsets)")
    _savefig("06_univariate_hist.png")

    log("\n--- skew / kurtosis (sensors) ---")
    log(df[sensors].agg(["skew", "kurtosis"]).T.to_string())


def plot_degradation(df: pd.DataFrame) -> None:
    # Engines with the longest lives show the full healthy->fault arc.
    life = df.groupby("vehicle_id")["timestamp"].max().sort_values(ascending=False)
    sample_ids = life.head(4).index.tolist()
    log(f"\n[trajectories] sample engines (longest-lived): {sample_ids}")
    log("[trend] the FD004 engine (6 conditions) oscillates between operating "
        "points while FD003 engines (1 condition) degrade monotonically. Raw "
        "levels mix regime jumps with wear - normalise per condition.")

    trending = ["T24", "T30", "T50", "P30", "Ps30", "phi", "NRc", "BPR"]
    fig, axes = plt.subplots(2, 4, figsize=(15, 7))
    for ax, col in zip(axes.flat, trending):
        for vid in sample_ids:
            g = df[df["vehicle_id"] == vid].sort_values("timestamp")
            ax.plot(g["timestamp"].values, g[col].values, lw=1, label=vid[-8:])
        ax.set_title(f"{col} ({NUMBERS[col]})", fontsize=9)
        ax.set_xlabel("cycle")
    axes.flat[0].legend(fontsize=7)
    fig.suptitle("Sensor trajectories over engine life (monotonic = RUL signal)")
    _savefig("07_degradation_trajectories.png")

    # Mean sensor value per RUL bin: monotonic curves confirm degradation signal.
    df["_rul_bin"] = (df["rul"] // 10 * 10).astype(int)
    means = df.groupby("_rul_bin")[trending].mean().sort_index()
    fig2, axes2 = plt.subplots(2, 4, figsize=(15, 7))
    for ax, col in zip(axes2.flat, trending):
        ax.plot(means.index.values, means[col].values, marker=".", ms=3)
        ax.set_title(f"{col} ({NUMBERS[col]}) vs RUL", fontsize=9)
        ax.set_xlabel("RUL")
        ax.invert_xaxis()  # time flows right -> left as RUL shrinks
    fig2.suptitle("Mean sensor value vs RUL (10-cycle bins, inverted axis = ageing)")
    _savefig("08_sensor_vs_rul.png")
    df.drop(columns=["_rul_bin"], inplace=True)

    log("\n--- corr(sensor, RUL) ranked by |r| ---")
    corr_rul = df[_sensors(df) + ["rul"]].corr(numeric_only=True)["rul"].drop("rul")
    log(corr_rul.sort_values(key=np.abs, ascending=False).to_string())


def plot_correlation(df: pd.DataFrame) -> None:
    sensors = _sensors(df)
    cols = sensors + ["rul"]
    corr = df[cols].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(cols)), cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(cols)), cols, fontsize=8)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{corr.values[i, j]:.1f}",
                    ha="center", va="center", fontsize=6)
    ax.set_title("Pearson correlation (sensors + RUL)")
    fig.colorbar(im, ax=ax, label="r")
    _savefig("09_correlation.png")
    log("\n--- top |corr| pairs among sensors (multicollinearity suspects) ---")
    pairs = []
    for i, a in enumerate(sensors):
        for b in sensors[i + 1:]:
            pairs.append((a, b, abs(corr.loc[a, b])))
    pairs.sort(key=lambda t: -t[2])
    for a, b, r in pairs[:10]:
        log(f"{a} - {b}: |r| = {r:.3f}")


def _vif(frame: pd.DataFrame) -> pd.Series:
    X = frame.to_numpy(dtype=float)
    out = {}
    for j, col in enumerate(frame.columns):
        y = X[:, j]
        if np.std(y) == 0:
            out[col] = np.inf
            continue
        mask = np.ones(X.shape[1], bool)
        mask[j] = False
        reg = LinearRegression().fit(X[:, mask], y)
        r2 = reg.score(X[:, mask], y)
        out[col] = float(1.0 / max(1e-12, 1.0 - r2))
    return pd.Series(out).sort_values(ascending=False)


def prototype_features(df: pd.DataFrame) -> list[str]:
    sensors = _sensors(df)
    # nunique (not std == 0.0) so floating-point dust on flat sensors can't
    # hide them: groupby.std and Series.std disagree at ~1e-15 on constants.
    const_union = sorted(
        {c for _, g in df.groupby("subset") for c in sensors if g[c].nunique() <= 1}
    )
    log(f"\n[features] constant in >=1 subset (drop candidates): {const_union}")

    usable = [c for c in sensors if c not in const_union]
    log(f"[features] sensors entering redundancy prune: {usable}")

    # Redundancy is clustered on FD001 only (single operating condition + single
    # fault mode). On pooled multi-condition data every sensor correlates via
    # the operating point (|r| > 0.95 chains everything into one cluster),
    # which says nothing about sensor physics. FD001 isolates true redundancy.
    ref = df[df["subset"] == "FD001"]
    ref_corr = ref[usable + ["rul"]].corr(numeric_only=True)
    ref_corr_rul = ref_corr["rul"].drop("rul").abs()
    thresh = 0.95
    parent: dict[str, str] = {c: c for c in usable}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(usable):
        for b in usable[i + 1:]:
            if abs(ref_corr.loc[a, b]) > thresh:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    clusters: dict[str, list[str]] = {}
    for c in usable:
        clusters.setdefault(find(c), []).append(c)
    kept = [max(m, key=lambda c: ref_corr_rul[c]) for m in clusters.values()]
    log(f"[features] FD001-based |r| > {thresh}: {len(usable)} sensors -> "
        f"{len(clusters)} clusters, keeps={sorted(kept)}")
    for members in sorted(clusters.values(), key=len, reverse=True):
        if len(members) > 1:
            log(f"  cluster {members} -> keep {max(members, key=lambda c: ref_corr_rul[c])}")

    log("\n--- VIF before prune (top 10) ---")
    log(_vif(df[usable].sample(min(20000, len(df)), random_state=0)).head(10).to_string())
    log("\n--- VIF after prune ---")
    log(_vif(df[kept].sample(min(20000, len(df)), random_state=0)).to_string())

    # Candidate engineered features (computed per engine, causal - no leakage).
    # Built on informative trending sensors (independent of the prune outcome
    # so the trend check is not hostage to tie-breaks in |corr with RUL| ~0.01).
    # NOTE: `cycle` below correlates -1.0 with RUL by construction
    # (RUL = max_cycle - cycle per engine) - shown only as a leakage demo,
    # it must NEVER be a model input.
    sample_vid = df.groupby("vehicle_id")["timestamp"].max().idxmax()
    g = df[df["vehicle_id"] == sample_vid].sort_values("timestamp")
    base_cols = ["T50", "P30", "Ps30", "phi", "NRc", "BPR"]
    feats = pd.DataFrame({"rul": g["rul"].values, "cycle": g["timestamp"].values})
    for c in base_cols:
        s = g[c].reset_index(drop=True)
        feats[f"{c}_rollmean_10"] = s.rolling(10, min_periods=1).mean()
        feats[f"{c}_slope_10"] = s.diff(10).fillna(0) / 10.0
        baseline = s.iloc[:20].mean()
        feats[f"{c}_vs_baseline"] = s - baseline
    feat_corr = feats.corr()
    log("\n--- engineered-feature |corr| with RUL (sample engine) ---")
    log(feat_corr["rul"].drop("rul").sort_values(
        key=np.abs, ascending=False).to_string())

    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(feat_corr.values, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(feat_corr.columns)), feat_corr.columns,
                  rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(len(feat_corr.columns)), feat_corr.columns, fontsize=7)
    ax.set_title("Engineered-feature correlation (linear-independence check)")
    fig.colorbar(im, ax=ax, label="r")
    _savefig("10_engineered_corr.png")

    # `cycle` is excluded: leakage demo, not a candidate.
    ranked = feat_corr["rul"].drop(["rul", "cycle"]).abs().sort_values(ascending=False)
    log("\n--- engineered-feature |corr| with RUL, leakage col excluded ---")
    log(ranked.to_string())
    log("\n--- VIF on engineered set (slopes + baseline deltas, no raw levels) ---")
    log(_vif(feats.drop(columns=["rul", "cycle"])).to_string())
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    top2 = ranked.head(2).index.tolist()
    ax2.scatter(feats[top2[0]], feats[top2[1]], c=feats["rul"], s=8, cmap="viridis_r")
    ax2.set_xlabel(top2[0])
    ax2.set_ylabel(top2[1])
    ax2.set_title("Top-2 engineered features coloured by RUL")
    _savefig("11_derived_scatter.png")

    log("\n=== FEATURE RECOMMENDATIONS (C-MAPSS -> DrivePulse RUL) ===")
    log(f"1. Base regressors (one keep per |r|>{thresh} cluster): {sorted(kept)}")
    log(f"2. ALWAYS drop {const_union}: flat in single-condition subsets, "
        "pure operating-point bias elsewhere. Matches the classic C-MAPSS "
        "drop set (T2/P2/P15/epr/farB/Nf_dmd/PCNfR_dmd + setting_3).")
    log("3. Do NOT feed raw setting_1/2/3 as plain regressors on mixed subsets; "
        "instead normalise sensors per operating condition (groupby-setting "
        "z-score) or add the condition id as a categorical effect.")
    log("4. Linear independence comes from per-condition normalisation, not from "
        "stacking smoothings: rollmean_10 tracks its raw parent (VIF ~1e5), so "
        "raw + smoothed versions of one sensor must never co-exist in a linear "
        "model. Normalise sensors per operating condition first (groupby-setting "
        "z-score), then derive causal rolling slopes / delta-vs-baseline on the "
        "residuals - slopes are the most orthogonal family in the VIF table.")
    log("5. Clip the RUL label (e.g. RUL_clip = min(RUL, 125), He et al. "
        "piecewise-linear target): early-life sensor plateaus cannot predict "
        "200+ cycles ahead and inflate error; clipping is standard on C-MAPSS.")
    log("6. Leakage guards: never use cycle/max_cycle ratios, future-cycle "
        "aggregates, or the subset id as a proxy for fault mode at inference. "
        "Split train/val/test by engine (vehicle_id), not by row, and scale "
        "with PreProcessing.scale fitted on train only.")
    return kept


def validate_pipeline(df: pd.DataFrame, kept: list[str]) -> None:
    """Exercise the recommended features through src.data.preprocessing.

    Uses the exact PreProcessing steps the RUL model will use - engine-grouped
    time split (no row-level leakage), scaler fitted on train only, and
    window tensor construction - so the EDA proves the features survive the
    real pipeline instead of a notebook-only transform.
    """
    log("\n--- pipeline check: PreProcessing.train_val_test_split "
        "(group_by_vehicle=True) ---")
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.15, test_frac=0.15, group_by_vehicle=True)
    for name, part in (("train", train), ("val", val), ("test", test)):
        log(f"{name}: rows={len(part)} engines={part['vehicle_id'].nunique()} "
            f"mean_RUL={part['rul'].mean():.1f}")
    overlap = (set(train["vehicle_id"]) & set(val["vehicle_id"])
               | set(train["vehicle_id"]) & set(test["vehicle_id"]))
    log(f"[split-behaviour] group_by_vehicle=True slices EACH engine timeline "
        f"chronologically, so {len(overlap)} engines appear in every split and "
        f"RUL ranges barely overlap (train ~early life, test ~end of life). "
        f"For RUL regression prefer whole-engine splits (all cycles of an "
        f"engine in exactly one split, e.g. GroupShuffleSplit on vehicle_id); "
        f"consider adding that mode to PreProcessing.train_val_test_split.")

    log("\n--- pipeline check: PreProcessing.scale (fit train, reuse on val) ---")
    train_s, scaler = PreProcessing.scale(train, feature_cols=kept)
    val_s, _ = PreProcessing.scale(val, scaler=scaler, feature_cols=kept)
    log("train scaled mean (should be ~0):")
    log(train_s[kept].mean().round(4).to_string())
    log("val scaled std (spread preserved, not refit):")
    log(val_s[kept].std().round(4).to_string())
    assert "rul" not in scaler.feature_names_in_, "Target leaked into scaler!"

    log("\n--- pipeline check: PreProcessing.make_time_windows "
        "(window_size=30) ---")
    X = PreProcessing.make_time_windows(train_s, window_size=30, feature_cols=kept)
    log(f"window tensor shape (n_windows, 30, n_features={len(kept)}): {X.shape}")
    assert X.ndim == 3 and X.shape[1:] == (30, len(kept))

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist([train["rul"], val["rul"], test["rul"]], bins=50,
            label=["train", "val", "test"], alpha=0.6)
    ax.set_title("RUL distribution per engine-grouped split")
    ax.set_xlabel("RUL")
    ax.legend()
    _savefig("12_split_rul_hist.png")


def write_report() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for f in FIG_DIR.glob("*.png"):
        if f.name not in SAVED_FIGS:
            f.unlink()
    (FIG_DIR / "REPORT.md").write_text(
        "# C-MAPSS EDA report (RUL regression)\n\n"
        "Generated by `ml/notebooks/eda_cmapss.py` via "
        "`src.data.loaders.load_cmapss` and validated against "
        "`src.data.preprocessing.PreProcessing` (clean / scale / windows / "
        "engine-grouped splits).\n\n"
        + "\n".join(f"    {ln}" if ln and not ln.startswith(("=", "-", "[")) else ln
                    for ln in REPORT_LINES)
        + "\n",
        encoding="utf-8",
    )
    log(f"\n[done] figures + REPORT.md saved to {FIG_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA for C-MAPSS RUL data.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--subset", default="all",
                        help="FD001..FD004 or 'all' (default)")
    parser.add_argument("--no-show", action="store_true",
                        help="Only save figures (default behaviour).")
    args = parser.parse_args()
    no_show = True  # Agg backend: always save; flag kept for CLI parity

    if not Path(args.data_dir).exists():
        sys.exit(f"Data dir not found: {args.data_dir} (pass --data-dir PATH)")

    df = load_and_profile(args.data_dir, args.subset)
    df = clean_and_verify(df)
    analyse_target(df)
    plot_operating_conditions(df)
    screen_sensor_variance(df)
    plot_univariate(df)
    plot_degradation(df)
    plot_correlation(df)
    kept = prototype_features(df)
    validate_pipeline(df, kept)
    write_report()


if __name__ == "__main__":
    main()
