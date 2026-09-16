import json
from pathlib import Path

import pandas as pd
import pytest
from src.data.loaders import load_simulated


def test_load_simulated_single_csv(tmp_path: Path):
    csv_file = tmp_path / "trip_01.csv"
    df_raw = pd.DataFrame(
        {
            "ENGINE_RUN_TINE ()": [1, 2],
            "ENGINE_RPM ()": [1500, 1600],
            "VEHICLE_SPEED ()": [45, 50],
            "CONTROL_MODULE_VOLTAGE ()": [13.8, 14.1],
        }
    )
    df_raw.to_csv(csv_file, index=False)

    df = load_simulated(csv_file)
    assert len(df) == 2
    assert "timestamp" in df.columns
    assert "engine_rpm" in df.columns
    assert "speed_kmph" in df.columns
    assert "battery_voltage" in df.columns
    assert df["source"].iloc[0] == "simulated"
    assert df["vehicle_id"].iloc[0] == "SIM-trip_01"


def test_load_simulated_single_jsonl(tmp_path: Path):
    jsonl_file = tmp_path / "trip_json.jsonl"
    records = [
        {"ENGINE_RPM ()": 2000, "VEHICLE_SPEED ()": 60},
        {"ENGINE_RPM ()": 2100, "VEHICLE_SPEED ()": 65},
    ]
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    df = load_simulated(jsonl_file)
    assert len(df) == 2
    assert "engine_rpm" in df.columns
    assert "speed_kmph" in df.columns
    assert df["source"].iloc[0] == "simulated"
    assert df["vehicle_id"].iloc[0] == "SIM-trip_json"


def test_load_simulated_directory(tmp_path: Path):
    file1 = tmp_path / "vehicle_101.csv"
    file2 = tmp_path / "vehicle_102.csv"
    pd.DataFrame({"ENGINE_RPM ()": [1000]}).to_csv(file1, index=False)
    pd.DataFrame({"ENGINE_RPM ()": [2000]}).to_csv(file2, index=False)

    df = load_simulated(tmp_path, pattern="*.csv")
    assert len(df) == 2
    assert set(df["vehicle_id"]) == {"SIM-vehicle_101", "SIM-vehicle_102"}
    assert df["source"].unique().tolist() == ["simulated"]
    assert "engine_rpm" in df.columns


def test_load_simulated_directory_empty_raises(tmp_path: Path):
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No matching files found"):
        load_simulated(empty_dir)


def test_load_simulated_missing_path_raises(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.csv"
    with pytest.raises(FileNotFoundError, match="File or directory not found"):
        load_simulated(non_existent)
