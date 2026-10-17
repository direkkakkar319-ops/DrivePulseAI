"""Two-stage, immutable Isolation Forest experiment with a pre-test settings freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pyarrow
import sklearn
from nissan_leaf_preparation.core import digest, save_json

from .core import (
    FEATURES,
    diagnostics,
    fit_forest,
    score_with_evidence,
    thresholds,
    validate_inputs,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "ml/notebooks/nissan_leaf_2018/config/isolation_forest.json"


def utc_now() -> str:
    """Record execution chronology separately from deterministic outputs."""
    return datetime.now(timezone.utc).isoformat()


def verify_preparation(config: dict) -> tuple[Path, dict, dict]:
    """Verify pinned preparation, frozen predecessor and original source hashes."""
    directory = (
        ROOT
        / "ml/artifacts/nissan_leaf_2018/preparation"
        / config["preparation_run_id"]
    )
    manifest = directory / "manifest.json"
    if digest(manifest) != config["preparation_manifest_sha256"]:
        raise ValueError("Preparation manifest changed")
    prepared = json.loads(manifest.read_text())
    if (
        prepared["run_id"] != config["preparation_run_id"]
        or prepared["config"]["features"] != FEATURES
    ):
        raise ValueError("Wrong preparation")
    hashes = {str(manifest.relative_to(ROOT)): digest(manifest)}
    for name, info in prepared["outputs"].items():
        hashes[str((directory / name).relative_to(ROOT))] = info["sha256"]
    hashes.update(prepared["source_hashes"])
    hashes.update(prepared["immutable_parent_hashes"])
    verify_hashes(hashes)
    return directory, prepared, hashes


def verify_hashes(hashes: dict) -> None:
    """Fail on mutation; never repair or overwrite protected files."""
    for name, expected in hashes.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Protected file changed: {name}")


def load_split(
    directory: Path, prepared: dict, split: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load aligned scaled inputs and original metadata; do not fit preprocessing."""
    x = pd.read_parquet(directory / f"features_{split}.parquet")
    meta = pd.read_parquet(directory / f"metadata_{split}.parquet")
    validate_inputs(x, meta, split)
    expected = next(r for r in prepared["splits"] if r["split"] == split)
    if (
        len(x) != expected["feature_rows"]
        or meta.Trip.nunique() != expected["retained_trips"]
    ):
        raise ValueError("Prepared counts disagree")
    trips = pd.read_csv(directory / "trip_splits.csv").set_index("Trip").split
    if not meta.Trip.map(trips).eq(split).all():
        raise ValueError("Prepared split membership")
    return x, meta


def attach_evidence(
    scores: pd.DataFrame, meta: pd.DataFrame, directory: Path
) -> pd.DataFrame:
    """Attach exact logged values, source provenance and flags to every score."""
    ledger = pd.read_parquet(
        directory / "row_ledger.parquet",
        columns=["source_row", "Trip", "Timestamp", *FEATURES],
    )
    raw = ledger.set_index("source_row").loc[meta.source_row]
    if not np.array_equal(raw.Timestamp, meta.Timestamp) or not np.array_equal(
        raw.Trip, meta.Trip
    ):
        raise ValueError("Raw evidence alignment")
    out = pd.concat(
        [meta.reset_index(drop=True), scores.reset_index(drop=True)], axis=1
    )
    for name in FEATURES:
        out[name] = raw[name].to_numpy()
    return out


def summarize_split(
    frame: pd.DataFrame, threshold: float, config: dict, out: Path, split: str
) -> dict:
    """Write interval, trip, date and quality diagnostics for frozen settings."""
    result, events, trips, dates = diagnostics(frame, threshold, config["aggregation"])
    events.to_parquet(out / f"intervals_{split}.parquet", index=False)
    trips.to_csv(out / f"trips_{split}.csv", index=False)
    dates.to_csv(out / f"dates_{split}.csv", index=False)
    flags = []
    for name, mask in [
        ("any_quality_flag", frame.quality_flags.ne(0)),
        ("drivetrain_unavailable_suspected", frame.drivetrain_unavailable_suspected),
        *[
            (f"quality_bit_{bit}", (frame.quality_flags & (1 << bit)).ne(0))
            for bit in range(17)
        ],
    ]:
        for present in [False, True]:
            subset = frame.loc[mask.eq(present)]
            flags.append(
                {
                    "flag": name,
                    "present": present,
                    "rows": len(subset),
                    "flagged_rows": int(subset.score_samples.lt(threshold).sum()),
                    "flagged_pct": float(
                        100 * subset.score_samples.lt(threshold).mean()
                    )
                    if len(subset)
                    else None,
                    "score_median": float(subset.score_samples.median())
                    if len(subset)
                    else None,
                }
            )
    pd.DataFrame(flags).to_csv(out / f"quality_{split}.csv", index=False)
    return result


