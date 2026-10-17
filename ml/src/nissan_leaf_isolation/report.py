"""Render experimental score diagnostics, review evidence and a provenance report."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from nissan_leaf_preparation.core import digest, save_json
from nissan_leaf_preparation.report import markdown

from .core import FEATURES


def build_report(out: Path, root: Path) -> None:
    """Use saved scores only; reporting never refits or rescores the model."""
    dev = json.loads((out / "development.json").read_text())
    test_path = out / "test_evaluation.json"
    test = json.loads(test_path.read_text()) if test_path.exists() else None
    for name, expected in dev["development_outputs"].items():
        if digest(out / name) != expected:
            raise ValueError("Development artifact changed before reporting")
    if test:
        for name, expected in test["test_outputs"].items():
            if digest(out / name) != expected:
                raise ValueError("Test artifact changed before reporting")
    results = dict(dev["results"])
    if test:
        results["test"] = test["results"]
    base = root / "ml/reports/nissan_leaf_2018"
    tables = base / "tables/isolation_forest" / out.name
    figures = base / "figures/isolation_forest" / out.name
    tables.mkdir(parents=True, exist_ok=False)
    figures.mkdir(parents=True, exist_ok=False)
    config = dev["config"]
    summary = pd.DataFrame(
        [
            {
                "split": split,
                **{k: v for k, v in metrics.items() if k != "score_quantiles"},
            }
            for split, metrics in results.items()
        ]
    )
    summary.to_csv(tables / "split_metrics.csv", index=False)
    save_json(tables / "experiment_summary.json", {"development": dev, "test": test})
    candidates = pd.read_csv(out / "threshold_candidates.csv")
    candidates.to_csv(tables / "threshold_candidates.csv", index=False)
    for path in out.glob("*.csv"):
        if path.name != "threshold_candidates.csv":
            (tables / path.name).write_bytes(path.read_bytes())
    fig, ax = plt.subplots(figsize=(9, 5))
    reviews, stability, distributions = [], [], []
    for split in results:
        frame = pd.read_parquet(out / f"scores_{split}.parquet")
        frame["date"] = pd.to_datetime(
            frame.Timestamp, unit="us", utc=True
        ).dt.strftime("%Y-%m-%d")
        hist, edges = np.histogram(
            frame.score_samples, bins=np.linspace(-1, 0, 201), density=True
        )
        ax.stairs(hist, edges, label=split)
        quantiles = results[split]["score_quantiles"]
        stability.append(
            {
                "split": split,
                **quantiles,
                "first_half_median": frame.score_samples.iloc[
                    : len(frame) // 2
                ].median(),
                "second_half_median": frame.score_samples.iloc[
                    len(frame) // 2 :
                ].median(),
            }
        )
        for name in FEATURES:
            stats = (
                frame[name]
                .describe(percentiles=[0.001, 0.01, 0.25, 0.5, 0.75, 0.99, 0.999])
                .to_dict()
            )
            distributions.append({"split": split, "feature": name, **stats})
        for key in ["trips", "dates"]:
            table = pd.read_csv(out / f"{key}_{split}.csv")
            figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
            x = np.arange(len(table))
            axes[0].bar(x, table.flagged_pct)
            axes[0].set_ylabel("Flagged rows (%)")
            axes[1].bar(x, table.alerts_per_recorded_hour)
            axes[1].set_ylabel("Persistent intervals / hour")
            labels = table.iloc[:, 0].astype(str).to_numpy()
            ticks = x[:: max(1, len(x) // 15)]
            axes[1].set_xticks(ticks, labels[ticks], rotation=45, ha="right")
            axes[1].set_xlabel("Trip" if key == "trips" else "Recording date (UTC)")
            axes[0].set_title(f"{split}: provisional alert policy")
            figure.tight_layout()
            figure.savefig(figures / f"{key}_{split}.png", dpi=130)
            plt.close(figure)
        events = pd.read_parquet(out / f"intervals_{split}.parquet")
        chosen = events.sort_values(
            ["persistent", "score_min", "start_us"], ascending=[False, True, True]
        ).head(config["review_intervals_per_split"])
        for rank, row in enumerate(chosen.itertuples(), start=1):
            event = frame[frame.source_row.between(row.start_row, row.end_row)]
            context = frame[
                frame.Trip.eq(row.Trip)
                & frame.segment_id.eq(row.segment_id)
                & frame.Timestamp.between(
                    row.start_us - config["context_seconds"] * 1e6,
                    row.end_us + config["context_seconds"] * 1e6,
                )
            ]
            info = row._asdict()
            info.pop("Index")
            info.update(
                {
                    "rank": rank,
                    "quality_flags_or": int(
                        np.bitwise_or.reduce(event.quality_flags.to_numpy())
                    ),
                    "drivetrain_unavailable_fraction": float(
                        event.drivetrain_unavailable_suspected.mean()
                    ),
                    "context_rows": len(context),
                }
            )
            for name in FEATURES:
                info.update(
                    {
                        f"{name}_{stat}": float(getattr(event[name], stat)())
                        for stat in ["min", "max", "mean"]
                    }
                )
            reviews.append(info)
            context.to_parquet(
                tables / f"context_{split}_{rank}.parquet",
                index=False,
                compression="zstd",
            )
            if rank == 1:
                figure, axes = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
                times = pd.to_datetime(context.Timestamp, unit="us", utc=True)
                for axis, field, unit in zip(
                    axes,
                    [*FEATURES, "score_samples"],
                    ["V", "°C", "%", "score"],
                    strict=True,
                ):
                    axis.plot(times, context[field], ".", markersize=2)
                    axis.set_ylabel(f"{field}\n{unit}")
                    axis.axvspan(row.start_utc, row.end_utc, alpha=0.12, color="orange")
                axes[-1].axhline(dev["threshold"], color="red", linestyle="--")
                axes[0].set_title(
                    f"{split}, trip {row.Trip}: unusual interval, not confirmed fault"
                )
                figure.tight_layout()
                figure.savefig(figures / f"context_{split}.png", dpi=130)
                plt.close(figure)
    ax.axvline(
        dev["threshold"], color="black", linestyle="--", label="Provisional threshold"
    )
    ax.set(
        xlabel="score_samples (lower is more unusual)",
        ylabel="Density",
        xlim=(-0.85, -0.3),
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "score_distributions.png", dpi=130)
    plt.close(fig)
    pd.DataFrame(reviews).to_csv(tables / "expert_review_candidates.csv", index=False)
    pd.DataFrame(stability).to_csv(tables / "score_stability.csv", index=False)
    pd.DataFrame(distributions).to_csv(
        tables / "feature_distributions_original_units.csv", index=False
    )
    inventory = [
        {
            "file": str(p.relative_to(root)),
            "bytes": p.stat().st_size,
            "sha256": digest(p),
        }
        for p in sorted(out.iterdir())
        if p.is_file()
    ]
    pd.DataFrame(inventory).to_csv(tables / "artifact_inventory.csv", index=False)
    summary_columns = [
        "split",
        "scored_rows",
        "flagged_rows",
        "flagged_pct",
        "persistent_alert_intervals",
        "recorded_hours",
        "alerts_per_recorded_hour",
        "trips_with_alerts",
    ]
    table_link = f"tables/isolation_forest/{out.name}"
    figure_link = f"figures/isolation_forest/{out.name}"
    selected_candidates = candidates[
        candidates.persistence_seconds.eq(
            config["aggregation"]["minimum_duration_seconds"]
        )
    ]
    report = f"""# Isolation Forest battery baseline

