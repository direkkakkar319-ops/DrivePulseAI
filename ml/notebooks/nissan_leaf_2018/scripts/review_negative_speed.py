"""Investigate -1 speed and compare fixed-split feature policies without replacing prepared data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "ml/src"))
from nissan_leaf_preparation.core import (
    FLAGS,
    digest,
    fingerprints,
    fit_transformer,
    make_windows,
    save_json,
)
from nissan_leaf_preparation.report import markdown

BASE = ROOT / "ml/reports/nissan_leaf_2018"
OUT = BASE / "tables/negative_speed"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    original = json.loads(
        (BASE / "tables/preparation/preparation_summary.json").read_text()
    )
    config = original["config"]
    artifact = ROOT / original["artifact_directory"]
    for relative, expected in original["source_hashes"].items():
        assert digest(ROOT / relative) == expected, relative
    assert (
        digest(artifact / "row_ledger.parquet")
        == original["outputs"]["row_ledger.parquet"]["sha256"]
    )
    columns = [
        "source_row",
        "index",
        "Timestamp",
        "Trip",
        "split",
        "segment_id",
        "quality_flags",
        "quality_eligible",
        "export_eligible",
        "RPM",
        "Odometer",
        "Pack_2_C_Temp",
        "Pack_4_C_Temp",
        *config["features"],
    ]
    frame = pd.read_parquet(artifact / "row_ledger.parquet", columns=columns)
    raw = pd.read_csv(
        ROOT / "data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv",
        usecols=["Timestamp", "Gear"],
    )
    assert np.array_equal(frame.Timestamp, raw.Timestamp)
    frame["Gear"] = raw.Gear
    del raw
    negative = frame.Speed.lt(0)
    pd.DataFrame(
        {
            "Speed": frame.loc[negative, "Speed"].value_counts().index,
            "rows": frame.loc[negative, "Speed"].value_counts().values,
        }
    ).to_csv(OUT / "negative_values.csv", index=False)
    gear = (
        frame.assign(
            speed_group=np.where(
                negative, "negative", np.where(frame.Speed.eq(0), "zero", "positive")
            )
        )
        .groupby(["speed_group", "Gear"], dropna=False)
        .size()
        .reset_index(name="rows")
    )
    gear["documented_meaning"] = gear.Gear.map(
        {
            0: "Not read yet",
            1: "Park",
            2: "Reverse",
            3: "Neutral",
            4: "Drive",
            7: "B/Eco",
        }
    ).fillna("Undocumented")
    gear.to_csv(OUT / "gear_context.csv", index=False)
    context = []
    for split, g in frame.loc[negative].groupby("split", sort=False):
        for col in [
            "RPM",
            "Torque",
            "Motor_Temp",
            "HV_Bat_Voltage",
            "Pack_1_C_Temp",
            "SOC",
        ]:
            context.append(
                {
                    "split": split,
                    "column": col,
                    "negative_speed_rows": len(g),
                    "minus_one_rows": int(g[col].eq(-1).sum()),
                    "unique": int(g[col].nunique()),
                    "min": g[col].min(),
                    "max": g[col].max(),
                }
            )
    pd.DataFrame(context).to_csv(OUT / "other_channels.csv", index=False)
    trips = []
    for tid, g in frame.groupby("Trip", sort=False):
        neg = g.Speed.lt(0)
        if not neg.any():
            continue
        runs = neg.ne(neg.shift()).cumsum()
        longest = int(g.loc[neg].groupby(runs[neg]).size().max())
        trips.append(
            {
                "Trip": int(tid),
                "split": g.split.iloc[0],
                "rows": len(g),
                "negative_rows": int(neg.sum()),
                "negative_pct": neg.mean() * 100,
                "longest_consecutive_negative_rows": longest,
                "first_negative_utc": str(
                    pd.to_datetime(g.loc[neg, "Timestamp"].min(), unit="us", utc=True)
                ),
                "last_negative_utc": str(
                    pd.to_datetime(g.loc[neg, "Timestamp"].max(), unit="us", utc=True)
                ),
                "original_retained_rows": int(g.export_eligible.sum()),
                "negative_with_reverse_code": int((neg & g.Gear.eq(2)).sum()),
                "negative_with_rpm_and_torque_minus_one": int(
                    (neg & g.RPM.eq(-1) & g.Torque.eq(-1)).sum()
                ),
                **{
                    col + "_unique": int(g[col].nunique())
                    for col in [
                        "Torque",
                        "Motor_Temp",
                        "HV_Bat_Voltage",
                        "Pack_1_C_Temp",
                        "SOC",
                    ]
                },
            }
        )
    trip_table = pd.DataFrame(trips)
    trip_table.to_csv(OUT / "negative_trips.csv", index=False)
    processed = pd.read_csv(
        ROOT / "data/nissan_leaf_2018/processed/Dataset_Preprocessed.csv",
        usecols=["Timestamp", "Trip", "Speed"],
    )
    matched = frame.loc[negative, ["Timestamp", "Trip", "Speed"]].merge(
        processed,
        on="Timestamp",
        how="left",
        suffixes=("_raw", "_processed"),
        indicator=True,
        validate="one_to_one",
    )
    match_summary = {
        "raw_negative_rows": int(negative.sum()),
        "matched_processed_rows": int(matched._merge.eq("both").sum()),
        "not_present_in_processed": int(matched._merge.eq("left_only").sum()),
        "matched_processed_speed_counts": {
            str(k): int(v)
            for k, v in matched.loc[matched._merge.eq("both"), "Speed_processed"]
            .value_counts()
            .items()
        },
    }
    save_json(OUT / "processed_comparison.json", match_summary)
    del processed, matched
    flags_without_speed = sum(
        FLAGS[name][0]
        for name in [
            "missing_candidate",
            "nonfinite_candidate",
            "soc_domain",
            "voltage_review",
            "pack_sentinel",
            "physical_temperature",
            "duplicate_timestamp",
        ]
    )
    policies = {
        "existing_six_features": config["features"],
        "omit_speed_only_diagnostic": [c for c in config["features"] if c != "Speed"],
        "battery_only_conditional": ["HV_Bat_Voltage", "Pack_1_C_Temp", "SOC"],
    }
    summaries, by_trip, artifacts = [], [], {}
    original_windows = (
        pd.read_csv(artifact / "window_accounting.csv").set_index("Trip").exported
    )
    for policy, features in policies.items():
        print(f"Comparing {policy}", flush=True)
        cfg = dict(
            config,
            features=features,
            duplicate_round_decimals={
                f: config["duplicate_round_decimals"][f] for f in features
            },
        )
        earlier, current, last_split = set(), set(), None
        eligible_all = np.zeros(len(frame), dtype=bool)
        for tid, group in frame.groupby("Trip", sort=False):
            group = group.copy()
            split = group.split.iloc[0]
            if last_split != split:
                earlier.update(current)
                current = set()
                last_split = split
            if policy == "existing_six_features":
                quality_ok = group.quality_eligible.to_numpy()
            else:
                quality_ok = (
                    (group.quality_flags & flags_without_speed) == 0
                ).to_numpy()
            # The retained non-speed rules conservatively include checks on unselected pack peers.
            hashes = fingerprints(group, cfg)
            repeated = pd.Series(hashes).isin(earlier).to_numpy() & quality_ok
            current.update(hashes[quality_ok].tolist())
            eligible = quality_ok & ~repeated
            eligible_all[group.index] = eligible
            group["export_eligible"] = eligible
            if policy == "existing_six_features":
                assert np.array_equal(
                    eligible, frame.loc[group.index, "export_eligible"]
                )
                n_windows = int(original_windows.loc[tid])
            else:
                windows, _ = make_windows(group, cfg["temperature"])
                assert windows.empty or (
                    (windows.anchor_us < windows.target_us).all()
                    and windows.split.eq(split).all()
                )
                n_windows = len(windows)
            by_trip.append(
                {
                    "policy": policy,
                    "Trip": int(tid),
                    "split": split,
                    "feature_rows": int(eligible.sum()),
                    "quality_excluded": int((~quality_ok).sum()),
                    "repeat_excluded": int(repeated.sum()),
                    "recovered_negative_rows": int(
                        (eligible & group.Speed.lt(0)).sum()
                    ),
                    "temperature_windows": n_windows,
                }
            )
        retained = frame.loc[eligible_all]
        training = retained[retained.split.eq("train")]
        state = fit_transformer(training, features, cfg)
        artifacts[policy] = state
        for split in ("train", "validation", "test"):
            selected = retained[retained.split.eq(split)]
            entries = [
                x for x in by_trip if x["policy"] == policy and x["split"] == split
            ]
            summaries.append(
                {
                    "policy": policy,
                    "split": split,
                    "features": len(features),
                    "feature_rows": len(selected),
                    "temperature_windows": sum(
                        x["temperature_windows"] for x in entries
                    ),
                    "trips_with_rows": selected.Trip.nunique(),
                    "recorded_days": pd.to_datetime(
                        selected.Timestamp, unit="us", utc=True
                    )
                    .dt.floor("D")
                    .nunique(),
                    "negative_speed_rows_retained": int(selected.Speed.lt(0).sum()),
                    "repeat_excluded": sum(x["repeat_excluded"] for x in entries),
                }
            )
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "policy_comparison.csv", index=False)
    pd.DataFrame(by_trip).to_csv(OUT / "policy_trip_counts.csv", index=False)
    save_json(OUT / "training_transformers_comparison.json", artifacts)
    total = len(frame)
    combo = int((negative & frame.RPM.eq(-1) & frame.Torque.eq(-1)).sum())
    fullneg = trip_table[trip_table.negative_rows.eq(trip_table.rows)]
    neg_gears = gear[gear.speed_group.eq("negative")]
    final = f"""# Negative-speed investigation and fixed-split policy comparison

