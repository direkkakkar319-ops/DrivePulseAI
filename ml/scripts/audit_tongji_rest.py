"""Audit the untouched Tongji release using only the Python standard library."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from xml.etree import ElementTree

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
DEFAULT_INPUT = pathlib.Path("data/automotive_prognostics/tongji_rest/v1/raw/data.zip")
DEFAULT_OUTPUT = pathlib.Path("ml/reports/data_validation/step2_tongji_rest.json")


def column_number(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def rows_from_xlsx(payload: bytes) -> list[dict[int, str]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(item.itertext()) for item in root.findall("m:si", NS)]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels
            if rel.attrib.get("Type", "").endswith("/worksheet")
        }
        sheet = workbook.find("m:sheets/m:sheet", NS)
        target = rel_map[sheet.attrib[REL_ID]].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ElementTree.fromstring(archive.read(target))
        result: list[dict[int, str]] = []
        for row in root.findall("m:sheetData/m:row", NS):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", NS):
                value = cell.find("m:v", NS)
                text = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and text.isdigit():
                    text = shared[int(text)]
                values[column_number(cell.attrib["r"])] = text
            if values:
                result.append(values)
        return result


def digest(path: pathlib.Path) -> dict[str, str | int]:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return {"bytes": size, "md5": md5.hexdigest(), "sha256": sha256.hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    aggregate: dict[str, object] = {
        "source": "Tongji real-world EV SOH release, Zenodo record 16868546",
        "raw_archive": str(args.input),
        "archive_digest": digest(args.input),
        "official_split": {
            "train_directory": "data/data_train",
            "test_directory": "data/data_test",
        },
        "files": {},
        "aggregate": {},
    }
    aggregate_rows: Counter[str] = Counter()
    aggregate_units: dict[str, set[str]] = defaultdict(set)
    aggregate_asset_rows: Counter[tuple[str, str]] = Counter()
    aggregate_headers: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    aggregate_soh: dict[str, list[float]] = defaultdict(list)
    aggregate_cap: dict[str, list[float]] = defaultdict(list)
    aggregate_backwards: Counter[str] = Counter()

    with zipfile.ZipFile(args.input) as archive:
        xlsx_names = [name for name in archive.namelist() if name.endswith(".xlsx")]
        for name in sorted(xlsx_names):
            split = "test" if "/data_test/" in name else "train"
            rows = rows_from_xlsx(archive.read(name))
            header = rows[0]
            names = {index: value for index, value in header.items()}
            kind = "slow" if "_slow_" in name else "fast"
            key = f"{split}_{kind}"
            stats = {
                "split": split,
                "kind": kind,
                "rows_including_header": len(rows),
                "data_rows": max(0, len(rows) - 1),
                "column_count": len(header),
                "columns": list(header.values()),
                "backward_t_start_steps": 0,
            }
            last_time: float | None = None
            for row in rows[1:]:
                aggregate_rows[key] += 1
                for field, target in (("soh", aggregate_soh), ("cap", aggregate_cap)):
                    index = next(
                        (i for i, value in names.items() if value == field), None
                    )
                    if index is not None:
                        try:
                            target[key].append(float(row.get(index, "")))
                        except ValueError:
                            pass
                identifier = next(
                    (i for i, value in names.items() if value == "car_identifier"), None
                )
                asset_id = row.get(identifier, "") if identifier is not None else ""
                if asset_id:
                    aggregate_units[split].add(asset_id)
                else:
                    asset_id = pathlib.PurePosixPath(name).stem
                aggregate_asset_rows[(split, asset_id)] += 1
                time_index = next(
                    (i for i, value in names.items() if value == "t_start"), None
                )
                if time_index is not None:
                    try:
                        current = float(row.get(time_index, ""))
                        if last_time is not None and current < last_time:
                            stats["backward_t_start_steps"] += 1
                            aggregate_backwards[key] += 1
                        last_time = current
                    except ValueError:
                        pass
            aggregate_headers[key].add(tuple(header.values()))
            aggregate["files"][name] = stats

    evaluation_ids = {
        asset_id
        for (source_split, asset_id) in aggregate_asset_rows
        if source_split == "test"
    }
    effective_rows: Counter[str] = Counter()
    for (source_split, asset_id), row_count in aggregate_asset_rows.items():
        partition = "test" if asset_id in evaluation_ids else "train"
        effective_rows[partition] += row_count

    summary: dict[str, object] = {
        "xlsx_files": len(aggregate["files"]),
        "rows_by_split_and_kind": dict(aggregate_rows),
        "independent_car_ids_by_split": {
            key: sorted(value) for key, value in aggregate_units.items()
        },
        "car_id_overlap_train_test": sorted(
            aggregate_units["train"] & aggregate_units["test"]
        ),
        "vehicle_disjoint_partition": {
            "protocol": "all rows for a known vehicle in the official test directory are assigned to evaluation; unidentified files retain file-stem identity",
            "train_asset_count": len(
                {
                    asset_id
                    for source_split, asset_id in aggregate_asset_rows
                    if source_split == "train"
                }
                - evaluation_ids
            ),
            "evaluation_asset_ids": sorted(evaluation_ids),
            "evaluation_asset_count": len(evaluation_ids),
            "rows_by_partition": dict(effective_rows),
            "source_train_overlap_assets_moved_to_evaluation": sorted(
                aggregate_units["train"] & evaluation_ids
            ),
        },
        "header_variants_by_split_and_kind": {
            key: len(value) for key, value in aggregate_headers.items()
        },
        "column_counts_by_split_and_kind": {
            key: sorted({len(header) for header in value})
            for key, value in aggregate_headers.items()
        },
        "backward_t_start_steps_by_split_and_kind": dict(aggregate_backwards),
        "value_ranges": {},
    }
    for key in sorted(set(aggregate_soh) | set(aggregate_cap)):
        summary["value_ranges"][key] = {}
        for field, values in (("soh", aggregate_soh[key]), ("cap", aggregate_cap[key])):
            if values:
                summary["value_ranges"][key][field] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": statistics.mean(values),
                }
    aggregate["aggregate"] = summary
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
