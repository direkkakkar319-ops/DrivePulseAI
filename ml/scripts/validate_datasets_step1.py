"""Read-only structural validation for the datasets used by DrivePulseAI.

This intentionally does not deserialize the 347-EV pickle payloads or mutate
raw files. It records provenance and structural evidence needed before any
model training decision.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import tarfile
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]


def row_digest(row: Iterable[str]) -> str:
    return hashlib.sha256("\x1f".join(row).encode("utf-8", "replace")).hexdigest()


def csv_stats(
    path: Path, *, skiprows: int = 0, timestamp_index: int | None = None
) -> dict:
    rows = 0
    widths = Counter()
    missing = 0
    duplicate_rows = 0
    seen: set[str] = set()
    backward = 0
    previous_time: float | None = None
    header: list[str] = []
    labels = Counter()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        for _ in range(skiprows):
            next(reader, None)
        header = next(reader, [])
        for row in reader:
            if not row:
                continue
            rows += 1
            widths[len(row)] += 1
            missing += sum(value.strip().lower() in {"", "na", "nan"} for value in row)
            digest = row_digest(row)
            if digest in seen:
                duplicate_rows += 1
            seen.add(digest)
            if header and "class" in header:
                labels[row[header.index("class")]] += 1
            if timestamp_index is not None and timestamp_index < len(row):
                value = row[timestamp_index].strip()
                try:
                    clock, fraction = (value.split(".", 1) + ["0"])[:2]
                    hours, minutes, seconds_text = clock.split(":")
                    seconds = (
                        int(hours) * 3600
                        + int(minutes) * 60
                        + int(seconds_text)
                        + float(f"0.{fraction}")
                    )
                except ValueError:
                    try:
                        seconds = float(value)
                    except ValueError:
                        continue
                if previous_time is not None and seconds < previous_time:
                    backward += 1
                previous_time = seconds
    return {
        "file": str(path.relative_to(ROOT)),
        "rows": rows,
        "header_columns": len(header),
        "header": header,
        "row_widths": dict(widths),
        "missing_cells": missing,
        "duplicate_rows": duplicate_rows,
        "backward_timestamp_steps": backward,
        "labels": dict(labels),
    }


def xlsx_sheet_stats(path: Path) -> dict:
    """Count rows/cells from a simple XLSX without requiring openpyxl."""

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared.append("".join(item.itertext()))
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels
            if rel.attrib.get("Type", "").endswith("/worksheet")
        }
        sheet = workbook.find("m:sheets/m:sheet", ns)
        rid = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = rel_map[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ElementTree.fromstring(archive.read(target))
        rows = 0
        widths = Counter()
        missing = 0
        digests: set[str] = set()
        duplicates = 0
        for row in root.findall("m:sheetData/m:row", ns):
            values: list[str] = []
            for cell in row.findall("m:c", ns):
                value = cell.find("m:v", ns)
                text = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and text.isdigit():
                    text = shared[int(text)]
                values.append(text)
            if not values:
                continue
            rows += 1
            widths[len(values)] += 1
            missing += sum(value == "" for value in values)
            digest = row_digest(values)
            if digest in digests:
                duplicates += 1
            digests.add(digest)
        return {
            "file": str(path.relative_to(ROOT)),
            "rows_including_header": rows,
            "data_rows": max(0, rows - 1),
            "row_widths": dict(widths),
            "missing_cells": missing,
            "duplicate_rows_including_header": duplicates,
        }


def archive_inventory(path: Path) -> dict:
    result = {"file": str(path.relative_to(ROOT)), "bytes": path.stat().st_size}
    with tarfile.open(path, mode="r:gz") as archive:
        members = archive.getmembers()
        result["members"] = len(members)
        result["pickle_members"] = sum(
            member.name.endswith(".pkl") for member in members
        )
        result["label_members"] = [
            member.name for member in members if "label" in member.name.lower()
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ml/reports/data_validation/step1.json"
    )
    args = parser.parse_args()

    result: dict = {
        "step": 1,
        "python": platform.python_version(),
        "datasets": {},
        "references_absent_locally": [],
    }

    kit_files = sorted(
        (ROOT / "data/automotive_obd/kit_obd/raw/recordings/OBD-II-Dataset").glob(
            "*.csv"
        )
    )
    result["datasets"]["kit_obd"] = {
        "files": len(kit_files),
        "per_file": [csv_stats(path, timestamp_index=0) for path in kit_files],
    }
    car_files = sorted((ROOT / "data/automotive_obd/carobd/raw").glob("*.csv"))
    result["datasets"]["carobd"] = {
        "files": len(car_files),
        "per_file": [csv_stats(path, timestamp_index=0) for path in car_files],
    }

    aps_dir = ROOT / "data/automotive_failure/scania_aps/raw"
    result["datasets"]["scania_aps"] = {
        "train": csv_stats(aps_dir / "aps_failure_training_set.csv", skiprows=20),
        "test": csv_stats(aps_dir / "aps_failure_test_set.csv", skiprows=20),
        "domain": "heavy truck; no vehicle/time IDs",
    }

    diesel_dir = ROOT / "data/automotive_obd/dieselobd/raw"
    result["datasets"]["dieselobd"] = {
        "train": xlsx_sheet_stats(diesel_dir / "MASTER_TRAIN_X.xlsx"),
        "test": xlsx_sheet_stats(diesel_dir / "MASTER_TEST_X.xlsx"),
        "domain": "provenance, units, labels and vehicle identities unverified",
    }

    component_dir = ROOT / "data/automotive_prognostics/scania_component_x/v3/raw"
    result["datasets"]["scania_component_x_v3"] = {
        "files": sorted(path.name for path in component_dir.glob("*.csv")),
        "domain": "Scania heavy-duty truck; excluded from passenger-car claims",
        "detailed_join_audit": "tasks_done.md Step 2",
    }

    ev_dir = ROOT / "data/automotive_prognostics/ev_fault_347/v1/raw"
    result["datasets"]["ev_fault_347"] = {
        "archives": [
            archive_inventory(path) for path in sorted(ev_dir.glob("*.tar.gz"))
        ],
        "domain": "EV; passenger-car body style unverified",
        "label_audit": "tasks_done.md Step 5; local 348 IDs vs paper 347",
        "pickle_payloads_deserialized": False,
    }

    capacity_dir = (
        ROOT / "data/automotive_prognostics/onroad_ev_capacity/source_release"
    )
    result["datasets"]["onroad_ev_capacity_20"] = {
        "archives": [
            {"file": str(path.relative_to(ROOT)), "bytes": path.stat().st_size}
            for path in sorted(capacity_dir.glob("#*.rar"))
        ],
        "domain": "BAIC EU500 commercial EVs; data-specific rights unresolved",
        "detailed_schema_audit": "tasks_done.md Step 4",
    }

    for name, patterns in {
        "ai4i": ["data/**/predictive_maintenance.csv"],
        "cmapss": ["data/**/train_FD*.txt"],
        "ved_dynamic": ["data/**/VED_Dynamic*"],
    }.items():
        if not any(any(ROOT.glob(pattern)) for pattern in patterns):
            result["references_absent_locally"].append(name)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output.relative_to(ROOT)),
                "datasets": {
                    key: (
                        value.get(
                            "files", value.get("archives", value.get("train", {}))
                        )
                    )
                    for key, value in result["datasets"].items()
                },
                "references_absent_locally": result["references_absent_locally"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
