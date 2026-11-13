#!/usr/bin/env python3
"""Record the official Shenzhen Mendeley metadata without downloading its zip."""

from __future__ import annotations

import argparse
import json
import pathlib
import urllib.request

API = "https://data.mendeley.com/public-api/datasets/c7gg94tmvz/snapshot/3"
ZIP_API = "https://data.mendeley.com/api/datasets-v2/datasets/c7gg94tmvz/zip?version=3"
OUTPUT = pathlib.Path("ml/reports/data_validation/step2_shenzhen_ev_fault.json")


def get_json(url: str) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "DrivePulseAI-data-audit/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    snapshot = get_json(API)
    archive = get_json(ZIP_API)
    description = snapshot["description"]
    result = {
        "source": "Mendeley Data DOI 10.17632/c7gg94tmvz.3",
        "api_snapshot": API,
        "archive_api": ZIP_API,
        "license": snapshot["licence"]["short_name"],
        "publish_date": snapshot["publish_date"],
        "archive": archive,
        "metadata_assertions": {
            "charging_sequences": 21175,
            "sampling_points": 1547432,
            "ev_count": 10154,
            "sampling_interval": "1 minute",
            "label_definition": "1=faulty battery, 0=normal",
            "files": ["processed_data.xlsx", "processed_data_longer_than_30.xlsx"],
            "description_contains_expected_counts": all(
                token in description for token in ("21175", "1547432", "10154")
            ),
        },
        "acquisition_status": "blocked_http_403_from_official_s3_asset",
        "raw_asset_present": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
