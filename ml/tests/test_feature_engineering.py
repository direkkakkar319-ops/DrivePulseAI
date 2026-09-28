import pandas as pd

from src.data.feature_engineering import AI4I_LEAKAGE_COLS, FeatureEngineering


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Rotational speed": [1500, 1400],
            "Torque": [40.0, 50.0],
            "Process temperature": [310.0, 312.0],
            "Air temperature": [300.0, 300.0],
            "Tool wear": [100, 210],
            "Type": ["L", "M"],
            "Machine failure": [0, 1],
            "TWF": [0, 1],
            "HDF": [0, 0],
            "PWF": [0, 0],
            "OSF": [0, 0],
            "RNF": [0, 0],
        }
    )


def test_derived_math():
    out = FeatureEngineering.add_ai4i_features(_sample())
    assert out["temp_diff"].tolist() == [10.0, 12.0]
    assert out["power_proxy"].tolist() == [60000.0, 70000.0]
    assert out["wear_critical"].tolist() == [0, 1]


def test_leakage_dropped_by_default():
    out = FeatureEngineering.add_ai4i_features(_sample())
    for col in AI4I_LEAKAGE_COLS:
        assert col not in out.columns
    assert "Machine failure" in out.columns


def test_leakage_kept_when_off():
    out = FeatureEngineering.add_ai4i_features(_sample(), drop_leakage=False)
    assert "TWF" in out.columns


def test_type_one_hot():
    out = FeatureEngineering.add_ai4i_features(_sample())
    assert "Type" not in out.columns
    assert out["type_L"].tolist() == [1, 0]
    assert out["type_M"].tolist() == [0, 1]


def test_input_not_mutated():
    df = _sample()
    before = df.copy(deep=True)
    FeatureEngineering.add_ai4i_features(df)
    pd.testing.assert_frame_equal(df, before)


def test_model_columns_excludes_targets_and_meta():
    df = FeatureEngineering.add_ai4i_features(_sample())
    df["vehicle_id"] = ["A", "B"]
    df["source"] = ["ai4i", "ai4i"]
    cols = FeatureEngineering.ai4i_model_columns(df)
    assert "temp_diff" in cols and "power_proxy" in cols
    assert "Machine failure" not in cols
    assert "vehicle_id" not in cols and "source" not in cols
    for col in AI4I_LEAKAGE_COLS:
        assert col not in cols
