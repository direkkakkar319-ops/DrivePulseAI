"""Reassemble the Oxford MAT source from repository-sized parts and verify SHA-256."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "raw_chunks"
OUTPUT = ROOT / "raw" / "Oxford_Battery_Degradation_Dataset_1.mat"
EXPECTED_SHA256 = "a8f0b928f4ea77d7ba98b97194b78cc77336f2338fee8b57573d043f0cf26781"


def main() -> None:
    """Join ordered parts, then fail if the result differs from the source hash."""
    part_paths = sorted(PARTS.glob("Oxford_Battery_Degradation_Dataset_1.mat.part-*"))
    if len(part_paths) != 64:
        raise SystemExit(f"Expected 64 source parts, found {len(part_paths)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with OUTPUT.open("wb") as destination:
        for part in part_paths:
            with part.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
                    digest.update(chunk)
    actual = digest.hexdigest()
    if actual != EXPECTED_SHA256:
        OUTPUT.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 mismatch: expected {EXPECTED_SHA256}, got {actual}")
    print(f"Reassembled and verified {OUTPUT} ({actual})")


if __name__ == "__main__":
    main()
