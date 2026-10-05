"""Standalone APS benchmark EDA; preserves raw data and existing analyses.

Run: MPLCONFIGDIR=/tmp/aps-mpl python ml/notebooks/eda_scania_aps_uda.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path) -> pd.DataFrame:
    with path.open(encoding="latin-1") as handle:
        header = next(
            (i for i, line in enumerate(handle) if line.startswith("class,")), None
        )
    if header is None:
        raise ValueError(f"Missing class header: {path}")
    frame = pd.read_csv(path, skiprows=header, encoding="latin-1", na_values=["na"])
    if frame["class"].isna().any() or not set(frame["class"]).issubset({"neg", "pos"}):
        raise ValueError("Invalid or missing target")
    frame.iloc[:, 1:].apply(pd.to_numeric, errors="raise")
    if np.isinf(frame.iloc[:, 1:].to_numpy(dtype=float)).any():
        raise ValueError("Infinite feature values")
    return frame


def fingerprints(frame: pd.DataFrame, rounded: bool = False) -> pd.Series:
    features = frame.drop(columns="class").copy()
    if rounded:
        # Coarse candidate screen, not proof of physical-event duplication.
        features = features.apply(
            lambda col: col.map(lambda v: float(f"{v:.3g}") if pd.notna(v) else v)
        )
    return pd.util.hash_pandas_object(features, index=False)


def metrics(y: pd.Series, probability: np.ndarray, threshold: float) -> dict:
    prediction = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()
    return {
        "average_precision": float(average_precision_score(y, probability)),
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "challenge_cost": int(10 * fp + 500 * fn),
    }


def run(raw: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    paths = [raw / f"aps_failure_{name}_set.csv" for name in ("training", "test")]
    supplied, test = map(load, paths)
    if list(supplied.columns) != list(test.columns):
        raise ValueError("Train/test schema mismatch")
    train_hash, test_hash = fingerprints(supplied), fingerprints(test)
    train_coarse, test_coarse = fingerprints(supplied, True), fingerprints(test, True)
    conflicts = supplied.assign(group=train_hash).groupby("group")["class"].nunique()
    leakage = {
        "training_full_row_duplicates": int(supplied.duplicated().sum()),
        "test_full_row_duplicates": int(test.duplicated().sum()),
        "training_predictor_duplicate_rows": int(train_hash.duplicated().sum()),
        "test_predictor_duplicate_rows": int(test_hash.duplicated().sum()),
        "cross_split_distinct_predictor_hashes": len(set(train_hash) & set(test_hash)),
        "cross_split_three_significant_digit_candidates": len(
            set(train_coarse) & set(test_coarse)
        ),
        "training_conflicting_label_groups": int((conflicts > 1).sum()),
    }
    representatives = pd.DataFrame(
        {"hash": train_coarse, "training_row": supplied.index}
    ).drop_duplicates("hash")
    candidates = pd.DataFrame({"hash": test_coarse, "test_row": test.index}).merge(
        representatives, on="hash"
    )
    evidence = []
    for pair in candidates.head(25).itertuples():
        a = supplied.drop(columns="class").iloc[pair.training_row].to_numpy(dtype=float)
        b = test.drop(columns="class").iloc[pair.test_row].to_numpy(dtype=float)
        relative = np.abs(a - b) / np.maximum(1.0, np.maximum(np.abs(a), np.abs(b)))
        evidence.append(
            {
                "training_row": pair.training_row,
                "test_row": pair.test_row,
                "changed_features": int(
                    np.sum(~np.isclose(a, b, rtol=0.0, atol=0.0, equal_nan=True))
                ),
                "maximum_relative_difference": float(np.nanmax(relative)),
            }
        )
    pd.DataFrame(
        evidence,
        columns=[
            "training_row",
            "test_row",
            "changed_features",
            "maximum_relative_difference",
        ],
    ).to_csv(output / "near_duplicate_examples.csv", index=False)
    # Group coarse matches as a conservative guard for our validation split.
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    train_idx, val_idx = next(
        splitter.split(supplied, supplied["class"], groups=train_coarse)
    )
    train, validation = supplied.iloc[train_idx], supplied.iloc[val_idx]
    assert not set(train_coarse.iloc[train_idx]) & set(train_coarse.iloc[val_idx])
    pd.DataFrame(
        {
            "source_row": np.arange(len(supplied)),
            "partition": np.where(
                np.isin(np.arange(len(supplied)), val_idx), "validation", "train"
            ),
        }
    ).to_csv(output / "split_manifest.csv", index=False)
    x_train = train.drop(columns="class")
    profile = x_train.describe(percentiles=[0.01, 0.25, 0.5, 0.75, 0.99]).T
    profile["missing_fraction"] = x_train.isna().mean()
    profile["distinct_nonmissing"] = x_train.nunique()
    profile.to_csv(output / "training_feature_profile.csv")
    by_class = train.groupby("class").agg(lambda col: col.isna().mean()).T
    by_class.to_csv(output / "training_missingness_by_class.csv")
    correlations = x_train.corr(method="spearman")
    pairs = correlations.where(
        np.triu(np.ones(correlations.shape), k=1).astype(bool)
    ).stack()
    pairs[pairs.abs() >= 0.95].rename("spearman").to_csv(
        output / "training_high_correlations.csv"
    )
    counts = train["class"].value_counts()
    counts.plot.bar(title="APS training partition: label imbalance")
    plt.ylabel("Rows")
    plt.tight_layout()
    plt.savefig(output / "class_balance.png")
    plt.close()
    profile["missing_fraction"].nlargest(25).sort_values().plot.barh(
        title="Training: 25 most incomplete features", figsize=(8, 8)
    )
    plt.xlabel("Missing fraction")
    plt.tight_layout()
    plt.savefig(output / "missingness.png")
    plt.close()
    chosen = x_train.isna().mean().nsmallest(6).index
    x_train[chosen].apply(np.log1p).hist(bins=40, figsize=(12, 8))
    plt.suptitle("Training distributions, log(1 + value); anonymized counters")
    plt.tight_layout()
    plt.savefig(output / "distributions.png")
    plt.close()
    usable = profile.index[profile["distinct_nonmissing"] > 1].tolist()
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=100,
                    min_samples_leaf=2,
                    class_weight="balanced_subsample",
                    random_state=42,
                    n_jobs=2,
                ),
            ),
        ]
    )
    y_train = train["class"].eq("pos").astype(int)
    y_val = validation["class"].eq("pos").astype(int)
    pipeline.fit(x_train[usable], y_train)
    probabilities = pipeline.predict_proba(validation[usable])[:, 1]
    thresholds = np.unique(np.r_[0.0, probabilities, np.nextafter(1.0, 2.0)])
    costs = [
        10 * ((probabilities >= t) & (y_val == 0)).sum()
        + 500 * ((probabilities < t) & (y_val == 1)).sum()
        for t in thresholds
    ]
    threshold = float(thresholds[int(np.argmin(costs))])
    result = {
        "validation": metrics(y_val, probabilities, threshold),
        "threshold": threshold,
    }
    # Fail closed for questionable overlap. Never alter the supplied test set.
    blocked = any(
        leakage[k]
        for k in (
            "cross_split_distinct_predictor_hashes",
            "cross_split_three_significant_digit_candidates",
            "training_conflicting_label_groups",
        )
    )
    if not blocked:
        result["test"] = metrics(
            test["class"].eq("pos").astype(int),
            pipeline.predict_proba(test[usable])[:, 1],
            threshold,
        )
    result["test_evaluation_blocked"] = blocked
    summary = {
        "seed": 42,
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "sklearn": __import__("sklearn").__version__,
        },
        "partitions": {
            name: {
                "rows": len(df),
                "labels": df["class"].value_counts().to_dict(),
                "missing_cells": int(df.drop(columns="class").isna().sum().sum()),
            }
            for name, df in [
                ("supplied_training", supplied),
                ("train", train),
                ("validation", validation),
                ("test", test),
            ]
        },
        "leakage": leakage,
        "excluded_constant_features": profile.index[
            profile["distinct_nonmissing"] <= 1
        ].tolist(),
        "baseline": result,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    report = f"""# Scania APS EDA by UDA