def development(
    config: dict,
    directory: Path,
    prepared: dict,
    hashes: dict,
    out: Path,
    identity: dict,
) -> None:
    """Train and diagnose train/validation only; freeze before test is loadable."""
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    train, train_meta = load_split(directory, prepared, "train")
    validation, val_meta = load_split(directory, prepared, "validation")
    if (
        set(train_meta.Trip) & set(val_meta.Trip)
        or train_meta.Timestamp.max() >= val_meta.Timestamp.min()
    ):
        raise ValueError("Train/validation leakage")
    print(
        f"Fitting {len(train):,} training rows from {train_meta.Trip.nunique()} trips",
        flush=True,
    )
    before = time.perf_counter()
    model = fit_forest(train, train_meta, config["model"])
    fit_seconds = time.perf_counter() - before
    joblib.dump(model, out / "model.joblib", compress=0)
    train_meta[["source_row", "Timestamp", "Trip", "split"]].to_parquet(
        out / "fit_rows.parquet", index=False
    )
    train.describe(percentiles=[0.001, 0.01, 0.25, 0.5, 0.75, 0.99, 0.999]).to_csv(
        out / "fit_feature_distributions_scaled.csv"
    )
    # Exact same-seed reconstruction checks reproducibility without another model choice.
    replica = fit_forest(train, train_meta, config["model"])
    joblib.dump(replica, out / "replica.tmp", compress=0)
    identical_model = digest(out / "model.joblib") == digest(out / "replica.tmp")
    (out / "replica.tmp").unlink()
    if not identical_model:
        raise ValueError("Same-seed fitted model bytes differ")
    probe = validation.iloc[
        np.linspace(0, len(validation) - 1, min(4096, len(validation)), dtype=int)
    ]
    if not np.array_equal(model.score_samples(probe), replica.score_samples(probe)):
        raise ValueError("Same-seed scoring differs")
    del replica
    frames, runtimes = {}, {}
    for split, x, meta in [
        ("train", train, train_meta),
        ("validation", validation, val_meta),
    ]:
        print(f"Scoring {split} only", flush=True)
        before = time.perf_counter()
        scored = score_with_evidence(model, x, config["score_batch_rows"])
        check = x.iloc[: min(1024, len(x))]
        if not np.allclose(
            scored.decision_function.iloc[: len(check)],
            model.decision_function(check),
            atol=1e-14,
            rtol=0,
        ):
            raise ValueError("Decision function mismatch")
        frames[split] = attach_evidence(scored, meta, directory)
        frames[split].to_parquet(
            out / f"scores_{split}.parquet", index=False, compression="zstd"
        )
        runtimes[split] = time.perf_counter() - before
    candidates = thresholds(
        frames["train"].score_samples.to_numpy(), "train", config["alert_budgets"]
    )
    rows = []
    for budget, threshold in candidates.items():
        for persistence in config["persistence_candidates_seconds"]:
            policy = dict(config["aggregation"], minimum_duration_seconds=persistence)
            for split, frame in frames.items():
                metrics, _, _, _ = diagnostics(frame, threshold, policy)
                rows.append(
                    {
                        "split": split,
                        "training_budget": float(budget),
                        "threshold": threshold,
                        "persistence_seconds": persistence,
                        **{k: v for k, v in metrics.items() if k != "score_quantiles"},
                    }
                )
    pd.DataFrame(rows).to_csv(out / "threshold_candidates.csv", index=False)
    selected = candidates[str(config["provisional_budget"])]
    results = {
        split: summarize_split(frame, selected, config, out, split)
        for split, frame in frames.items()
    }
    # No automatic claim of an optimal cutoff from unlabeled validation.
    frozen = {
        "created_utc": utc_now(),
        "test_scored": False,
        "threshold": selected,
        "comparison": "score_samples < threshold",
        "budget": config["provisional_budget"],
        "status": "provisional",
        "selection": config["threshold_reason"],
        "aggregation": config["aggregation"],
        "config": config,
        "model_sha256": digest(out / "model.joblib"),
        "threshold_candidates_sha256": digest(out / "threshold_candidates.csv"),
        "identity": identity,
    }
    verify_hashes(hashes)
    save_json(out / "frozen_protocol.json", frozen)
    summary = {
        "experiment_id": out.name,
        "identity": identity,
        "config": config,
        "preparation_rows_verified": {
            r["split"]: r["feature_rows"] for r in prepared["splits"]
        },
        "fit_rows": len(train),
        "fit_trips": int(train_meta.Trip.nunique()),
        "fit_dates": int(
            pd.to_datetime(train_meta.Timestamp, unit="us", utc=True).dt.date.nunique()
        ),
        "fit_seconds": fit_seconds,
        "model_bytes": (out / "model.joblib").stat().st_size,
        "development_seconds": time.perf_counter() - started,
        "scoring_seconds": runtimes,
        "model_sha256": digest(out / "model.joblib"),
        "threshold": selected,
        "frozen_protocol_sha256": digest(out / "frozen_protocol.json"),
        "reproducibility": {
            "same_seed_model_bytes": True,
            "validation_probe_scores_identical": True,
            "probe_rows": len(probe),
            "decision_function_api_checked": True,
        },
        "results": results,
        "development_outputs": {
            p.name: digest(p) for p in sorted(out.iterdir()) if p.is_file()
        },
    }
    save_json(out / "development.json", summary)
    print(
        "Training/validation complete; protocol frozen before test scoring.", flush=True
    )