Purpose: identify statistically unusual logged battery telemetry, without diagnosing confirmed failures. Experiment `{out.name}`; threshold **provisional**.

## 1. Objective

Train one lightweight unsupervised baseline. No artificial anomaly labels, fault-rate assumptions, supervised classification metrics, neural networks or application integration are used.

## 2. Dataset and preparation provenance

Input preparation: `{config["preparation_run_id"]}`, pinned manifest SHA-256 `{config["preparation_manifest_sha256"]}`. The source CSVs, workbook, preparation outputs and original six-feature artifacts were checksum-verified before and after execution. Prepared counts are verified from files and compared with the manifest: `{dev["preparation_rows_verified"]}`. Existing 142/34/51 trip memberships and preprocessing are unchanged; retained coverage differs from assigned trips.

See [EDA_REPORT.md](EDA_REPORT.md), [ML_READINESS_REPORT.md](ML_READINESS_REPORT.md), [DATA_PREPARATION_REPORT.md](DATA_PREPARATION_REPORT.md), [NEGATIVE_SPEED_REVIEW.md](NEGATIVE_SPEED_REVIEW.md) and [BATTERY_ONLY_PREPARATION_REPORT.md](BATTERY_ONLY_PREPARATION_REPORT.md). Test-period data-quality inspection already occurred. This test is exploratory held-out evaluation, not pristine independent confirmation.

## 3. Inputs and explanations