Scope: heavy-truck APS component failure classification, not passenger-car diagnosis.
`pos` denotes a specified APS component failure; `neg` denotes other component failures, not healthy trucks.
Local supplied files are structurally complete; external release checksums are unverified.
Features are 170 anonymized counters/histogram bins. No established vehicle IDs, trip IDs, timeline, or RUL labels exist.

## Procedure and split contract

Raw files and earlier EDA artifacts are untouched. Copyright preambles are skipped by locating `class,`; `na` becomes missing.
The supplied test set is preserved. A seeded five-fold stratified group splitter provides approximately 80/20 train/validation;
predictor rows matching at three significant digits stay in one partition. The manifest uses zero-based data row numbers.
Fingerprints exclude targets; coarse matches are candidate screens, not proof of identical events. Hash collision risk is nonzero.
This screen cannot establish absence of general near duplicates or independent vehicles; vehicle-held-out performance is unverified.

Detailed distributions, missingness, constants and correlations use training only. Test labels are used for final evaluation,
apart from basic integrity counts. No outliers or raw rows are deleted. Confirmed duplicates would require a reviewed policy;
conflicting training labels or cross-split exact/coarse overlap block test scoring.

Median imputation and missingness indicators fit on training only. All-null/constant predictors are excluded using training only.
High-missingness features and outliers are retained in this baseline; there is no evidence for arbitrary deletion.
No target imputation, oversampling, scaling, or future observations are used. Tree models do not require scaling.
Training-only class weighting addresses imbalance. The fixed random-forest baseline uses 100 trees and minimum leaf size 2.
The threshold minimizes validation challenge cost (10 per false positive, 500 per missed APS failure), as specified in the local description.
The fitted pipeline is frozen for a single test evaluation; it is not refit using validation and no test-driven tuning is performed.
This baseline is exploratory, not a deployed or production-qualified model; no trained model artifact is published.

