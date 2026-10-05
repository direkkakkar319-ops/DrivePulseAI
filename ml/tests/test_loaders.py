from pathlib import Path

import pandas as pd
import pytest

from src.data.loaders import load_aps, load_carobd, load_kit_obd

APS_DIR = (
    Path(__file__).parents[2]
    / "data"
    / "deferred"
    / "scania_aps"
    / "raw"
)
KIT_DIR = (
    Path(__file__).parents[2]
    / "data"
    / "passenger_cars"
    / "kit_obd"
    / "raw"
    / "recordings"
    / "OBD-II-Dataset"
)
CAROBD_DIR = (
    Path(__file__).parents[2] / "data" / "deferred" / "carobd" / "raw"
)

needs_data = pytest.mark.skipif(
    not APS_DIR.exists(), reason="APS data not checked out"
)


@needs_data
def test_load_aps_train():
    df = load_aps(APS_DIR, split="train")
    assert len(df) == 60000
    assert df["failure"].sum() == 1000
    assert df["source"].unique().tolist() == ["scania_aps"]


@needs_data
def test_load_aps_test():
    df = load_aps(APS_DIR, split="test")
    assert len(df) == 16000
    assert df["failure"].sum() == 375


@needs_data
def test_load_aps_bad_split():
    with pytest.raises(ValueError, match="split must be"):
        load_aps(APS_DIR, split="valid")


def test_load_aps_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_aps(tmp_path / "nope")


def test_load_kit_single_file(tmp_path: Path):
    rec = tmp_path / "trip.csv"
    rec.write_text(
        "Time,ECT,MAP,RPM,VSS,IAT,MAF,THR,AMB,PD,PE\n"
        "08:00:00.000,90,40,1500,50,30,10.0,20,25,10,12\n"
        "08:00:01.000,91,41,1600,55,31,11.0,21,25,11,12\n"
    )

    df = load_kit_obd(rec)
    assert len(df) == 2
    assert df["timestamp"].tolist() == [28800.0, 28801.0]
    assert df["engine_rpm"].tolist() == [1500, 1600]
    assert df["source"].unique().tolist() == ["kit_obd"]
    assert df["vehicle_id"].iloc[0] == "KIT-trip"


def test_load_kit_wrong_columns(tmp_path: Path):
    rec = tmp_path / "bad.csv"
    pd.DataFrame([[1, 2, 3]]).to_csv(rec, index=False)
    with pytest.raises(ValueError, match="expected 11 columns"):
        load_kit_obd(rec)


def test_load_kit_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="No KIT recordings"):
        load_kit_obd(tmp_path / "nope")


def test_load_carobd_trailing_field(tmp_path: Path):
    header = ",".join(f"C{i}" for i in range(27))
    rec = tmp_path / "drive1.csv"
    rec.write_text(header + "\n" + ",".join(["1"] * 28) + "\n")

    df = load_carobd(rec)
    assert len(df) == 1
    assert len(df.columns) == 27 + 2  # signals + vehicle_id/source
    assert df["source"].iloc[0] == "carobd"
    assert df["vehicle_id"].iloc[0] == "carOBD-drive1"


def test_load_carobd_bad_header(tmp_path: Path):
    rec = tmp_path / "bad.csv"
    rec.write_text("A,B,C\n1,2,3\n")
    with pytest.raises(ValueError, match="expected 27 header columns"):
        load_carobd(rec)


def test_load_carobd_missing_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="No carOBD recordings"):
        load_carobd(tmp_path / "nope")
