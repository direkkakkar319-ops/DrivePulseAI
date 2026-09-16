import numpy as np
import pandas as pd
import pytest
from src.data.preprocessing import PreProcessing


def test_clean_drops_duplicates():
    df = pd.DataFrame({"vehicle_id": ["A", "A", "A"], "speed": [10, 10, 20]})
    cleaned = PreProcessing.clean(df, drop_duplicates=True)
    assert len(cleaned) == 2
    assert cleaned.iloc[0]["speed"] == 10
    assert cleaned.iloc[1]["speed"] == 20


def test_clean_fills_dropouts():
    df = pd.DataFrame({"vehicle_id": ["A", "A", "A"], "speed": [10, np.nan, 30]})
    cleaned = PreProcessing.clean(df, drop_duplicates=False, fill_dropouts=True)
    assert cleaned.iloc[1]["speed"] == 10.0


def test_clean_excludes_labels_from_imputation():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A", "A"],
            "speed": [10.0, np.nan, 30.0],
            "failure": [0.0, np.nan, 1.0],
            "rul": [50.0, np.nan, 10.0],
        }
    )
    cleaned = PreProcessing.clean(
        df, fill_dropouts=True, fill_remaining_numeric="median"
    )
    # speed should be imputed
    assert cleaned["speed"].isna().sum() == 0
    # failure and rul should NOT be imputed
    assert pd.isna(cleaned.loc[1, "failure"])
    assert pd.isna(cleaned.loc[1, "rul"])


def test_clean_imputer_stats_fit_and_transform():
    df_train = pd.DataFrame({"speed": [10.0, 20.0, 30.0, np.nan]})
    cleaned_train, stats = PreProcessing.clean(
        df_train,
        fill_dropouts=False,
        fill_remaining_numeric="median",
        return_imputer_stats=True,
    )
    # Median of [10, 20, 30] is 20.0
    assert stats["speed"] == 20.0
    assert cleaned_train.loc[3, "speed"] == 20.0

    # Test set uses train statistics
    df_test = pd.DataFrame({"speed": [100.0, np.nan]})
    cleaned_test = PreProcessing.clean(
        df_test,
        fill_dropouts=False,
        imputer_stats=stats,
    )
    assert cleaned_test.loc[1, "speed"] == 20.0


def test_clean_invalid_strategy_raises():
    df = pd.DataFrame({"speed": [10.0, np.nan]})
    with pytest.raises(ValueError, match="Unsupported fill_remaining_numeric strategy"):
        PreProcessing.clean(df, fill_remaining_numeric="unsupported_mode")


def test_clean_sorts_by_timestamp():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A", "A"],
            "timestamp": [3, 1, 2],
            "speed": [30.0, 10.0, np.nan],
        }
    )
    cleaned = PreProcessing.clean(df, fill_dropouts=True)
    # After sorting: t=1 (10.0), t=2 (nan -> ffill 10.0), t=3 (30.0)
    assert list(cleaned["timestamp"]) == [1, 2, 3]
    assert cleaned.loc[cleaned["timestamp"] == 2, "speed"].values[0] == 10.0


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


def test_scale_excludes_target_labels():
    df = pd.DataFrame(
        {
            "speed": [10.0, 20.0],
            "failure": [0, 1],
            "rul": [100.0, 50.0],
            "timestamp": [1, 2],
            "source": ["simulated", "simulated"],
        }
    )
    scaled, _ = PreProcessing.scale(df)
    # speed is scaled
    assert np.isclose(scaled["speed"].iloc[0], -1.0)
    assert np.isclose(scaled["speed"].iloc[1], 1.0)
    # failure and rul must remain unscaled
    assert list(scaled["failure"]) == [0, 1]
    assert list(scaled["rul"]) == [100.0, 50.0]


def test_scale_custom_feature_cols():
    df = pd.DataFrame({"speed": [10.0, 20.0], "rpm": [1000.0, 2000.0]})
    scaled, _ = PreProcessing.scale(df, feature_cols=["rpm"])
    # rpm scaled, speed unscaled
    assert np.isclose(scaled["rpm"].iloc[0], -1.0)
    assert scaled["speed"].iloc[0] == 10.0