Exactly HV_Bat_Voltage, Pack_1_C_Temp, SOC, in that order. Already robust-scaled with frozen training medians/IQRs. No scaler is fitted here. IDs, timestamps and flags are audit metadata only. Every score includes exact logged feature values and training-IQR deviations. These deviations explain observed feature extremeness, **not causal reasons or exact isolation-tree contributions**.

## 4. Algorithm and score meaning

Isolation Forest repeatedly partitions randomly sampled observations using random feature thresholds. Points isolated in shorter paths receive more unusual scores. See [scikit-learn documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).

Lower `score_samples` means more unusual. `decision_function = score_samples - offset_`; with contamination='auto', offset is -0.5. Negative decision values refer to that default offset, not this experiment's review threshold. We export both scores, verify the formula against the API, and do not call predict. The operational flag is explicitly `score_samples < {dev["threshold"]}`. Scores are not probabilities or mechanical risk percentages.

## 5. Training configuration

- n_estimators=200: number of randomized trees; a starting choice, not optimized.
- max_samples='auto': min(256, fitting rows) observations per tree.
- max_features=1.0: all three features available to each tree.
- bootstrap=False: without replacement within each tree's subsample.
- random_state=42: deterministic random draws.
- n_jobs=-1: available cores for fitting; scoring is batched without forced parallelism.
- contamination='auto': estimator offset convention only; the operational budget is separate.

Versions: `{dev["identity"]["libraries"]}`. Fit runtime: **{dev["fit_seconds"]:.3f}s**. Model: **{dev["model_bytes"]:,} bytes**. Runtime is environment-dependent. No hyperparameter search occurred.

## 6. Fitting coverage and distributions

All **{dev["fit_rows"]:,}** retained training rows, **{dev["fit_trips"]} trips**, **{dev["fit_dates"]} recording dates** were supplied to fit. No external sample was selected, so sample/full-training distribution differences are exactly zero. Per-tree subsampling is internal to Isolation Forest. Exact fit source row IDs, timestamps and trips are in fit_rows.parquet.

Long trips contribute more candidate rows; temporal autocorrelation and sensor refresh differences remain. Tree subsamples do not imply independent or healthy observations. [Scaled fitting distribution](./{table_link}/fit_feature_distributions_scaled.csv) and [original-unit feature distributions](./{table_link}/feature_distributions_original_units.csv) include ranges and percentiles.

## 7. Threshold strategy

Training-only lower quantiles at 0.1%, 0.5%, 1% define review-budget candidates. Strict '<' handles ties conservatively, so actual rates can differ. Validation checks alert volume, trip coverage and persistence, without fault labels. No labeled evidence or operator-capacity constraint establishes an optimal threshold, so the predeclared middle 0.5% budget remains **provisional**, not selected as best. Continuous scores are the primary output.

{markdown(selected_candidates[["split", "training_budget", "threshold", "flagged_pct", "persistent_alert_intervals", "alerts_per_recorded_hour", "trips_with_alerts"]])}

All 0/2/5-second persistence comparisons are in [threshold_candidates.csv](./{table_link}/threshold_candidates.csv); none uses test scores.

## 8. Time-aware aggregation

Consecutive flagged source rows only, same trip and preparation segment; break on unflagged rows, excluded source rows, nonpositive intervals or gaps >1s. No bridging through missing/excluded measurements. Event duration is last minus first observed timestamp, never row_count times assumed cadence. Single points have zero observed duration.

The predeclared 2s filter separates persistent review intervals from point/short candidates. It is a review convenience, not a physically validated fault duration. All point/short intervals and all row scores remain available. Complete interval tables retain source endpoints, timestamps, segment, trip, row count and min/mean/max score.

Recorded hours sum positive adjacent eligible-row intervals <=1s within the same segment/trip and consecutive source IDs. This is **eligible observed coverage**, not wall-clock vehicle use. Excluded periods and isolated points add no time. Date alert counts are assigned to event start dates; elapsed edges are assigned to their ending dates (a subsecond midnight edge may straddle dates).

## 9. Training diagnostics

{markdown(summary[summary.split.eq("train")][summary_columns])}

Fit/score runtimes, medians, ranges, coverage and model hashes are recorded in [experiment_summary.json](./{table_link}/experiment_summary.json). All training data can include unknown faults or acquisition problems; this is not a known-healthy reference.

## 10. Validation diagnostics

{markdown(summary[summary.split.eq("validation")][summary_columns])}

Trip and date tables include zero-alert groups, scored counts, exposure hours, flagged percentages and score medians. Alert counts below mean persistent intervals; point candidates are recorded separately. An alert budget is not a false-positive rate.

## 11. Frozen test protocol