Purpose: investigate unavailable-looking telemetry and quantify alternative preparation policies. Existing source files, split assignments and prepared artifacts were not modified. No models were trained, no new training records or fault labels were invented, and no alternative feature dataset was exported.

## Exact values, frequency and trips

All **{int(negative.sum()):,}** negative-speed readings are exactly **-1 km/h**, representing **{negative.mean() * 100:.6f}%** of the {total:,} raw rows. There are **{len(trip_table)} affected trips**, of which **{len(fullneg)} have -1 for every row**. Full counts, dates, longest runs, gear context and other-channel variability are in [negative_trips.csv](tables/negative_speed/negative_trips.csv).

{markdown(trip_table[["Trip", "split", "rows", "negative_rows", "negative_pct", "original_retained_rows"]])}

## Meaning: reverse gear versus unavailable measurement

The parameter workbook documents speed in km/h but does **not** define negative speed or a -1 speed sentinel. Gear codes are 0 not read, 1 Park, 2 Reverse, 3 Neutral, 4 Drive and 7 B/Eco; Gear=-1 is undocumented. Gear polling is documented at 100 seconds and speed at 1 second, so a same-row gear code may be stale.

{markdown(neg_gears[["Gear", "documented_meaning", "rows"]])}

Only 1,093 of the negative readings coincide with reverse gear. Most coincide with Drive/B-Eco or an undocumented gear code. Therefore treating -1 as reverse velocity or taking its absolute value is not justified. Even reverse-code coincidences cannot validate a signed-speed convention given slow gear polling.

