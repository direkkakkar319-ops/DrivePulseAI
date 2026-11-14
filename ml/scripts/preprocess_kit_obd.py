"""Create an unlabeled, recording-safe KIT OBD window dataset for exploration.

Run from the repository root with ``python3 ml/scripts/preprocess_kit_obd.py``.
Generated files are local-only and intentionally gitignored.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data/automotive_obd/kit_obd/raw/recordings/OBD-II-Dataset"
OUTPUT_DIR = ROOT / "data/automotive_obd/kit_obd/processed"
WINDOW_SECONDS = 10
DATE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
SIGNALS = [
    "coolant_temp_c",
    "map_kpa",
    "engine_rpm",
    "speed_kmph",
    "intake_air_temp_c",
    "maf_gs",
    "throttle_pct",
    "ambient_air_temp_c",
    "pedal_d_pct",
    "pedal_e_pct",
]
EXPECTED_WIDTH = 1 + len(SIGNALS)


def recording_date(filename: str) -> str:
    match = DATE_PATTERN.match(filename)
    if match is None:
        raise ValueError(f"Cannot parse calendar date from recording {filename!r}")
    date.fromisoformat(match.group(1))
    return match.group(1)


def date_partitions(dates: list[str]) -> dict[str, str]:
    """Chronologically hold out dates so trips from a day cannot cross splits."""
    ordered = sorted(set(dates))
    if len(ordered) < 3:
        raise ValueError("At least three distinct recording dates are required")
    train_end = max(1, int(len(ordered) * 0.70))
    validation_end = max(train_end + 1, int(len(ordered) * 0.85))
    validation_end = min(validation_end, len(ordered) - 1)
    return {
        day: (
            "train" if i < train_end else "validation" if i < validation_end else "test"
        )
        for i, day in enumerate(ordered)
    }


def parse_time(value: str) -> float | None:
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M:%S.%f")
    except ValueError:
        return None
    return (
        parsed.hour * 3600
        + parsed.minute * 60
        + parsed.second
        + parsed.microsecond / 1_000_000
    )


def process_file(path: Path, split: str) -> tuple[list[dict], dict]:
    day = recording_date(path.name)
    recording_id = f"KIT-{path.stem}"
    # Each bucket keeps only one 10-second window's values in memory.
    buckets: dict[tuple[int, int], dict] = {}
    previous_time = None
    segment_id = 0
    backward_jumps = 0
    invalid_timestamp_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as raw:
        reader = csv.reader(raw)
        header = next(reader, None)
        if header is None or len(header) != EXPECTED_WIDTH:
            raise ValueError(f"{path.name}: expected {EXPECTED_WIDTH} columns")
        for line_number, row in enumerate(reader, start=2):
            if len(row) != EXPECTED_WIDTH:
                raise ValueError(
                    f"{path.name}:{line_number}: expected {EXPECTED_WIDTH} fields, got {len(row)}"
                )
            timestamp = parse_time(row[0])
            if timestamp is None:
                invalid_timestamp_rows += 1
                continue
            if previous_time is not None and timestamp < previous_time:
                segment_id += 1
                backward_jumps += 1
            previous_time = timestamp
            elapsed = timestamp
            window_id = math.floor(elapsed / WINDOW_SECONDS)
            key = (segment_id, window_id)
            bucket = buckets.setdefault(
                key, {"values": [[] for _ in SIGNALS], "rows": 0}
            )
            bucket["rows"] += 1
            for index, raw_value in enumerate(row[1:]):
                try:
                    value = float(raw_value.strip())
                except ValueError:
                    continue
                if math.isfinite(value):
                    bucket["values"][index].append(value)

    result = []
    for (segment, window), bucket in sorted(buckets.items()):
        values = bucket["values"]
        # Require at least one actual observation for each signal; do not fill.
        if any(not signal_values for signal_values in values):
            continue
        output = {
            "split": split,
            "recording_date": day,
            "recording_id": recording_id,
            "segment_id": segment,
            "window_start_seconds": window * WINDOW_SECONDS,
        }
        for name, signal_values in zip(SIGNALS, values):
            output[f"{name}__median"] = statistics.median(signal_values)
            output[f"{name}__std"] = statistics.pstdev(signal_values)
            output[f"{name}__missing_fraction"] = (
                1 - len(signal_values) / bucket["rows"]
            )
        result.append(output)
    return result, {
        "recording_id": recording_id,
        "date": day,
        "invalid_timestamp_rows": invalid_timestamp_rows,
        "backward_jumps": backward_jumps,
        "window_count": len(result),
    }


def main() -> None:
    files = sorted(RAW_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No KIT recordings found at {RAW_DIR}")
    partitions = date_partitions([recording_date(file.name) for file in files])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "windows_10s.csv.gz"
    audit = []
    counts = defaultdict(int)
    with gzip.open(output_path, "wt", encoding="utf-8", newline="") as compressed:
        writer = None
        for path in files:
            windows, record_audit = process_file(
                path, partitions[recording_date(path.name)]
            )
            audit.append(record_audit)
            for window in windows:
                if writer is None:
                    writer = csv.DictWriter(compressed, fieldnames=list(window))
                    writer.writeheader()
                writer.writerow(window)
                counts[window["split"]] += 1

    summary = {
        "dataset": "KIT Automotive OBD-II",
        "source_doi": "10.35097/1130",
        "purpose": "unlabeled exploratory telemetry anomaly detection",
        "window_seconds": WINDOW_SECONDS,
        "features": SIGNALS,
        "aggregation": "per-signal median, population standard deviation, missing fraction",
        "missing_value_policy": "no imputation; discard windows missing any signal entirely",
        "timestamp_policy": "retain source order; start a new segment on each backward jump",
        "split_policy": "chronological 70/15/15 calendar-date split; all trips on a date stay together",
        "identity_limit": "recording/trip IDs are not verified vehicle identities",
        "label_limit": "no failure labels; filename road-condition text is not a fault label",
        "recordings": len(audit),
        "dates_by_split": {
            split: sorted(
                day for day, assigned in partitions.items() if assigned == split
            )
            for split in ("train", "validation", "test")
        },
        "window_counts_by_split": dict(counts),
        "recording_audit": audit,
    }
    (OUTPUT_DIR / "preprocessing_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT_DIR),
                "recordings": len(audit),
                "window_counts_by_split": dict(counts),
                "backward_jumps": sum(item["backward_jumps"] for item in audit),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
