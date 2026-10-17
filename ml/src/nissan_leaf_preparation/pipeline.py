"""Bounded CSV scans, trip-grouped Parquet preparation and reproducible manifests."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .core import (
    AUDIT_COLUMNS,
    FLAGS,
    audit_trip,
    chronological_split,
    digest,
    fingerprints,
    fit_transformer,
    make_windows,
    parse_time,
    save_json,
    transform,
    validate_config,
    validate_schema,
)

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "ml/reports/nissan_leaf_2018"
DEFAULT_CONFIG = ROOT / "ml/notebooks/nissan_leaf_2018/config/preparation.json"


class ParquetSink:
    """Append one trip per row group with a stable, explicit schema."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.writer: pq.ParquetWriter | None = None

    def add(self, frame: pd.DataFrame) -> None:
        table = pa.Table.from_pandas(frame, preserve_index=False)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, table.schema, compression="zstd")
        self.writer.write_table(table)

    def close(self) -> None:
        if self.writer:
            self.writer.close()


def trip_chunks(
    path: Path, columns: list[str], chunk_size: int
) -> Iterator[pd.DataFrame]:
    """Yield complete consecutive trips, retaining at most a chunk plus one trip."""
    carry = pd.DataFrame()
    offset = 0
    seen = set()
    for chunk in pd.read_csv(
        path,
        usecols=columns,
        chunksize=chunk_size,
        dtype={
            c: ("int64" if c in {"Timestamp", "index"} else "float64") for c in columns
        },
    ):
        chunk["source_row"] = np.arange(offset, offset + len(chunk), dtype=np.int64)
        offset += len(chunk)
        joined = pd.concat([carry, chunk], ignore_index=True)
        if joined.Trip.isna().any():
            raise ValueError("Missing trip identifier")
        final = joined.Trip.iloc[-1]
        # Only the last contiguous block is carried, so a reused ID is detected.
        changes = joined.Trip.ne(joined.Trip.shift())
        last_start = int(np.flatnonzero(changes)[-1])
        complete, carry = joined.iloc[:last_start], joined.iloc[last_start:].copy()
        for _, trip in complete.groupby(
            complete.Trip.ne(complete.Trip.shift()).cumsum(), sort=False
        ):
            tid = trip.Trip.iloc[0]
            if tid in seen:
                raise ValueError(f"Noncontiguous reused trip ID: {tid}")
            seen.add(tid)
            yield trip
        if final in seen:
            raise ValueError(f"Noncontiguous reused trip ID: {final}")
    if not carry.empty:
        yield carry


def scan(
    version: str, path: Path, config: dict, directory: Path
) -> tuple[pd.DataFrame, dict]:
    """Audit both releases; only raw contributes measurements to preparation."""
    overview = json.loads((REPORT / f"tables/{version}/overview.json").read_text())
    validate_schema(
        pd.read_csv(path, nrows=0).columns.tolist(), overview["pandas_columns"]
    )
    raw_sink = (
        ParquetSink(directory / "raw_audited.parquet") if version == "raw" else None
    )
    flags_sink = (
        ParquetSink(directory / "processed_flagged_rows.parquet")
        if version == "processed"
        else None
    )
    counts = {name: 0 for name in FLAGS}
    missing = {name: 0 for name in AUDIT_COLUMNS}
    segment_offset, sessions, rows, flagged, eligible = 0, [], 0, 0, 0
    segments = []
    for trip in trip_chunks(path, AUDIT_COLUMNS, config["chunk_rows"]):
        frame = audit_trip(trip, config)
        frame["segment_id"] = frame.segment_in_trip.astype("int64") + segment_offset
        segment_offset = int(frame.segment_id.max()) + 1
        rows += len(frame)
        flagged += int(frame.quality_flags.ne(0).sum())
        eligible += int(frame.quality_eligible.sum())
        for name, (bit, _, _) in FLAGS.items():
            counts[name] += int(((frame.quality_flags & bit) != 0).sum())
        for name in missing:
            missing[name] += int(frame[name].isna().sum())
        sessions.append(
            {
                "Trip": int(frame.Trip.iloc[0]),
                "rows": len(frame),
                "start_us": int(frame.Timestamp.iloc[0]),
                "end_us": int(frame.Timestamp.iloc[-1]),
                "quality_eligible": int(frame.quality_eligible.sum()),
                "segments": int(frame.segment_id.nunique()),
                "recorded_dates": ";".join(
                    sorted(set(parse_time(frame.Timestamp).dt.strftime("%Y-%m-%d")))
                ),
            }
        )
        if raw_sink:
            raw_sink.add(frame)
            sg = frame.groupby("segment_id").agg(
                Trip=("Trip", "first"),
                start_us=("Timestamp", "min"),
                end_us=("Timestamp", "max"),
                rows=("Timestamp", "size"),
            )
            sg["duration_seconds"] = (sg.end_us - sg.start_us) / 1e6
            segments.append(sg.reset_index())
        if flags_sink:
            selected = frame.loc[
                frame.quality_flags.ne(0),
                ["source_row", "index", "Trip", "Timestamp", "quality_flags"],
            ]
            if len(selected):
                flags_sink.add(selected)
    if raw_sink:
        raw_sink.close()
        pd.concat(segments).to_csv(directory / "segments.csv", index=False)
    if flags_sink:
        flags_sink.close()
    if rows != overview["rows"]:
        raise ValueError("Source row count differs from prior EDA")
    return pd.DataFrame(sessions), {
        "rows": rows,
        "flagged_rows_any_flag": flagged,
        "no_row_flags": rows - flagged,
        "quality_eligible_rows": eligible,
        "quality_excluded_rows": rows - eligible,
        "flag_counts_overlapping": counts,
        "missing_counts": missing,
    }