## Findings

Training/validation/test contain {len(train):,}/{len(validation):,}/{len(test):,} rows.
The supplied training set has {int(supplied["class"].eq("pos").sum()):,} APS-positive cases among {len(supplied):,} rows.
Training feature `br_000` is missing in {profile.loc["br_000", "missing_fraction"]:.1%} of rows;
constant features excluded from this baseline: {summary["excluded_constant_features"]}.
There are {leakage["cross_split_distinct_predictor_hashes"]} exact cross-split predictor hash matches,
but {leakage["cross_split_three_significant_digit_candidates"]:,} distinct coarse matches.
`near_duplicate_examples.csv` gives up to 25 candidate pairs with zero-based source row numbers and unrounded differences.
Test scoring is {"blocked pending overlap investigation" if blocked else "completed for the fixed baseline"}.
Validation recall is {result["validation"]["recall"]:.1%}, precision {result["validation"]["precision"]:.1%},
and average precision {result["validation"]["average_precision"]:.3f}. These are threshold-selection results, not independent test performance.

See `training_feature_profile.csv` for missingness, percentiles and constants, `training_missingness_by_class.csv`
for label-conditional missingness, and `training_high_correlations.csv` for absolute Spearman correlations >= 0.95.
Plots show imbalance, missingness and log-transformed distributions. Histograms describe counters, not physical sensor units.
`summary.json` records source checksums, software versions, leakage screens, partition counts and evaluation metrics.

Leakage screen: `{json.dumps(leakage)}`.

Baseline results: `{json.dumps(result)}`.

## Next decisions

Review missingness and correlated histogram bins before changing features. Compare preprocessing/model alternatives using
training cross-validation only in a future experiment; any test result must not become a tuning signal.
Obtain vehicle grouping, collection-time definitions and feature availability documentation before claiming event independence
or excluding outcome-derived leakage. Anonymization prevents certifying predictor availability at diagnosis time.
Obtain separately labeled passenger-car data with compatible OBD signals for DrivePulseAI passenger-car classification.

## Reproduce

From the repository root: `MPLCONFIGDIR=/tmp/aps-mpl python ml/notebooks/eda_scania_aps_uda.py`.
Requires pandas, NumPy, scikit-learn and Matplotlib. Optional `--raw` and `--output` override directories.
Reproduction overwrites this analysis's artifacts in the chosen output directory.
Do not repeatedly alter the experiment based on held-out results; overlap remediation requires a separately reviewed policy.
"""
    (output / "REPORT.md").write_text(report)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw", type=Path, default=ROOT / "data/automotive_failure/scania_aps/raw"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ml/reports/scania_aps_uda"
    )
    args = parser.parse_args()
    run(args.raw, args.output)