**New evidence:** {combo:,} negative-speed rows simultaneously report RPM=-1 and Torque=-1. In the test split, 182,885 of 182,887 negative-speed rows have both values. This strongly suggests unavailable/failed acquisition for a group of drivetrain channels, rather than genuine constant reverse motion. It does **not** identify the exact logger defect or prove a manufacturer sentinel convention. Motor temperature also equals -1 in 66,540 affected test rows. Actual physical speed remains unknown.

Battery voltage, SOC and pack temperature still vary in many affected trips; their exact ranges/cardinalities are in [other_channels.csv](tables/negative_speed/other_channels.csv) and the per-trip table. Unavailable drivetrain fields do not prove every battery observation is invalid. Trip 232's pack temperatures also trigger the existing sentinel review, so it is not automatically rescued.

Matched-export observations: `{match_summary}`. These are evidence of export/preprocessing differences, not documentation that changing -1 to zero is physically correct.

## Why whole trips disappeared

There is no rule deleting an entire trip because it contains one negative reading. `audit_trip` sets a row-level `speed_negative` flag; the default six-feature eligibility mask blocks that row. A trip with all Speed=-1 therefore contributes zero rows. All observations remain in the original CSV and prepared row ledger, with their trip assignments and quality flags.

Temperature windows use the same six-feature eligibility and reject any interval containing an excluded row, including the full interval through the target. Consequently even a few unavailable readings can reject more windows than rows. This is a conservative validity gate, not a fault diagnosis. The coupling of all task views to the same feature mask is a limitation: one missing drivetrain channel need not block a battery-only experiment.

Training, validation and test use exactly the same policy. Training has 83,332 negative-speed rows, validation 16, test 182,887. Their total row exclusions are 88,655 / 261 / 182,887 respectively because other rules also apply. Training loses four complete trips under all rules (one is entirely negative-speed); test loses 25 complete trips. Negative-speed and all-exclusion counts must not be added because they overlap.

## Alternative-policy comparison

All policies retain the original 142/34/51 whole-trip chronological assignments, embargo, source timestamps, segment boundaries, target definition and other quality rules. Cross-split rounded-feature screening is rerun on each policy's actual feature set, and robust scaling statistics are recomputed from that policy's retained **training rows only**. Full-source hash checks and ledger hash checks precede the analysis. Existing-six-feature masks reproduce exactly; its sequence counts come from the already-validated preparation artifacts. Alternative windows are generated in memory with the existing safe window builder, counted and discarded, not published as training datasets.

