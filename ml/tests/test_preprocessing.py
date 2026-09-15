import sys
from pathlib import Path
import pandas as pd
import numpy as np


sys.path.append(str(Path(__file__).resolve().parents[1] / "src" / "data"))

from preprocessing import PreProcessing


def test_clean_drops_duplicates():
    df = pd.DataFrame({"vehicle_id": ["A", "A", "A"], "speed": [10, 10, 20]})
    cleaned = PreProcessing.clean(df, drop_duplicates=True)
    assert len(cleaned) == 2
    assert cleaned.iloc[0]["speed"] == 10
    assert cleaned.iloc[1]["speed"] == 20


def test_clean_fills_dropouts():
    df = pd.DataFrame({"vehicle_id": ["A", "A", "A"], "speed": [10, np.nan, 30]})
    # ffill should fill NaN with 10
    cleaned = PreProcessing.clean(df, drop_duplicates=False, fill_dropouts=True)
    assert cleaned.iloc[1]["speed"] == 10.0


def test_scale():
    df = pd.DataFrame(
        {"vehicle_id": ["A", "B"], "speed": [10.0, 20.0], "rpm": [1000.0, 2000.0]}
    )
    scaled, scaler = PreProcessing.scale(df)

    assert "vehicle_id" in scaled.columns
    assert scaled["vehicle_id"].iloc[0] == "A"
    assert "speed" in scaled.columns

    # StandardScaler transforms [10, 20] -> [-1, 1]
    assert np.isclose(scaled["speed"].iloc[0], -1.0)
    assert np.isclose(scaled["speed"].iloc[1], 1.0)
    assert scaler is not None


def test_scale_with_existing_scaler():
    df_train = pd.DataFrame({"speed": [10.0, 20.0]})
    _, scaler = PreProcessing.scale(df_train)

    df_test = pd.DataFrame({"speed": [30.0]})
    scaled_test, out_scaler = PreProcessing.scale(df_test, scaler=scaler)

    assert out_scaler is scaler
    # mean is 15, std is 5. (30 - 15) / 5 = 3
    assert np.isclose(scaled_test["speed"].iloc[0], 3.0)


def test_make_time_windows():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A", "A", "B", "B", "B"],
            "speed": [1, 2, 3, 4, 5, 6],
            "source": ["simulated"] * 6,
        }
    )
    # window_size=2, step=1
    # For A: [1,2], [2,3]
    # For B: [4,5], [5,6]
    windows = PreProcessing.make_time_windows(df, window_size=2, step=1)

    assert windows.shape == (4, 2, 1)  # 4 windows, size 2, 1 feature (speed)
    assert np.array_equal(windows[0, :, 0], [1, 2])
    assert np.array_equal(windows[1, :, 0], [2, 3])
    assert np.array_equal(windows[2, :, 0], [4, 5])
    assert np.array_equal(windows[3, :, 0], [5, 6])


def test_train_val_test_split_random():
    df = pd.DataFrame({"val": range(100)})
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.2, time_ordered=False
    )

    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20

    # Check that they are disjoint
    train_vals = set(train["val"])
    val_vals = set(val["val"])
    assert len(train_vals.intersection(val_vals)) == 0


def test_train_val_test_split_time_ordered():
    df = pd.DataFrame({"val": range(100)})
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.2, time_ordered=True
    )

    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20

    # Check order
    assert train["val"].iloc[0] == 0
    assert train["val"].iloc[-1] == 59
    assert val["val"].iloc[0] == 60
    assert val["val"].iloc[-1] == 79
    assert test["val"].iloc[0] == 80
    assert test["val"].iloc[-1] == 99
