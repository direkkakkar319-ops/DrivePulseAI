#!/usr/bin/env python3
"""Download the official Mendeley Shenzhen EV fault release, unchanged."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import urllib.request

METADATA_URL = (
    "https://data.mendeley.com/api/datasets-v2/datasets/c7gg94tmvz/zip?version=3"
)
DEFAULT_OUTPUT = pathlib.Path(
    "data/automotive_prognostics/shenzhen_ev_fault/v3/raw/dataset.zip"
)
EXPECTED_BYTES = 207_174_326
EXPECTED_SHA256 = "6b5c77c331e173ac6cab7a0ff2791320cb4fe4c3ffbe9d90205902dbc703eac3"


def sha256(path: pathlib.Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return digest.hexdigest(), size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        digest, size = sha256(args.output)
        if digest != EXPECTED_SHA256 or size != EXPECTED_BYTES:
            raise SystemExit(
                f"existing file failed verification: sha256={digest} bytes={size}"
            )
        print(f"already verified: {args.output} sha256={digest} bytes={size}")
        return

    metadata_request = urllib.request.Request(
        METADATA_URL,
        headers={
            "User-Agent": "DrivePulseAI-data-audit/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(metadata_request, timeout=30) as response:
        metadata = response.read().decode("utf-8")
    import json

    release = json.loads(metadata)
    url = release["url"]
    if (
        release.get("size") != EXPECTED_BYTES
        or release.get("sha256_hash") != EXPECTED_SHA256
    ):
        raise SystemExit(f"official metadata changed: {release}")

    partial = args.output.with_suffix(args.output.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "DrivePulseAI-data-audit/1.0",
            "Accept": "application/zip",
        },
    )
    with (
        urllib.request.urlopen(request, timeout=120) as response,
        partial.open("wb") as handle,
    ):
        while block := response.read(1024 * 1024):
            handle.write(block)
    digest, size = sha256(partial)
    if digest != EXPECTED_SHA256 or size != EXPECTED_BYTES:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"download failed verification: sha256={digest} bytes={size}")
    partial.replace(args.output)
    print(f"downloaded: {args.output} sha256={digest} bytes={size}")


if __name__ == "__main__":
    main()