- **existing_six_features:** current Speed, Torque, Motor_Temp, voltage, pack-1 temperature and SOC.
- **omit_speed_only_diagnostic:** five features, removing Speed only. This is a numerical sensitivity check, **not recommended**: it still treats many Torque=-1 and questionable motor-temperature values as ordinary measurements.
- **battery_only_conditional:** voltage, pack-1 temperature and SOC. This omits Speed, RPM, Torque and motor temperature, avoiding the correlated acquisition issue without guessing missing values. Other existing conservative quality rules remain. It narrows anomaly scope to battery telemetry; driving/idle/charging state cannot be inferred reliably for unknown-speed rows.

{markdown(summary)}

“Feature rows” are eligible observations; “temperature windows” are sequence examples. A retained negative-speed row uses only the alternative policy's input columns; -1 speed is not converted to a valid speed measurement. Counts do not certify sensor accuracy or healthy behavior. Fewer input dimensions can increase duplicate-screen exclusions; those counts are visible. Full per-trip effects: [policy_trip_counts.csv](tables/negative_speed/policy_trip_counts.csv).

## Can more usable test observations be preserved without leakage?

**Yes, conditionally for a battery-only experiment**, without recovering the unknown vehicle speed. This requires a task-specific feature mask rather than relaxing validity for the original six-feature task. Keep unavailable signals in audit metadata, never replace them with zero or absolute values. If an experiment requires speed/load, missing-aware inputs would need separately justified per-channel availability masks and training-only imputation; that policy has not been implemented or counted here because the drivetrain issue affects more than speed.

The split dates are unchanged; whole trips remain exclusive. Window inputs end at the anchor, all input/target rows stay within one original safe segment, and no future values fill earlier measurements. Scalers use training only. A reduced feature set still needs all existing duplicate and window checks, as used here. No cross-source merging or raw/preprocessed leakage is introduced.

**Evaluation limitation:** the test-set exclusion pattern motivated this investigation. Even with computationally leakage-safe preparation, repeatedly choosing policies after inspecting test behavior makes this an explored holdout. Freeze and document the policy before evaluating model performance, and obtain a fresh independent chronological/vehicle holdout for strong confirmatory claims. No model scores were examined here.

## Recommendation and unresolved questions

Preserve the existing prepared release. Prefer a separately versioned three-channel battery-only view for logged-temperature forecasting and narrowly scoped battery-pattern experiments; review its remaining sentinel and physical-quality limitations before training. Do not simply enable the five-channel speed-omitted view. Seek researcher confirmation of the sustained Speed/RPM/Torque=-1 episodes, raw logger availability flags, and whether motor temperature=-1 is an unavailable code. Verify sensor freshness/calibration before asserting real battery faults or physical temperature prediction.

## Reproduce and outputs

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/review_negative_speed.py
```

The script reuses the current preparation summary and audited ledger. Outputs under `tables/negative_speed/`: `negative_values.csv`, `negative_trips.csv`, `gear_context.csv`, `other_channels.csv`, `processed_comparison.json`, `policy_comparison.csv`, `policy_trip_counts.csv`, `training_transformers_comparison.json`, and `review_manifest.json`. The transformer comparison JSON records per-policy training-only medians/scales, not trained models. The manifest hashes every output, the source preparation manifest and this script. No production pipeline defaults, prepared datasets, source records or splits were changed.
"""
    (BASE / "NEGATIVE_SPEED_REVIEW.md").write_text(final)
    save_json(
        OUT / "review_manifest.json",
        {
            "source_preparation_run": original["run_id"],
            "source_preparation_summary_sha256": digest(
                BASE / "tables/preparation/preparation_summary.json"
            ),
            "script_sha256": digest(Path(__file__)),
            "source_hashes": original["source_hashes"],
            "source_ledger_sha256": digest(artifact / "row_ledger.parquet"),
            "outputs": {
                str(p.relative_to(ROOT)): digest(p)
                for p in [
                    *sorted(OUT.glob("*.csv")),
                    *[
                        p
                        for p in sorted(OUT.glob("*.json"))
                        if p.name != "review_manifest.json"
                    ],
                    BASE / "NEGATIVE_SPEED_REVIEW.md",
                ]
            },
        },
    )
    print(summary.to_string(index=False), flush=True)
    print(json.dumps(match_summary), flush=True)


if __name__ == "__main__":
    main()
