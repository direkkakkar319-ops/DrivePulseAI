"""Read-only byte-preservation and download verification."""

import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]


def main() -> None:
    moves = json.loads(
        (DATA / "organization/passenger-car-move-manifest.json").read_text()
    )
    additions = json.loads(
        (DATA / "organization/new-downloads-manifest.json").read_text()
    )
    for entry in moves["moves"]:
        path = DATA / entry["after"]
        if (
            path.stat().st_size != entry["bytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise ValueError(f"Moved file changed: {path}")
    for entry in additions["files"]:
        path = DATA / entry["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Downloaded file changed: {path}")
    edge = DATA / "passenger_cars/edge_impulse_airleak"
    manifest = json.loads((edge / "download_manifest.json").read_text())
    actual = {str(p.relative_to(edge)) for p in (edge / "raw").rglob("*.json")}
    listed = {entry["path"] for entry in manifest["samples"]}
    if actual != listed or len(listed) != 230:
        raise ValueError("Public sample inventory differs from manifest")
    for entry in manifest["samples"]:
        if (
            hashlib.sha256((edge / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError(f"Sample changed: {entry['id']}")
    print(
        f"Verified {len(moves['moves'])} moved files, {len(additions['files'])} additions and 230 public samples."
    )
    print(
        "Byte preservation does not certify labels, fault detection or split independence."
    )


if __name__ == "__main__":
    main()