def test_once(
    config: dict,
    directory: Path,
    prepared: dict,
    hashes: dict,
    out: Path,
    identity: dict,
) -> None:
    """One frozen exploratory held-out evaluation; never tune or re-score test."""
    dev = json.loads((out / "development.json").read_text())
    if dev["identity"] != identity:
        raise ValueError(
            "Code/config/environment changed after freeze; stop before test"
        )
    for name, expected in dev["development_outputs"].items():
        if digest(out / name) != expected:
            raise ValueError("Frozen development artifact changed")
    if (out / "test_started.json").exists():
        raise ValueError("Test already started; refusing repeat evaluation")
    frozen = json.loads((out / "frozen_protocol.json").read_text())
    # Receipt is written exclusively before loading/scoring test. Failed attempts require review.
    with (out / "test_started.json").open("x") as handle:
        json.dump(
            {
                "started_utc": utc_now(),
                "frozen_protocol_sha256": digest(out / "frozen_protocol.json"),
            },
            handle,
        )
    x, meta = load_split(directory, prepared, "test")
    earlier = pd.read_parquet(directory / "metadata_validation.parquet")
    train_meta = pd.read_parquet(directory / "metadata_train.parquet", columns=["Trip"])
    if (
        set(meta.Trip) & (set(earlier.Trip) | set(train_meta.Trip))
        or meta.Timestamp.min() <= earlier.Timestamp.max()
    ):
        raise ValueError("Test trip/time overlap")
    print("Single frozen exploratory test evaluation", flush=True)
    model = joblib.load(out / "model.joblib")
    before = time.perf_counter()
    frame = attach_evidence(
        score_with_evidence(model, x, config["score_batch_rows"]), meta, directory
    )
    frame.to_parquet(out / "scores_test.parquet", index=False, compression="zstd")
    result = summarize_split(frame, frozen["threshold"], config, out, "test")
    verify_hashes(hashes)
    save_json(
        out / "test_evaluation.json",
        {
            "completed_utc": utc_now(),
            "scoring_seconds": time.perf_counter() - before,
            "frozen_protocol_sha256": digest(out / "frozen_protocol.json"),
            "results": result,
            "preparation_unchanged": True,
            "test_outputs": {p.name: digest(p) for p in sorted(out.glob("*_test.*"))},
        },
    )


def main() -> None:
    """Run explicit development, test or report stages without output replacement."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=["develop", "test", "report"], required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if config["features"] != FEATURES or config["fit_policy"] != "all_training_rows":
        raise ValueError("Unsupported feature or fit policy")
    directory, prepared, hashes = verify_preparation(config)
    identity = {
        "config": config,
        "input_hashes": hashes,
        "code_hashes": {
            str(p.relative_to(ROOT)): digest(p)
            for p in sorted(Path(__file__).parent.glob("*.py"))
        },
        "libraries": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pyarrow.__version__,
            "joblib": joblib.__version__,
        },
    }
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[
        :16
    ]
    out = ROOT / "ml/artifacts/nissan_leaf_2018/isolation_forest" / run_id
    print(f"Experiment {run_id}; preparation checksums verified", flush=True)
    if args.stage == "develop":
        development(config, directory, prepared, hashes, out, identity)
    elif args.stage == "test":
        test_once(config, directory, prepared, hashes, out, identity)
    else:
        from .report import build_report

        build_report(out, ROOT)
    verify_hashes(hashes)


if __name__ == "__main__":
    main()
