#!/usr/bin/env python3
"""Download the official Tongji real-world EV SOH release without altering it."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import urllib.request

URL = "https://zenodo.org/api/records/16868546/files/data.zip/content"
OUTPUT = pathlib.Path("data/automotive_prognostics/tongji_rest/v1/raw/data.zip")
EXPECTED_BYTES = 129_606_252
EXPECTED_MD5 = "88c3832d748c0adf8caa94173aada563"


def digest(path: pathlib.Path) -> tuple[str, str, int]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return md5.hexdigest(), sha256.hexdigest(), size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        md5, sha256, size = digest(args.output)
        if md5 != EXPECTED_MD5 or size != EXPECTED_BYTES:
            raise SystemExit(
                f"existing file failed verification: md5={md5} bytes={size}"
            )
        print(f"already verified: {args.output} md5={md5} sha256={sha256} bytes={size}")
        return

    partial = args.output.with_suffix(args.output.suffix + ".part")
    request = urllib.request.Request(
        URL,
        # Zenodo's file endpoint rejects an explicit application/octet-stream
        # Accept header even though it returns that content type.
        headers={"User-Agent": "DrivePulseAI-data-audit/1.0", "Accept": "*/*"},
    )
    with (
        urllib.request.urlopen(request, timeout=120) as response,
        partial.open("wb") as handle,
    ):
        while block := response.read(1024 * 1024):
            handle.write(block)
    md5, sha256, size = digest(partial)
    if md5 != EXPECTED_MD5 or size != EXPECTED_BYTES:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"download failed verification: md5={md5} bytes={size}")
    partial.replace(args.output)
    print(f"downloaded: {args.output} md5={md5} sha256={sha256} bytes={size}")


if __name__ == "__main__":
    main()
