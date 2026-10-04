"""Verify retained raw files and every recorded move/extraction against audit SHA-256 values."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "data" / "audit"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


checks = 0
for record in json.loads((AUDIT / "inventory-after.json").read_text()):
    path = ROOT / record["path"]
    assert path.stat().st_size == record["bytes"], path
    assert digest(path) == record["sha256"], path
    checks += 1
changes = json.loads((AUDIT / "changes.json").read_text())
for record in changes:
    if "to" in record:
        path = ROOT / record["to"]
        assert digest(path) == record["sha256"], path
        checks += 1
    else:
        assert record["action"] == "remove_verified_extracted_archive"
        assert not (ROOT / record["from"]).exists()
        assert any(
            c["action"] == "extract" and c["from"].startswith(record["from"] + "::")
            for c in changes
        )
for record in json.loads((AUDIT / "inventory-before.json").read_text()):
    if record["path"] == "data/README.md":
        continue  # Documentation intentionally replaced; not a raw source file.
    matches = [c for c in changes if c["from"] == record["path"]]
    assert len(matches) == 1, record["path"]
    assert matches[0]["sha256"] == record["sha256"], record["path"]
print(f"PASS: {checks} SHA-256 checks; every original source file accounted for.")
