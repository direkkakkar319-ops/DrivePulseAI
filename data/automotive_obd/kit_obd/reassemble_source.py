"""Reassemble the publisher's KIT BagIt archive from repository-sized parts."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "raw_chunks"
OUTPUT = ROOT / "raw" / "KIT_Automotive_OBD-II_Dataset.tar"
EXPECTED_MD5 = "22d9aac00d1a2b4c97aa35fd7a103ba4"


def main() -> None:
    """Join the three ordered parts and verify the publisher's archive MD5."""
    part_paths = sorted(PARTS.glob("KIT_Automotive_OBD-II_Dataset.tar.part-*"))
    if len(part_paths) != 3:
        raise SystemExit(f"Expected 3 source parts, found {len(part_paths)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.md5(usedforsecurity=False)
    with OUTPUT.open("wb") as destination:
        for part in part_paths:
            with part.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
                    digest.update(chunk)

    actual = digest.hexdigest()
    if actual != EXPECTED_MD5:
        OUTPUT.unlink(missing_ok=True)
        raise SystemExit(f"MD5 mismatch: expected {EXPECTED_MD5}, got {actual}")
    print(f"Reassembled and verified {OUTPUT} (MD5 {actual})")


if __name__ == "__main__":
    main()
