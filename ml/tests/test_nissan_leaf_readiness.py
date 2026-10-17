"""Check readiness helpers and artifacts using small real source excerpts, not full scans."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "notebooks/nissan_leaf_2018/scripts"
sys.path.insert(0, str(SCRIPTS))
from acquire import BASE, DATA, ROOT, sha256
from readiness import (
    SELECTED,
    check_schema,
    derived_checks,
    inventory,
    missing_accounting,
    temporal_checks,
)


@pytest.fixture
def excerpt() -> pd.DataFrame:
    """Read only the first 16 genuine processed records."""
    source = DATA / "processed/Dataset_Preprocessed.csv"
    if not source.exists():
        pytest.skip("Official source CSV is Git-ignored; run this check after acquisition")
    return pd.read_csv(source, nrows=16)


def test_inventory_completeness() -> None:
    actual = inventory()
    saved = pd.read_csv(
        BASE / "tables/readiness/feature_inventory.csv", keep_default_na=False
    )
    assert len(actual) == len(saved) == 124
    assert not actual.duplicated(["source_dataset", "column"]).any()
    for version in ("raw", "processed"):
        overview = json.loads((BASE / f"tables/{version}/overview.json").read_text())
        subset = actual[actual.source_dataset.eq(version)]
        assert subset.column.tolist() == overview["pandas_columns"]
        assert subset.missing_pct.between(0, 100).all()
        assert subset.possible_target_leakage.str.len().gt(0).all()
        assert (
            subset[subset.column.eq("Trip")]
            .potential_input.eq("excluded_from_initial_input_pool")
            .all()
        )
        assert subset.potential_target.ne("not_proposed").sum() == 10
    for frame in (actual, saved):
        frame["most_common_fraction_nonmissing"] = pd.to_numeric(
            frame.most_common_fraction_nonmissing, errors="coerce"
        )
    pd.testing.assert_frame_equal(actual, saved, check_dtype=False)


def test_expected_schema(excerpt: pd.DataFrame) -> None:
    expected = json.loads((BASE / "tables/processed/overview.json").read_text())[
        "pandas_columns"
    ]
    check_schema(excerpt.columns.tolist(), expected)
    with pytest.raises(ValueError, match="Schema"):
        check_schema(excerpt.columns.tolist()[:-1], expected)
    with pytest.raises(ValueError, match="Schema"):
        check_schema(expected + [expected[0]], expected)


def test_timestamp_ordering(excerpt: pd.DataFrame) -> None:
    result = temporal_checks(excerpt)
    assert result["global_reversals"] == 0
    assert result["timestamp_parse_failures"] == 0
    # Reorder existing real observations to exercise rejection diagnostics.
    reversed_rows = excerpt.iloc[::-1]
    assert temporal_checks(reversed_rows)["global_reversals"] == len(excerpt) - 1


def test_trip_boundaries() -> None:
    # Existing EDA contains actual trip-start timestamps; no generated telemetry.
    sessions = pd.read_csv(BASE / "tables/processed/sessions.csv", nrows=3)
    frame = sessions[["trip", "earliest_us"]].rename(
        columns={"trip": "Trip", "earliest_us": "Timestamp"}
    )
    result = temporal_checks(frame)
    assert result["trip_blocks"] == 3
    assert result["within_trip_gaps_gt_1s"] == 0
    assert result["reused_noncontiguous_trip_ids"] == 0
    repeated = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
    assert temporal_checks(repeated)["reused_noncontiguous_trip_ids"] == 1


def test_missing_accounting(excerpt: pd.DataFrame) -> None:
    assert missing_accounting(excerpt)["missing"].sum() == 0
    raw = pd.read_csv(
        DATA / "raw/Dataset_NissanLeaf-2021_2022.csv",
        nrows=16,
        usecols=["SWA", "Pack_3_C_Temp", "Timestamp"],
    )
    counts = missing_accounting(raw)
    assert counts.loc["SWA", "missing"] == 16
    assert counts.loc["Pack_3_C_Temp", "missing_pct"] == 100
    assert counts.loc["Timestamp", "missing"] == 0


def test_derived_consistency(excerpt: pd.DataFrame) -> None:
    assert all(row["mismatches"] == 0 for row in derived_checks(excerpt))
    raw = pd.read_csv(
        DATA / "raw/Dataset_NissanLeaf-2021_2022.csv", nrows=16, usecols=SELECTED
    )
    assert all(row["mismatches"] == 0 for row in derived_checks(raw))
    # Compare mismatched existing rows, without manufacturing sensor values.
    misaligned = excerpt.copy()
    misaligned["Horsepower"] = misaligned.Horsepower.iloc[::-1].to_numpy()
    results = {row["relationship"]: row for row in derived_checks(misaligned)}
    assert results["Horsepower_from_Instant_kW"]["mismatches"] > 0


def test_report_output_consistency() -> None:
    metrics = json.loads((BASE / "tables/readiness/readiness_metrics.json").read_text())
    report = (BASE / "ML_READINESS_REPORT.md").read_text()
    manifest = json.loads((BASE / "readiness_manifest.json").read_text())
    assert all(f"## {number}." in report for number in range(1, 16))
    for version in ("raw", "processed"):
        assert str(metrics[version]["rows"]) in report
        trip = pd.read_csv(BASE / f"tables/readiness/{version}_trip_soh.csv")
        assert trip.rows.sum() == metrics[version]["rows"]
        assert len(trip) == metrics[version]["trip_ids"]
        values = pd.read_csv(BASE / f"tables/readiness/{version}_soh_values.csv")
        assert values.rows.sum() == metrics[version]["rows"]
        existing = pd.read_csv(
            BASE / f"tables/{version}/derived_relationship_checks.csv"
        )
        for check in metrics[version]["derived_checks"]:
            old = existing[existing.relationship.eq(check["relationship"])].iloc[0]
            assert check["mismatches"] == (
                old["compared_rows"] - old["rows_close_atol_1e-8_rtol_1e-8"]
            )

    for relative, expected_hash in manifest["outputs"].items():
        assert sha256(ROOT / relative) == expected_hash, relative
    for relative, expected_hash in manifest["scripts"].items():
        assert sha256(ROOT / relative) == expected_hash, relative
