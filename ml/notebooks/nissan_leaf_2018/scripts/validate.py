"""Independently validate every CSV record width, source hash and report accounting."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
from acquire import BASE, sha256, source_path


def main() -> None:
    manifest = json.loads((BASE / "metadata/download_manifest.json").read_text())
    results = []
    for entry in manifest["files"]:
        path = source_path(entry["path"])
        assert path.stat().st_size == entry["bytes"], path
        assert sha256(path) == entry["sha256"], path
        if path.suffix != ".csv":
            continue
        version = Path(entry["path"]).parts[0]
        reports = BASE / "tables" / version
        overview = json.loads((reports / "overview.json").read_text())
        malformed = 0
        rows = 0
        with path.open(newline="") as f:
            reader = csv.reader(f, strict=True)
            header = next(reader)
            for record in reader:
                rows += 1
                malformed += len(record) != len(header)
        assert rows == overview["rows"], (rows, overview["rows"])
        assert len(header) == overview["columns"]
        assert malformed == 0, malformed
        dictionary = pd.read_csv(reports / "column_dictionary.csv")
        missing = pd.read_csv(reports / "missing_values.csv")
        sessions = pd.read_csv(reports / "sessions.csv")
        assert len(dictionary) == len(header)
        assert sessions.rows.sum() == rows
        assert missing.missing_count.sum() == overview["total_missing_cells"]
        assert dictionary.column.tolist() == overview["pandas_columns"]
        assert overview["sha256"] == entry["sha256"]
        results.append(
            {
                "version": version,
                "rows": rows,
                "columns": len(header),
                "malformed_records": malformed,
                "source_hash_matches": True,
                "report_accounting_matches": True,
            }
        )
    (BASE / "validation_results.json").write_text(
        json.dumps({"checks": results, "all_passed": True}, indent=2) + "\n"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
