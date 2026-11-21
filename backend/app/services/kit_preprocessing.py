"""Exact shared KIT clock/bucket statistics, extracted from the research recipe.

Ingestion policies (schema checking, rejecting invalid cells, limits) belong to
callers. This kernel does no filling, smoothing, unit conversion or resampling.
"""

import math
import statistics
from datetime import UTC, datetime

from .kit_samples import SIGNALS, WINDOW_SECONDS


def parse_time(value: str) -> float | None:
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M:%S.%f").replace(tzinfo=UTC)
    except ValueError:
        return None
    return (
        parsed.hour * 3600
        + parsed.minute * 60
        + parsed.second
        + parsed.microsecond / 1_000_000
    )


class KitWindowAccumulator:
    def __init__(self):
        self.buckets = {}
        self.previous_time = None
        self.segment_id = 0
        self.backward_jumps = 0
        self.duplicate_timestamps = 0

    def add(self, timestamp: float, values: list[float | None]) -> None:
        if self.previous_time is not None:
            if timestamp < self.previous_time:
                self.segment_id += 1
                self.backward_jumps += 1
            elif timestamp == self.previous_time:
                self.duplicate_timestamps += 1
        self.previous_time = timestamp
        key = (self.segment_id, math.floor(timestamp / WINDOW_SECONDS))
        bucket = self.buckets.setdefault(
            key, {"values": [[] for _ in SIGNALS], "rows": 0}
        )
        bucket["rows"] += 1
        for index, value in enumerate(values):
            if value is not None:
                bucket["values"][index].append(value)

    def windows(self):
        for (segment, window), bucket in sorted(self.buckets.items()):
            if any(not values for values in bucket["values"]):
                continue
            features = {}
            for name, values in zip(SIGNALS, bucket["values"], strict=True):
                features[f"{name}__median"] = statistics.median(values)
                features[f"{name}__std"] = statistics.pstdev(values)
                features[f"{name}__missing_fraction"] = 1 - len(values) / bucket["rows"]
            yield segment, window * WINDOW_SECONDS, features