def test_make_time_windows():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A", "A", "B", "B", "B"],
            "speed": [1, 2, 3, 4, 5, 6],
            "source": ["simulated"] * 6,
        }
    )
    windows = PreProcessing.make_time_windows(df, window_size=2, step=1)

    assert windows.shape == (4, 2, 1)
    assert np.array_equal(windows[0, :, 0], [1, 2])
    assert np.array_equal(windows[1, :, 0], [2, 3])
    assert np.array_equal(windows[2, :, 0], [4, 5])
    assert np.array_equal(windows[3, :, 0], [5, 6])


def test_make_time_windows_excludes_labels():
    df = pd.DataFrame(
        {
            "speed": [1.0, 2.0, 3.0],
            "rpm": [10.0, 20.0, 30.0],
            "failure": [0, 0, 1],
            "rul": [30.0, 20.0, 10.0],
            "subset": ["FD001", "FD001", "FD001"],
            "timestamp": [1, 2, 3],
        }
    )
    windows = PreProcessing.make_time_windows(df, window_size=2, step=1)
    # Shape should be (2 windows, size 2, 2 sensor features: speed, rpm)
    assert windows.shape == (2, 2, 2)


def test_make_time_windows_empty_shape():
    df = pd.DataFrame({"speed": [1.0, 2.0]})
    # Sequence length 2 < window_size 5 -> returns empty 3D array of shape (0, 5, 1)
    windows = PreProcessing.make_time_windows(df, window_size=5, step=1)
    assert windows.shape == (0, 5, 1)
    assert windows.ndim == 3


def test_make_time_windows_validation():
    df = pd.DataFrame({"speed": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="window_size must be >= 1"):
        PreProcessing.make_time_windows(df, window_size=0)
    with pytest.raises(ValueError, match="step must be >= 1"):
        PreProcessing.make_time_windows(df, window_size=2, step=0)


def test_make_time_windows_sorts_timestamps():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A", "A"],
            "timestamp": [3, 1, 2],
            "speed": [30.0, 10.0, 20.0],
        }
    )
    windows = PreProcessing.make_time_windows(df, window_size=2, step=1)
    # Window 0 should be [10, 20], window 1 should be [20, 30]
    assert np.array_equal(windows[0, :, 0], [10.0, 20.0])
    assert np.array_equal(windows[1, :, 0], [20.0, 30.0])


def test_train_val_test_split_random():
    df = pd.DataFrame({"val": range(100)})
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.2, time_ordered=False
    )

    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20

    train_vals = set(train["val"])
    val_vals = set(val["val"])
    assert len(train_vals.intersection(val_vals)) == 0


def test_train_val_test_split_time_ordered_default():
    df = pd.DataFrame({"timestamp": range(100), "val": range(100)})
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.2
    )

    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20
    assert train["val"].iloc[0] == 0
    assert train["val"].iloc[-1] == 59
    assert val["val"].iloc[0] == 60
    assert val["val"].iloc[-1] == 79
    assert test["val"].iloc[0] == 80
    assert test["val"].iloc[-1] == 99


def test_train_val_test_split_unsorted_timestamps():
    np.random.seed(42)
    shuffled_indices = np.random.permutation(100)
    df = pd.DataFrame({"timestamp": shuffled_indices, "val": shuffled_indices})

    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.2, time_ordered=True
    )

    assert max(train["timestamp"]) < min(val["timestamp"])
    assert max(val["timestamp"]) < min(test["timestamp"])


def test_train_val_test_split_missing_timestamp_raises():
    df = pd.DataFrame({"val": range(100)})
    with pytest.raises(ValueError, match="requires 'timestamp' column"):
        PreProcessing.train_val_test_split(df, time_ordered=True)

    # Allowed if assume_sorted=True
    train, val, test = PreProcessing.train_val_test_split(
        df, time_ordered=True, assume_sorted=True
    )
    assert len(train) == 70


def test_train_val_test_split_per_vehicle():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A"] * 50 + ["B"] * 50,
            "timestamp": list(range(50)) + list(range(50)),
            "val": list(range(50)) + list(range(50)),
        }
    )
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.2, time_ordered=True, group_by_vehicle=True
    )

    # Each vehicle has 50 rows: 30 train, 10 val, 10 test. Total: 60 train, 20 val, 20 test.
    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20
    assert set(train["vehicle_id"]) == {"A", "B"}
    assert set(test["vehicle_id"]) == {"A", "B"}