{"A single frozen test evaluation was performed after development.json and frozen_protocol.json were written and verified. A write-once receipt prevents another test evaluation in this experiment. No settings were revised from test scores." if test else "Test scoring was not performed."}

{markdown(summary[summary.split.eq("test")][summary_columns])}

Model and threshold hashes are verified before test loading. Source rows and trips are disjoint across splits and chronological boundaries are checked. The pipeline does not fit on validation or test, refit scaling, or introduce future input values. This same-vehicle time holdout limits generalization even with correct computational separation.

## 12. Score distributions

![Score distributions]({figure_link}/score_distributions.png)

[Quantiles and first/second-half medians](./{table_link}/score_stability.csv) describe temporal score shift. Same-seed refitting produced byte-identical model artifacts and identical scores on {dev["reproducibility"]["probe_rows"]} validation probe rows. Cross-seed robustness is **not assessed** in this single-configuration baseline.

## 13. Alert frequency and stability

![Validation trip frequency]({figure_link}/trips_validation.png)
![Validation date frequency]({figure_link}/dates_validation.png)

Equivalent training/test plots are in the same figure directory. Trends can reflect state coverage, season, recording drift or acquisition quality. Date and trip variation is not evidence of deterioration or known faults.

## 14. Expert-review candidates

[Candidate intervals](./{table_link}/expert_review_candidates.csv) lists at most {config["review_intervals_per_split"]} intervals per split, ordered by persistence, lowest score and timestamp. It includes voltage/temperature/SOC ranges and means, flags, drivetrain availability, score summaries and source/timestamp endpoints. Nearby scored telemetry within the same segment is saved as context_<split>_<rank>.parquet, extending up to {config["context_seconds"]}s either side. These are review candidates, not verified faults.

{"".join(f"![{split} review context]({figure_link}/context_{split}.png)" + chr(10) for split in results if (figures / f"context_{split}.png").exists())}

## 15. Data-quality interactions

quality_<split>.csv stratifies scores and alert fractions by each preparation flag and suspected drivetrain unavailability, including absent groups. These flags are contextual evidence, never targets. Observed associations are confounded by trip/date/state and do not establish sensor failure. Eligibility already excluded some suspicious battery readings, which affects the score distribution and possible anomaly coverage.

## 16. Limitations

No verified fault labels, independent healthy control, repair outcomes or fleet sample exist. Fault accuracy, precision, recall, F1, F2 and ROC-AUC cannot be assigned. A single vehicle and temporally correlated rows constrain generalization. Sensor calibration, polling and sentinel conventions remain uncertain; stale data and legitimate operating extremes can appear unusual. The model sees pointwise voltage/temperature/SOC only, without current or operating-state history. Historical test inspection limits confirmatory claims. No production readiness is claimed.

## 17. Artifacts and reproducibility

Artifacts: `{out.relative_to(root)}`. Fitted-model SHA-256: `{dev["model_sha256"]}`. [Complete artifact inventory](./{table_link}/artifact_inventory.csv) records sizes and hashes. Frozen protocol includes model/threshold/aggregation/configuration; identity includes Python/library versions, package code and input checksums. Score Parquets preserve row lineage and evidence compactly. Existing preparation outputs were never overwritten.

Same-seed model reconstruction and validation-probe comparison passed. Test was scored once, not repeatedly for reproduction. Runtime/UTC audit fields are intentionally nondeterministic. Unit tests and static-check results are recorded in [ISOLATION_FOREST_VALIDATION.md](ISOLATION_FOREST_VALIDATION.md). Load only trusted local joblib artifacts.

## 18. Reproduction commands

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage develop
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage test
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage report
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_isolation ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py ml/tests
```

Execute stages in order in a clean workspace with the pinned preparation. Existing experiment directories are not overwritten; repeat test execution is refused. Identical-seed refitting is already performed within development for reproducibility. A new reviewed code/configuration identity produces a separate experiment, not permission to tune against test results.

## 19. Recommended next experiment

First review candidate intervals and validation alert burden with domain input; refine the provisional review policy using development data. Investigate causal past-only temporal features and operating-state context, with separate versioning and the same trip/gap controls. Do not jump to an autoencoder until baseline weaknesses and review criteria are understood. Battery temperature forecasting can proceed as a separate conditional experiment with a persistence reference, but it does not validate fault detection. None of these follow-on stages was implemented here.
"""
    report_path = base / "ISOLATION_FOREST_BASELINE_REPORT.md"
    with report_path.open("x") as handle:
        handle.write(report)
    print(summary[summary_columns].to_string(index=False), flush=True)
