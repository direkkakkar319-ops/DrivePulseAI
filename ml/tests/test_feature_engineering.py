import pandas as pd

from src.data.feature_engineering import FeatureEngineering
from src.data.preprocessing import PreProcessing


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ag_000": [1.0, None, 3.0, 4.0],
            "ag_001": [2.0, 2.0, None, 4.0],
            "aa_000": [5.0, 6.0, 7.0, 8.0],
            "failure": [0, 1, 0, 1],
            "vehicle_id": ["a", "b", "c", "d"],
            "source": ["scania_aps"] * 4,
        }
    )


def test_add_aps_features_missing_count():
    out = FeatureEngineering.add_aps_features(_sample())
    assert out["n_missing"].tolist() == [0, 1, 1, 0]


def test_add_aps_features_group_aggs():
    out = FeatureEngineering.add_aps_features(_sample())
    assert out["ag_sum"].tolist() == [3.0, 2.0, 3.0, 8.0]
    assert out["ag_mean"].tolist() == [1.5, 2.0, 3.0, 4.0]
    assert out["ag_max"].tolist() == [2.0, 2.0, 3.0, 4.0]
    assert "aa_000_sum" not in out.columns  # singleton prefix: no aggs


def test_add_aps_features_all_nan_group_stays_nan():
    df = _sample()
    df.loc[0, ["ag_000", "ag_001"]] = None
    out = FeatureEngineering.add_aps_features(df)
    assert pd.isna(out.loc[0, "ag_sum"])
    cleaned = PreProcessing.clean(out)
    assert not cleaned[["ag_sum", "ag_mean", "ag_max"]].isna().any().any()


def test_add_aps_features_no_input_mutation():
    df = _sample()
    before = df.copy(deep=True)
    FeatureEngineering.add_aps_features(df)
    pd.testing.assert_frame_equal(df, before)


def test_aps_model_columns():
    out = FeatureEngineering.add_aps_features(_sample())
    cols = FeatureEngineering.aps_model_columns(out)
    assert "failure" not in cols and "vehicle_id" not in cols
    assert "n_missing" in cols and "ag_sum" in cols
