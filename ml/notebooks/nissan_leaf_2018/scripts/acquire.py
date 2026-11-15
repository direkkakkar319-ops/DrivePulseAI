"""Download official source files unchanged and record sizes, headers and SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "data/nissan_leaf_2018"
BASE = ROOT / "ml/reports/nissan_leaf_2018"


def source_path(relative: str) -> Path:
    """Resolve manifest source paths across dataset and documentation roots."""
    return (BASE if relative.startswith("metadata/") else DATA) / relative


URL = "https://ubilab.mpu.edu.mo/"
FILES = {
    "processed/Dataset_Preprocessed.csv": 443747562,
    "raw/Dataset_NissanLeaf-2021_2022.csv": 1538549900,
    "metadata/Nissan_Leaf_Model2018_Data_Description.xlsx": 28139,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--finalize-existing",
        action="store_true",
        help="Validate already downloaded .part files without network calls",
    )
    p.add_argument("--version", choices=["both", "processed"], default="both")
    args = p.parse_args()
    if shutil.disk_usage(BASE).free < 4 * 1024**3:
        raise RuntimeError("At least 4 GiB free space required")
    source = BASE / "metadata/source_page.html"
    if not source.exists() and not args.finalize_existing:
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "curl",
                "-L",
                "--fail",
                "--connect-timeout",
                "20",
                "--max-time",
                "90",
                URL + "data.html",
                "-o",
                str(source),
            ],
            check=True,
        )
    records = []
    for relative, expected in FILES.items():
        if args.version == "processed" and relative.startswith("raw/"):
            continue
        dest = source_path(relative)
        dest.parent.mkdir(parents=True, exist_ok=True)
        header = BASE / "metadata" / f"{dest.name}.headers.txt"
        if not dest.exists():
            part = dest.with_suffix(dest.suffix + ".part")
            if not args.finalize_existing:
                subprocess.run(
                    [
                        "curl",
                        "-L",
                        "--fail",
                        "--connect-timeout",
                        "20",
                        "--max-time",
                        "3600",
                        "--retry",
                        "2",
                        "--silent",
                        "--show-error",
                        "-D",
                        str(header),
                        URL + dest.name,
                        "-o",
                        str(part),
                    ],
                    check=True,
                )
            if not part.exists() or part.stat().st_size != expected:
                raise RuntimeError(
                    f"{relative}: download incomplete or publisher size changed; expected {expected} bytes. Inspect headers before updating expected size."
                )
            part.rename(dest)
        if dest.stat().st_size != expected:
            raise ValueError(f"Unexpected source size: {dest}")
        record = {
            "path": relative,
            "repository_path": str(dest.relative_to(ROOT)),
            "url": URL + dest.name,
            "filename": dest.name,
            "bytes": dest.stat().st_size,
            "sha256": sha256(dest),
            "compression": "none (CSV); XLSX is a ZIP container"
            if dest.suffix == ".xlsx"
            else "none",
            "download_status": "complete",
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if dest.suffix == ".xlsx":
            with zipfile.ZipFile(dest) as archive:
                record["uncompressed_member_bytes"] = sum(
                    info.file_size for info in archive.infolist()
                )
        if header.exists():
            text = header.read_text()
            record["http_status"] = re.findall(r"HTTP/\S+ (\d+)", text)
            record["last_modified"] = re.findall(r"(?im)^Last-Modified:\s*(.+)$", text)
            record["etag"] = re.findall(r"(?im)^Etag:\s*(.+)$", text)
            # Expiring response cookies are not provenance; do not track them.
            header.write_text(
                "\n".join(
                    line
                    for line in text.splitlines()
                    if not line.lower().startswith("set-cookie:")
                )
                + "\n"
            )
        records.append(record)
    source = BASE / "metadata/source_page.html"
    if source.exists():
        records.append(
            {
                "path": "metadata/source_page.html",
                "url": URL + "data.html",
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
                "download_status": "complete",
            }
        )
    (BASE / "metadata/download_manifest.json").write_text(
        json.dumps(
            {
                "files": records,
                "license": "No explicit dataset license found on source page or workbook; source requests research citation. Public access is not a grant of unrestricted reuse.",
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(records, indent=2))


if __name__ == "__main__":
    main()
