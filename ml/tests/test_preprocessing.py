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
    assert len(val) == 15
    assert len(test) == 15


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


def test_clean_per_vehicle_bfill_no_cross_vehicle_leakage():
    # Vehicle A has all-NaNs and leading-NaNs; vehicle B has valid readings.
    # Vehicle A must NOT receive values backward-filled from Vehicle B.
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A", "B", "B"],
            "timestamp": [1, 2, 1, 2],
            "speed": [np.nan, np.nan, 50.0, 60.0],
            "rpm": [np.nan, 800.0, 1500.0, 1600.0],
        }
    )
    cleaned = PreProcessing.clean(
        df, drop_duplicates=False, fill_dropouts=True, fill_remaining_numeric=None
    )

    # Vehicle A speed had only NaNs, so within vehicle A it remains NaN
    veh_a = cleaned[cleaned["vehicle_id"] == "A"].sort_values("timestamp")
    assert veh_a["speed"].isna().all()
    # Vehicle A rpm: row 0 leading NaN should be backward-filled from row 1 (800.0), NOT from B
    assert (veh_a["rpm"] == 800.0).all()

    # Vehicle B should preserve its values
    veh_b = cleaned[cleaned["vehicle_id"] == "B"].sort_values("timestamp")
    assert list(veh_b["speed"]) == [50.0, 60.0]
    assert list(veh_b["rpm"]) == [1500.0, 1600.0]


def test_clean_incomplete_imputer_stats_no_eval_refit():
    # When imputer_stats is supplied for val/test, columns missing from imputer_stats
    # must NOT silently refit median/mean from the val/test frame.
    df_eval = pd.DataFrame(
        {
            "speed": [100.0, np.nan],
            "rpm": [5000.0, np.nan],
        }
    )
    # Train stats only provide speed=20.0, rpm was omitted
    train_stats = {"speed": 20.0}

    cleaned_eval = PreProcessing.clean(
        df_eval,
        fill_dropouts=False,
        fill_remaining_numeric="median",
        imputer_stats=train_stats,
    )

    # Speed was present in imputer_stats -> filled with 20.0
    assert cleaned_eval.loc[1, "speed"] == 20.0
    # RPM was omitted -> must remain NaN, NOT filled with 5000.0 from df_eval
    assert pd.isna(cleaned_eval.loc[1, "rpm"])


def test_clean_all_null_numeric_column_preserved_as_nan():
    # If a numeric column has no observed values, median/mean must leave it as NaN
    # rather than inventing arbitrary numbers (e.g. 0.0), and omit from stats.
    df = pd.DataFrame(
        {
            "speed": [10.0, 20.0, np.nan],
            "all_null_sensor": [np.nan, np.nan, np.nan],
        }
    )
    cleaned_median, stats_median = PreProcessing.clean(
        df,
        fill_dropouts=False,
        fill_remaining_numeric="median",
        return_imputer_stats=True,
    )
    assert cleaned_median["all_null_sensor"].isna().all()
    assert "all_null_sensor" not in stats_median
    assert stats_median["speed"] == 15.0

    cleaned_mean, stats_mean = PreProcessing.clean(
        df,
        fill_dropouts=False,
        fill_remaining_numeric="mean",
        return_imputer_stats=True,
    )
    assert cleaned_mean["all_null_sensor"].isna().all()
    assert "all_null_sensor" not in stats_mean
    assert stats_mean["speed"] == 15.0


def test_exclude_cols_additive_across_methods():
    df = pd.DataFrame(
        {
            "vehicle_id": ["A", "A"],
            "timestamp": [1, 2],
            "speed": [10.0, 20.0],
            "failure": [0, 1],
            "rul": [50.0, 40.0],
            "custom_aux": [100.0, 200.0],
        }
    )

    # 1. clean: exclude_cols should add to default exclusions (labels + meta)
    cleaned = PreProcessing.clean(
        df,
        drop_duplicates=False,
        fill_dropouts=False,
        fill_remaining_numeric="median",
        exclude_cols=["custom_aux"],
        return_imputer_stats=True,
    )[0]
    # speed should be in features; custom_aux, failure, rul, vehicle_id, timestamp excluded
    assert "speed" in cleaned.columns

    # 2. scale: custom_aux, failure, rul, vehicle_id must not be scaled
    scaled, _ = PreProcessing.scale(df, exclude_cols=["custom_aux"])
    assert np.isclose(scaled["speed"].iloc[0], -1.0)
    assert scaled["custom_aux"].iloc[0] == 100.0
    assert scaled["failure"].iloc[0] == 0
    assert scaled["rul"].iloc[0] == 50.0

    # 3. make_time_windows: custom_aux, failure, rul must not be windowed
    windows = PreProcessing.make_time_windows(
        df, window_size=2, step=1, exclude_cols=["custom_aux"]
    )
    # Only 1 feature should be windowed: speed
    assert windows.shape == (1, 2, 1)


def test_train_val_test_split_zero_fractions():
    df = pd.DataFrame({"timestamp": range(20), "val": range(20)})

    # time_ordered=True with val_frac=0.0
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.0, test_frac=0.2, time_ordered=True
    )
    assert len(val) == 0
    assert len(train) == 16
    assert len(test) == 4

    # time_ordered=True with test_frac=0.0
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.0, time_ordered=True
    )
    assert len(test) == 0
    assert len(train) == 16
    assert len(val) == 4

    # time_ordered=True with both zero
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.0, test_frac=0.0, time_ordered=True
    )
    assert len(val) == 0
    assert len(test) == 0
    assert len(train) == 20

    # time_ordered=False with val_frac=0.0
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.0, test_frac=0.2, time_ordered=False
    )
    assert len(val) == 0
    assert len(train) == 16
    assert len(test) == 4

    # time_ordered=False with test_frac=0.0
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.2, test_frac=0.0, time_ordered=False
    )
    assert len(test) == 0
    assert len(train) == 16
    assert len(val) == 4

    # time_ordered=False with both zero
    train, val, test = PreProcessing.train_val_test_split(
        df, val_frac=0.0, test_frac=0.0, time_ordered=False
    )
    assert len(val) == 0
    assert len(test) == 0
    assert len(train) == 20
