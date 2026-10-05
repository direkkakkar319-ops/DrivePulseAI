"""Integrity contracts for the standalone APS analysis."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "notebooks/eda_scania_aps_uda.py"
SPEC = importlib.util.spec_from_file_location("aps_uda", SCRIPT)
aps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aps)


def test_loader_preserves_missing_predictors_and_rejects_missing_target(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("Copyright preamble\n\nclass,aa_000\nneg,na\npos,2\n")
    result = aps.load(source)
    assert result.shape == (2, 2)
    assert pd.isna(result.loc[0, "aa_000"])
    source.write_text("class,aa_000\nna,2\n")
    with pytest.raises(ValueError, match="target"):
        aps.load(source)


def test_predictor_overlap_ignores_labels_and_row_indices():
    frame = pd.DataFrame(
        {"class": ["neg", "pos"], "a": [1.0, 1.0], "b": [np.nan, np.nan]}, index=[4, 20]
    )
    hashes = aps.fingerprints(frame)
    assert hashes.iloc[0] == hashes.iloc[1]
    nearby = pd.DataFrame({"class": ["neg", "pos"], "a": [1234.0, 1234.1]})
    assert aps.fingerprints(nearby).nunique() == 2
    assert aps.fingerprints(nearby, rounded=True).nunique() == 1


def test_challenge_cost_penalizes_missed_failures():
    result = aps.metrics(pd.Series([0, 0, 1, 1]), np.array([0.9, 0.1, 0.1, 0.9]), 0.5)
    assert result["fp"] == result["fn"] == 1
    assert result["challenge_cost"] == 510
    assert result["precision"] == result["recall"] == 0.5
