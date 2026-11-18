"""Load allowlisted KIT research assets without database or ML dependencies.

Canonical windows/pairs are also suitable as the output of a future raw-CSV
adapter. This module does not impute, resample, fit, or score observations.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import re
import zlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import TextIO

SIGNALS = (
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
)
FEATURE_NAMES = tuple(
    f"{signal}__{stat}"
    for signal in SIGNALS
    for stat in ("median", "std", "missing_fraction")
)
TARGET_NAMES = tuple(f"{signal}__median" for signal in SIGNALS)
METADATA_NAMES = (
    "split",
    "recording_date",
    "recording_id",
    "segment_id",
    "window_start_seconds",
)
WINDOW_SECONDS = 10
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "data/samples/kit/manifest.json"


class SampleDataError(ValueError):
    """An unknown sample or invalid packaged asset cannot be used for inference."""


class UnknownSampleError(SampleDataError):
    """A well-formed ID is not present in the packaged allowlist."""


@dataclass(frozen=True)
class KitWindow:
    recording_id: str
    recording_date: str
    split: str
    segment_id: int
    start_seconds: int
    features: dict[str, float]


@dataclass(frozen=True)
class KitWindowPair:
    current: KitWindow
    following: KitWindow

    def inference_request(self) -> dict:
        """Return exactly the existing KIT single-pair API request contract."""
        return {
            "schema_version": 1,
            "current_window_features": dict(self.current.features),
            "next_window_medians": {
                name: self.following.features[name] for name in TARGET_NAMES
            },
        }


@dataclass(frozen=True)
class KitSample:
    manifest: dict
    windows: tuple[KitWindow, ...]
    pairs: tuple[KitWindowPair, ...]


def validate_window(window: KitWindow) -> None:
    """Validate canonical windows from packaged data or a future CSV adapter."""
    try:
        if (
            not isinstance(window.recording_id, str)
            or not window.recording_id.strip()
            or date.fromisoformat(window.recording_date).isoformat()
            != window.recording_date
            or window.split not in {"train", "validation", "test", "uploaded"}
            or type(window.segment_id) is not int
            or window.segment_id < 0
            or type(window.start_seconds) is not int
            or not 0 <= window.start_seconds < 86400
            or window.start_seconds % WINDOW_SECONDS
            or set(window.features) != set(FEATURE_NAMES)
        ):
            raise ValueError
        for name, value in window.features.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError
            if name.endswith("__std") and value < 0:
                raise ValueError
            if name.endswith("__missing_fraction") and not 0 <= value < 1:
                raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise SampleDataError("Invalid canonical KIT window") from None


def read_prepared_windows(source: TextIO) -> tuple[KitWindow, ...]:
    """Validate the canonical KIT prepared schema; preserve source row order."""
    reader = csv.DictReader(source)
    if reader.fieldnames != list(METADATA_NAMES + FEATURE_NAMES):
        raise SampleDataError("Incompatible KIT prepared columns or feature order")
    windows = []
    previous: dict[tuple[str, int], int] = {}
    try:
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed prepared row")
            day = date.fromisoformat(row["recording_date"]).isoformat()
            segment = int(row["segment_id"])
            start = int(row["window_start_seconds"])
            values = {name: float(row[name]) for name in FEATURE_NAMES}
            window = KitWindow(
                row["recording_id"], day, row["split"], segment, start, values
            )
            validate_window(window)
            key = (row["recording_id"], segment)
            if key in previous and start <= previous[key]:
                raise ValueError("Duplicate or unordered prepared windows")
            previous[key] = start
            windows.append(window)
    except (ValueError, TypeError, csv.Error) as error:
        raise SampleDataError("Invalid KIT prepared row") from error
    if not windows:
        raise SampleDataError("KIT prepared asset contains no windows")
    return tuple(windows)


def make_window_pairs(windows: tuple[KitWindow, ...]) -> tuple[KitWindowPair, ...]:
    """Match training's recording/segment grouping, split check and 10s adjacency."""
    groups = defaultdict(list)
    for window in windows:
        groups[
            (
                window.recording_id,
                window.recording_date,
                window.segment_id,
                window.split,
            )
        ].append(window)
    pairs = []
    for group in groups.values():
        for current, following in pairwise(
            sorted(group, key=lambda w: w.start_seconds)
        ):
            if (
                current.split == following.split
                and following.start_seconds - current.start_seconds == WINDOW_SECONDS
            ):
                pairs.append(KitWindowPair(current, following))
    return tuple(pairs)


def _manifest_entries(manifest_path: Path) -> list[dict]:
    try:
        catalog = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = catalog["samples"]
        if catalog["schema_version"] != 1 or not isinstance(entries, list):
            raise ValueError
        ids = [entry["id"] for entry in entries]
        if len(ids) != len(set(ids)):
            raise SampleDataError("Duplicate KIT sample IDs")
        if any(
            not isinstance(value, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value)
            for value in ids
        ):
            raise ValueError
        return entries
    except SampleDataError:
        raise
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        raise SampleDataError(
            "Missing, corrupt or incompatible KIT sample manifest"
        ) from None


def sample_ids(*, manifest_path: Path = MANIFEST_PATH) -> tuple[str, ...]:
    return tuple(entry["id"] for entry in _manifest_entries(manifest_path))


def load_sample(sample_id: str, *, manifest_path: Path = MANIFEST_PATH) -> KitSample:
    """Resolve only manifest IDs; check compressed bytes before interpreting data."""
    try:
        samples = _manifest_entries(manifest_path)
        matches = [entry for entry in samples if entry["id"] == sample_id]
        if len(matches) != 1:
            raise UnknownSampleError("Unknown KIT sample ID")
        entry = matches[0]
        asset_name = entry["asset_file"]
        root = manifest_path.parent.resolve()
        asset = (root / asset_name).resolve()
        if Path(asset_name).name != asset_name or asset.parent != root:
            raise SampleDataError("Invalid KIT asset location")
        if (
            entry["window_seconds"] != WINDOW_SECONDS
            or entry["feature_names"] != list(FEATURE_NAMES)
            or entry["target_names"] != list(TARGET_NAMES)
        ):
            raise SampleDataError("Incompatible KIT sample schema")
        compressed = asset.read_bytes()
        if hashlib.sha256(compressed).hexdigest() != entry["asset_sha256"]:
            raise SampleDataError("KIT sample checksum mismatch")
        with gzip.open(
            io.BytesIO(compressed), "rt", encoding="utf-8", newline=""
        ) as data:
            windows = read_prepared_windows(data)
        if any(
            w.recording_id != entry["recording_id"]
            or w.recording_date != entry["recording_date"]
            or w.split != entry["source_split"]
            or w.segment_id not in entry["segment_ids"]
            for w in windows
        ):
            raise SampleDataError("KIT sample provenance mismatch")
        pairs = make_window_pairs(windows)
        if (
            len(windows) != entry["window_count"]
            or len(pairs) != entry["valid_pair_count"]
            or not pairs
        ):
            raise SampleDataError("KIT sample window/pair count mismatch")
        return KitSample(entry, windows, pairs)
    except SampleDataError:
        raise
    except (
        OSError,
        EOFError,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
        zlib.error,
    ) as error:
        raise SampleDataError(
            "Missing, corrupt or incompatible KIT sample package"
        ) from error
