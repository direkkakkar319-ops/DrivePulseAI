"""EDA for the Scania APS failure-classification data (heavy-truck APS).

Usage:
    python ml/notebooks/eda_aps.py [--data-dir PATH] [--no-show]

Loads data through src.data.loaders.load_aps so the analysis matches exactly
what the classifier will train on (official split, na -> NaN, failure label).
Figures and a markdown report go to ml/reports/figures/aps/.

Only matplotlib is used for plots (seaborn is not a project dependency).
Main EDA runs on train; test is used only for a distribution-drift check,
never for feature selection.
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
from sklearn.linear_model import LinearRegression

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]
ML_DIR = THIS_FILE.parents[1]
for candidate in (ML_DIR, REPO_ROOT / "ml"):
    if (candidate / "src" / "data" / "loaders.py").exists():
        if str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        break

from src.data.loaders import load_aps  # noqa: E402
from src.data.preprocessing import PreProcessing  # noqa: E402

DEFAULT_DATA_DIR = REPO_ROOT / "data" / "automotive_failure" / "scania_aps" / "raw"
FIG_DIR = REPO_ROOT / "ml" / "reports" / "figures" / "aps"

META = ("class", "failure", "vehicle_id", "source")
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


def _feats(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in META]


def _prefix(col: str) -> str:
    return col.split("_")[0]


def load_and_profile(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = load_aps(data_dir, split="train")
    te = load_aps(data_dir, split="test")
    for name, df in (("train", tr), ("test", te)):
        feats = _feats(df)
        log(f"[{name}] rows={len(df)} features={len(feats)} "
            f"pos={int(df['failure'].sum())} "
            f"({df['failure'].mean():.4f}) source={df['source'].unique().tolist()}")
    log("\n--- dtypes (train) ---")
    log(tr.dtypes.value_counts().to_string())
    log("\n--- head (train, first 6 cols) ---")
    log(tr.iloc[:5, :6].to_string())
    log("\n--- missing cells ---")
    for name, df in (("train", tr), ("test", te)):
        n = int(df[_feats(df)].isna().sum().sum())
        log(f"{name}: {n} NaN cells "
            f"({n / (len(df) * len(_feats(df))):.2%} of feature cells)")
    log(f"\n--- duplicated rows: train={int(tr.duplicated().sum())} "
        f"test={int(te.duplicated().sum())} ---")
    log("\n--- describe (train features) ---")
    log(tr[_feats(tr)].describe().T.to_string())
    return tr, te


def clean_and_verify(tr: pd.DataFrame) -> pd.DataFrame:
    # Failure label excluded from imputation so positives are never fabricated.
    cleaned, stats = PreProcessing.clean(tr, return_imputer_stats=True)
    n_feat = len(_feats(tr))
    log(f"\n[clean] rows {len(tr)} -> {len(cleaned)} | "
        f"imputed {len(stats)}/{n_feat} features (median)")
    assert len(cleaned) == len(tr.drop_duplicates()), "Unexpected row loss in clean()"
    return cleaned


def analyse_target(tr: pd.DataFrame, te: pd.DataFrame) -> None:
    log("\n--- class balance ---")
    for name, df in (("train", tr), ("test", te)):
        log(f"{name}: neg={int((df['failure'] == 0).sum())} "
            f"pos={int(df['failure'].sum())} "
            f"neg:pos = {(df['failure'] == 0).sum() / max(df['failure'].sum(), 1):.1f}:1")
    log("[semantics] pos = APS component failed; neg = OTHER-component "
        "failure, not healthy. Precision here means 'right part flagged'.")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (name, df) in zip(axes, (("train", tr), ("test", te))):
        df["failure"].value_counts().sort_index().plot(kind="bar", rot=0, ax=ax)
        ax.set_title(f"{name} (0=other failure, 1=APS failure)")
        ax.set_ylabel("count")
        ax.set_yscale("log")
    fig.suptitle("Class balance, log scale (official split preserved)")
    _savefig("01_target_balance.png")


def analyse_missing(tr: pd.DataFrame) -> pd.Series:
    feats = _feats(tr)
    miss = tr[feats].isna().mean().sort_values(ascending=False)
    log("\n--- missing share per feature (worst 15) ---")
    log(miss.head(15).to_string())
    log(f"[missing] features >50% missing: {(miss > 0.5).tolist().count(True)} | "
        f"fully missing: {int((miss == 1.0).sum())}")

    per_row = tr[feats].isna().sum(axis=1)
    log("\n--- missing cells per row ---")
    log(per_row.describe().to_string())
    pos_miss = per_row[tr["failure"] == 1].mean()
    neg_miss = per_row[tr["failure"] == 0].mean()
    log(f"[missing] mean missing cells/row: pos={pos_miss:.1f} neg={neg_miss:.1f} "
        f"(gap = signal for missingness indicators)")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    miss.head(20).sort_values().plot(kind="barh", ax=axes[0])
    axes[0].set_title("Top-20 features by missing share")
    axes[0].set_xlabel("share NaN")
    per_row.hist(bins=60, ax=axes[1])
    axes[1].set_title("Missing cells per row")
    axes[1].set_xlabel("NaN count")
    fig.suptitle("Missingness overview (train)")
    _savefig("02_missing_overview.png")
    return miss


def analyse_groups(tr: pd.DataFrame, miss: pd.Series) -> None:
    feats = _feats(tr)
    corr = tr[feats + ["failure"]].corr(numeric_only=True)["failure"].drop("failure")
    rows = []
    by_prefix = pd.Series(feats).groupby([_prefix(c) for c in feats])
    for prefix, cols in by_prefix:
        cols = list(cols)
        rows.append({
            "group": prefix,
            "n": len(cols),
            "miss": float(miss[cols].mean()),
            "max_corr": float(corr[cols].abs().max()),
        })
    g = pd.DataFrame(rows).sort_values("max_corr", ascending=False)
    log("\n--- prefix groups by max |corr| with failure (top 20) ---")
    log(g.head(20).to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    top = g.head(25)
    top.plot(x="group", y="max_corr", kind="bar", rot=45, ax=axes[0], legend=False)
    axes[0].set_title("Top-25 groups by max |corr| with failure")
    axes[0].set_ylabel("|r|")
    top.plot(x="group", y="miss", kind="bar", rot=45, ax=axes[1], legend=False,
             color="orange")
    axes[1].set_title("Same groups: mean missing share")
    axes[1].set_ylabel("share NaN")
    fig.suptitle("Anonymized prefix groups: signal vs missingness")
    _savefig("03_group_profiles.png")


def plot_univariate(tr: pd.DataFrame) -> list[str]:
    feats = _feats(tr)
    corr = tr[feats + ["failure"]].corr(numeric_only=True)["failure"].drop("failure")
    top = corr.abs().sort_values(ascending=False).head(12).index.tolist()
    log("\n--- top |corr| with failure ---")
    log(corr[top].sort_values(key=np.abs, ascending=False).to_string())
    if (corr.abs().max() > 0.95):
        log("[leakage] a feature correlates ~1.0 with the label - inspect it.")
    else:
        log(f"[leakage] max |r| = {corr.abs().max():.3f}: no single-column "
            f"label leak.")

    fig, axes = plt.subplots(3, 4, figsize=(15, 9))
    for ax, col in zip(axes.flat, top):
        for val, sub in (("neg", tr[tr["failure"] == 0]), ("pos", tr[tr["failure"] == 1])):
            sub[col].hist(bins=40, ax=ax, alpha=0.5, label=val, density=True)
        ax.set_title(col, fontsize=9)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Top-12 features by |corr|: neg vs pos distributions")
    _savefig("04_univariate_top.png")

    log("\n--- skew (top-12 signal features) ---")
    log(tr[top].agg(["skew", "kurtosis"]).T.to_string())
    return top


def plot_separation(tr: pd.DataFrame) -> None:
    feats = _feats(tr)
    pos, neg = tr[tr["failure"] == 1], tr[tr["failure"] == 0]
    pooled = np.sqrt((pos[feats].var() + neg[feats].var()) / 2)
    smd = ((pos[feats].mean() - neg[feats].mean()) / pooled).abs()
    smd = smd.replace([np.inf, -np.inf], np.nan).dropna().sort_values(ascending=False)
    log("\n--- standardized mean difference |pos-neg|/sd (top 15) ---")
    log(smd.head(15).to_string())

    fig, ax = plt.subplots(figsize=(9, 6))
    smd.head(20).sort_values().plot(kind="barh", ax=ax)
    ax.set_title("Top-20 class separators (std. mean difference)")
    ax.set_xlabel("|mean_pos - mean_neg| / pooled sd")
    _savefig("05_separation_bar.png")

    fig2, axes2 = plt.subplots(2, 3, figsize=(13, 7))
    for ax, col in zip(axes2.flat, smd.head(6).index):
        ax.boxplot([neg[col].dropna(), pos[col].dropna()],
                   tick_labels=["neg", "pos"], showfliers=False)
        ax.set_title(col, fontsize=9)
    fig2.suptitle("Top-6 separators: neg vs pos (no outliers drawn)")
    _savefig("06_box_top.png")
    log("\n--- median by class (top-6 separators) ---")
    log(tr.groupby("failure")[smd.head(6).index.tolist()].median().T.to_string())


def plot_correlation(tr: pd.DataFrame, top: list[str]) -> None:
    corr = tr[top + ["failure"]].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(corr.columns)), corr.columns, rotation=45, ha="right",
                  fontsize=8)
    ax.set_yticks(range(len(corr.columns)), corr.columns, fontsize=8)
    ax.set_title("Correlation among top-12 signal features + label")
    fig.colorbar(im, ax=ax, label="r")
    _savefig("07_correlation_top.png")

    log("\n--- top |corr| pairs among top-12 (redundancy suspects) ---")
    pairs = [(a, b, abs(corr.loc[a, b])) for i, a in enumerate(top) for b in top[i + 1:]]
    for a, b, r in sorted(pairs, key=lambda t: -t[2])[:8]:
        log(f"{a} - {b}: |r| = {r:.3f}")


def check_drift(tr: pd.DataFrame, te: pd.DataFrame) -> None:
    feats = _feats(tr)
    drift = pd.DataFrame({
        "train_mean": tr[feats].mean(),
        "test_mean": te[feats].mean(),
        "train_miss": tr[feats].isna().mean(),
        "test_miss": te[feats].isna().mean(),
    })
    scale = tr[feats].std().replace(0, np.nan)
    drift["mean_shift"] = (drift["test_mean"] - drift["train_mean"]).abs() / scale
    drift["miss_shift"] = (drift["test_miss"] - drift["train_miss"]).abs()
    log("\n--- train vs test drift (worst 10 mean shifts, in train-sd units) ---")
    log(drift.sort_values("mean_shift", ascending=False).head(10).to_string())
    log("\n--- worst 5 missing-rate shifts ---")
    log(drift.sort_values("miss_shift", ascending=False).head(5).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].scatter(drift["train_mean"], drift["test_mean"], s=6, alpha=0.5)
    lims = [drift[["train_mean", "test_mean"]].min().min(),
            drift[["train_mean", "test_mean"]].max().max()]
    axes[0].plot(lims, lims, "r--", lw=1)
    axes[0].set_title("Per-feature mean: train vs test")
    axes[0].set_xlabel("train mean")
    axes[0].set_ylabel("test mean")
    axes[1].scatter(drift["train_miss"], drift["test_miss"], s=6, alpha=0.5)
    axes[1].plot([0, 1], [0, 1], "r--", lw=1)
    axes[1].set_title("Per-feature missing rate: train vs test")
    axes[1].set_xlabel("train NaN share")
    axes[1].set_ylabel("test NaN share")
    fig.suptitle("Official-split drift check (features only, no test labels used)")
    _savefig("08_drift.png")


def _vif(frame: pd.DataFrame) -> pd.Series:
    X = frame.to_numpy(dtype=float)
    out = {}
    for j, col in enumerate(frame.columns):
        y = X[:, j]
        if np.std(y) == 0 or np.isnan(y).any():
            out[col] = np.inf
            continue
        mask = np.ones(X.shape[1], bool)
        mask[j] = False
        reg = LinearRegression().fit(X[:, mask], y)
        out[col] = float(1.0 / max(1e-12, 1.0 - reg.score(X[:, mask], y)))
    return pd.Series(out).sort_values(ascending=False)


def prototype_features(tr: pd.DataFrame, top: list[str]) -> list[str]:
    sample = tr[top].sample(min(20000, len(tr)), random_state=0)
    log("\n--- VIF on top-12 signal features (median-imputed sample) ---")
    log(_vif(sample.fillna(sample.median(numeric_only=True))).to_string())

    # Missingness itself separates classes: a per-row NaN count is nearly
    # orthogonal to any single sensor and costs nothing at inference.
    feats = pd.DataFrame(index=tr.index)
    feats["n_missing"] = tr[_feats(tr)].isna().sum(axis=1)
    feats["failure"] = tr["failure"].values
    log("\n--- failure rate by missing-cell quartile ---")
    edges = np.unique(feats["n_missing"].quantile([0, 0.25, 0.5, 0.75, 1.0]))
    if len(edges) < 3:  # heavy ties collapse quantile edges; fall back to width
        edges = np.linspace(feats["n_missing"].min(),
                            feats["n_missing"].max() + 1, 5)
    feats["miss_q"] = pd.cut(feats["n_missing"], bins=edges,
                             include_lowest=True, duplicates="drop")
    log(feats.groupby("miss_q", observed=True)["failure"].mean().to_string())

    fig, ax = plt.subplots(figsize=(8, 4))
    feats.groupby("miss_q", observed=True)["failure"].mean().plot(kind="bar", ax=ax)
    ax.set_title("Failure rate by missing-cell quartile")
    ax.set_ylabel("APS failure rate")
    _savefig("09_missing_binned_rate.png")

    kept = top
    log("\n=== FEATURE RECOMMENDATIONS (APS -> DrivePulse failure model) ===")
    log(f"1. Start from these 12 ({', '.join(kept)}): strongest univariate "
        "signal, check the 07 heatmap before feeding correlated pairs to "
        "linear models. Trees take all 170.")
    log("2. Missing data: XGBoost consumes NaN natively - no imputation. "
        "For logreg, median-impute (PreProcessing.clean stats, fit on train) "
        "PLUS a per-row n_missing indicator and/or top-missing-feature flags.")
    log("3. Drop features >80% missing only after confirming no signal; "
        "the quartile plot above decides, not an arbitrary cutoff.")
    log("4. Imbalance 1.7% pos: scale_pos_weight ~= 59, judge on PR-AUC / F2, "
        "never accuracy. Tune the threshold for recall - a missed APS failure "
        "costs more than a false alarm on another component.")
    log("5. neg = other-component failure, not healthy: precision means the "
        "right part gets flagged, and 'negatives' still represent broken trucks.")
    log("6. Leakage guards: official test split stays untouched until final "
        "eval (drift check only); TWF-style fault flags don't exist here, but "
        "re-verify no |r| ~ 1.0 column after any future feature work. Scale "
        "with PreProcessing.scale fitted on train only.")
    return kept


def validate_pipeline(tr: pd.DataFrame, te: pd.DataFrame, kept: list[str]) -> None:
    log("\n--- pipeline check: PreProcessing.scale (fit train, reuse test) ---")
    tr_s, scaler = PreProcessing.scale(tr, feature_cols=kept)
    te_s, _ = PreProcessing.scale(te, scaler=scaler, feature_cols=kept)
    log("train scaled mean (~0): " + ", ".join(f"{v:.3f}" for v in tr_s[kept].mean()))
    log("test scaled std (spread preserved): " +
        ", ".join(f"{v:.3f}" for v in te_s[kept].std()))
    assert "failure" not in scaler.feature_names_in_, "Target leaked into scaler!"
    log(f"[split] official split preserved: train={len(tr_s)} test={len(te_s)}; "
        "no resplitting, no row shuffling across the boundary.")


def write_report() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for f in FIG_DIR.glob("*.png"):
        if f.name not in SAVED_FIGS:
            f.unlink()
    (FIG_DIR / "REPORT.md").write_text(
        "# APS EDA report (failure classification)\n\n"
        "Generated by `ml/notebooks/eda_aps.py` via "
        "`src.data.loaders.load_aps`.\n\n"
        + "\n".join(f"    {ln}" if ln and not ln.startswith(("=", "-", "[")) else ln
                    for ln in REPORT_LINES)
        + "\n",
        encoding="utf-8",
    )
    log(f"\n[done] figures + REPORT.md saved to {FIG_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA for Scania APS failure data.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--no-show", action="store_true",
                        help="Only save figures (default behaviour).")
    args = parser.parse_args()

    if not Path(args.data_dir).exists():
        sys.exit(f"Data dir not found: {args.data_dir} (pass --data-dir PATH)")

    tr, te = load_and_profile(args.data_dir)
    tr_raw = tr  # missingness needs the pre-imputation state; clean() fills NaN
    tr = clean_and_verify(tr)
    analyse_target(tr, te)
    miss = analyse_missing(tr_raw)
    analyse_groups(tr, miss)
    top = plot_univariate(tr)
    plot_separation(tr)
    plot_correlation(tr, top)
    check_drift(tr, te)
    kept = prototype_features(tr, top)
    validate_pipeline(tr, te, kept)
    write_report()


if __name__ == "__main__":
    main()