def prepare(config_path: Path) -> dict:
    config = json.loads(config_path.read_text())
    validate_config(config)
    battery = config.get("view") == "battery_only_v1"
    parent_original, parent_hashes = None, {}
    if battery:
        from .battery import verify_parent

        parent_original, parent_hashes = verify_parent(ROOT, config)
    source_manifest = json.loads(
        (REPORT / "metadata/download_manifest.json").read_text()
    )
    verified = {}
    for item in source_manifest["files"]:
        path = (
            ROOT / item["repository_path"]
            if "repository_path" in item
            else REPORT / item["path"]
        )
        if digest(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Source provenance changed: {path}")
        verified[str(path.relative_to(ROOT))] = item["sha256"]
    code = {
        str(p.relative_to(ROOT)): digest(p)
        for p in sorted(Path(__file__).parent.glob("*.py"))
    }
    fingerprint = {
        "config": config,
        "source_hashes": verified,
        "code_hashes": code,
        "libraries": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "pyarrow": pa.__version__,
        },
    }
    if battery:
        fingerprint["immutable_parent_hashes"] = parent_hashes
        fingerprint["configuration_sha256"] = digest(config_path)
    import hashlib

    run_id = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode()
    ).hexdigest()[:16]
    parent = ROOT / "ml/artifacts/nissan_leaf_2018/preparation"
    parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(parent).free < 3 * 1024**3:
        raise ValueError(
            "At least 3 GiB free space required for bounded preparation outputs"
        )
    directory = Path(tempfile.mkdtemp(prefix=f"{run_id}.incomplete-", dir=parent))
    print(f"Preparation {run_id}: source hashes verified", flush=True)
    source_paths = {
        "raw": ROOT / "data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv",
        "processed": ROOT / "data/nissan_leaf_2018/processed/Dataset_Preprocessed.csv",
    }
    audit = {}
    for version in ("raw",) if battery else ("processed", "raw"):
        print(f"Auditing {version}", flush=True)
        sessions, audit[version] = scan(
            version, source_paths[version], config, directory
        )
        if version == "raw":
            if battery:
                from .battery import inherit_splits

                frozen_path = (
                    ROOT / parent_original["artifact_directory"] / "trip_splits.csv"
                )
                frozen = pd.read_csv(frozen_path)
                trips = inherit_splits(sessions, frozen)
                shutil.copyfile(
                    frozen_path, directory / "frozen_parent_trip_splits.csv"
                )
            else:
                trips = chronological_split(sessions, config)
    trips.to_csv(directory / "trip_splits.csv", index=False)
    split_for_trip = trips.set_index("Trip").split.to_dict()
    source = pq.ParquetFile(directory / "raw_audited.parquet")
    print("Preparing feature eligibility and observed sequence indices", flush=True)
    annotated_sink = ParquetSink(directory / "row_ledger.parquet")
    earlier_hashes: set[int] = set()
    current_hashes: set[int] = set()
    previous_split = None
    earlier_sorted = np.array([], dtype=np.uint64)
    train_frames = []
    screen_counts = {name: 0 for name in ("train", "validation", "test")}
    retained_counts = dict(screen_counts)
    window_frames, window_counts = [], []
    horizon_counts = []
    for group in range(source.num_row_groups):
        frame = source.read_row_group(group).to_pandas()
        split = split_for_trip[int(frame.Trip.iloc[0])]
        frame["split"] = split
        if split != previous_split:
            earlier_hashes.update(current_hashes)
            current_hashes = set()
            previous_split = split
            if battery:
                earlier_sorted = np.sort(np.fromiter(earlier_hashes, dtype=np.uint64))
        hashes = fingerprints(frame, config)
        if battery:
            from .battery import sorted_membership

            duplicate = sorted_membership(hashes, earlier_sorted)
        else:
            duplicate = pd.Series(hashes).isin(earlier_hashes).to_numpy()
        # Include all quality-eligible original states from earlier partitions in the screen.
        current_hashes.update(hashes[frame.quality_eligible].tolist())
        frame["cross_split_repeat"] = duplicate & frame.quality_eligible
        frame["export_eligible"] = frame.quality_eligible & ~duplicate
        screen_counts[split] += int(frame.cross_split_repeat.sum())
        retained_counts[split] += int(frame.export_eligible.sum())
        annotated_sink.add(frame)
        if split == "train":
            train_frames.append(
                frame.loc[frame.export_eligible, config["features"] + ["split"]]
            )
        windows, reasons = make_windows(frame, config["temperature"])
        if len(windows):
            window_frames.append(windows)
        window_counts.append(
            {"Trip": int(frame.Trip.iloc[0]), "split": split, **reasons}
        )
        # Feasibility descriptions use the training partition only, preventing horizon selection on test outcomes.
        if split == "train":
            for horizon in config["temperature"]["review_horizons_seconds"]:
                spec = dict(config["temperature"], horizon_seconds=horizon)
                if horizon == config["temperature"]["horizon_seconds"]:
                    n = len(windows)
                else:
                    alternate, _ = make_windows(frame, spec)
                    n = len(alternate)
                horizon_counts.append(
                    {
                        "Trip": int(frame.Trip.iloc[0]),
                        "horizon_seconds": horizon,
                        "eligible_windows": n,
                    }
                )
    annotated_sink.close()
    state = fit_transformer(
        pd.concat(train_frames, ignore_index=True), config["features"], config
    )
    del train_frames
    save_json(directory / "transformer.json", state)
    window_summary = pd.DataFrame(window_counts)
    window_summary.to_csv(directory / "window_accounting.csv", index=False)
    pd.DataFrame(horizon_counts).groupby(
        "horizon_seconds"
    ).eligible_windows.sum().to_csv(directory / "training_horizon_feasibility.csv")
    if not window_frames:
        raise ValueError(
            "No defensible temperature windows; review continuity and target quality"
        )
    windows = pd.concat(window_frames, ignore_index=True)
    for split in ("train", "validation", "test"):
        subset = windows[windows.split.eq(split)]
        subset.to_parquet(
            directory / f"temperature_{split}.parquet", index=False, compression="zstd"
        )
    del window_frames
    sinks = {
        split: ParquetSink(directory / f"features_{split}.parquet")
        for split in retained_counts
    }
    metadata_sinks = (
        {
            split: ParquetSink(directory / f"metadata_{split}.parquet")
            for split in retained_counts
        }
        if battery
        else {}
    )
    ledger = pq.ParquetFile(directory / "row_ledger.parquet")
    feature_days = {split: set() for split in retained_counts}
    for group in range(ledger.num_row_groups):
        frame = ledger.read_row_group(group).to_pandas()
        subset = frame[frame.export_eligible].copy()
        if subset.empty:
            continue
        split = subset.split.iloc[0]
        feature_days[split].update(parse_time(subset.Timestamp).dt.strftime("%Y-%m-%d"))
        transformed = transform(subset, state)
        # source_row is an audit join key, explicitly not a model feature.
        if battery:
            from .battery import companion_metadata

            metadata_sinks[split].add(companion_metadata(subset))
        else:
            transformed.insert(0, "source_row", subset.source_row.to_numpy())
        sinks[split].add(transformed.reset_index(drop=True))
    for sink in [*sinks.values(), *metadata_sinks.values()]:
        sink.close()
    # Audited rows now live in the ledger, so remove only this run's redundant intermediate.
    (directory / "raw_audited.parquet").unlink()
    split_summary = []
    # Feature-row counts need not equal safe-window counts: retain both explicitly.
    retained_trip_counts = {}
    for group in range(ledger.num_row_groups):
        info = ledger.read_row_group(
            group, columns=["Trip", "split", "export_eligible"]
        ).to_pandas()
        if info.export_eligible.any():
            split = info.split.iloc[0]
            retained_trip_counts[split] = retained_trip_counts.get(split, 0) + 1
    for split, group in trips.groupby("split", sort=False):
        source_days = {
            day for dates in group.recorded_dates for day in dates.split(";")
        }
        split_summary.append(
            {
                "split": split,
                "trips": len(group),
                "retained_trips": retained_trip_counts.get(split, 0),
                "source_rows": int(group.rows.sum()),
                "quality_excluded_rows": int(
                    group.rows.sum() - group.quality_eligible.sum()
                ),
                "cross_split_repeat_exclusions": screen_counts[split],
                "feature_rows": retained_counts[split],
                "temperature_sequences": int(windows.split.eq(split).sum()),
                "source_recorded_days": len(source_days),
                "retained_recorded_days": len(feature_days[split]),
                "start_utc": str(
                    pd.to_datetime(group.start_us.min(), unit="us", utc=True)
                ),
                "end_utc": str(pd.to_datetime(group.end_us.max(), unit="us", utc=True)),
            }
        )
    summary = {
        **fingerprint,
        "run_id": run_id,
        "artifact_directory": str((parent / run_id).relative_to(ROOT)),
        "audit": audit,
        "splits": split_summary,
        "transformer": state,
        "task_status": {
            "anomaly": "conditional",
            "energy": "blocked",
            "temperature": "conditional",
        },
        "window_accounting": window_summary.drop(columns=["Trip", "split"])
        .sum()
        .astype(int)
        .to_dict(),
        "cross_split_repeat_screen": screen_counts,
        "leakage_checks": {
            "trip_overlap": 0,
            "chronological_trip_overlap": 0,
            "cross_split_window_overlap": 0,
            "training_only_transformer": True,
            "source_versions_in_features": ["raw"],
        },
    }
    if battery:
        summary["parent_run_id"] = config["parent_run_id"]
        summary["original_artifacts_verified"] = len(parent_original["outputs"]) + 1
        reference = pd.read_csv(REPORT / "tables/negative_speed/policy_comparison.csv")
        reference = reference[
            reference.policy.eq("battery_only_conditional")
        ].set_index("split")
        summary["reference_comparison"] = [
            {
                "split": row["split"],
                "feature_rows_difference": row["feature_rows"]
                - int(reference.loc[row["split"], "feature_rows"]),
                "temperature_sequences_difference": row["temperature_sequences"]
                - int(reference.loc[row["split"], "temperature_windows"]),
            }
            for row in split_summary
        ]
    save_json(
        directory / "quality_flag_dictionary.json",
        {
            name: {"bit": bit, "category": category, "meaning": meaning}
            for name, (bit, category, meaning) in FLAGS.items()
        },
    )
    save_json(directory / "configuration.json", config)
    # Independent output checks must pass before publishing the run as complete.
    from .validation import validate_outputs

    summary["validation"] = validate_outputs(directory, config)
    summary["outputs"] = {
        p.name: {
            "bytes": p.stat().st_size,
            "sha256": digest(p),
            "rows": pq.ParquetFile(p).metadata.num_rows
            if p.suffix == ".parquet"
            else None,
            "schema": str(pq.ParquetFile(p).schema_arrow)
            if p.suffix == ".parquet"
            else None,
        }
        for p in sorted(directory.iterdir())
        if p.is_file()
    }
    for relative, expected_hash in {**verified, **code, **parent_hashes}.items():
        if digest(ROOT / relative) != expected_hash:
            raise ValueError(f"Source or code changed during run: {relative}")
    save_json(directory / "manifest.json", summary)
    final = parent / run_id
    if final.exists():
        old = json.loads((final / "manifest.json").read_text())
        if old != summary:
            raise ValueError(
                "Reproduction mismatch; both run directories preserved for investigation"
            )
        for name, info in old["outputs"].items():
            if digest(final / name) != info["sha256"]:
                raise ValueError("Prior output changed; refusing to replace it")
        shutil.rmtree(directory)
        print("Independent rerun matched every output checksum", flush=True)
    else:
        directory.rename(final)
    if battery:
        from .battery_report import write_report
    else:
        from .report import write_report
    write_report(summary, final)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "splits": split_summary,
                "validation": summary["validation"],
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    prepare(args.config)


if __name__ == "__main__":
    main()
