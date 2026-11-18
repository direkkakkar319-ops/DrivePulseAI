"""Real packaged telemetry, strict rejection, pairing parity and optional inference."""

import csv
import gzip
import hashlib
import io
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from app.services.kit_samples import (
    FEATURE_NAMES,
    MANIFEST_PATH,
    TARGET_NAMES,
    SampleDataError,
    load_sample,
    make_window_pairs,
)

SAMPLE_ID = "kit-20180320-normal"
EXPECTED = Path(__file__).parent / "fixtures/kit_known_request.json"


@pytest.fixture
def package(tmp_path):
    destination = tmp_path / "kit"
    shutil.copytree(MANIFEST_PATH.parent, destination)
    return destination / "manifest.json"


def change_manifest(path, update):
    catalog = json.loads(path.read_text())
    update(catalog["samples"][0])
    path.write_text(json.dumps(catalog))


def change_asset(path, update):
    catalog = json.loads(path.read_text())
    entry = catalog["samples"][0]
    asset = path.parent / entry["asset_file"]
    with gzip.open(asset, "rt", newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        rows = list(reader)
    update(rows)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    compressed = gzip.compress(output.getvalue().encode(), mtime=0)
    asset.write_bytes(compressed)
    entry["asset_sha256"] = hashlib.sha256(compressed).hexdigest()
    path.write_text(json.dumps(catalog))


def test_real_sample_counts_metadata_finite_values_and_known_request():
    sample = load_sample(SAMPLE_ID)
    assert len(sample.windows) == 163
    assert len(sample.pairs) == 162
    assert sample.manifest["license"] == "CC-BY-4.0"
    assert sample.manifest["creator"] == "Marc Weber"
    assert sample.manifest["source_doi"] == "10.35097/1130"
    assert sample.manifest["compatible_model_version"] == "kit-xgb-forecast-v1"
    assert sample.manifest["asset_sha256"] == (
        "3f24c1fcfd54538cf1b081515085045751c9ebe025e731fb17598cdbfc3795d9"
    )
    for window in sample.windows:
        assert window.recording_id == "KIT-2018-03-20_Seat_Leon_KA_KA_Normal"
        assert window.recording_date == "2018-03-20"
        assert window.split == "test" and window.segment_id == 0
        assert tuple(window.features) == FEATURE_NAMES
        # JSON's strict encoder rejects non-finite inference values.
        json.dumps(window.features, allow_nan=False)
    for pair in sample.pairs:
        assert pair.following.start_seconds - pair.current.start_seconds == 10
        assert tuple(pair.inference_request()["next_window_medians"]) == TARGET_NAMES
    first = sample.pairs[0]
    assert (first.current.start_seconds, first.following.start_seconds) == (
        30480,
        30490,
    )
    assert first.inference_request() == json.loads(EXPECTED.read_text())


def test_sample_loads_without_repository_root_or_working_directory(
    package, monkeypatch
):
    monkeypatch.chdir(package.parent)
    assert len(load_sample(SAMPLE_ID).pairs) == 162
    assert len(load_sample(SAMPLE_ID, manifest_path=package).pairs) == 162


def test_asset_is_exact_original_rows_with_reproducible_gzip():
    root = Path(__file__).resolve().parents[2]
    source = root / "data/automotive_obd/kit_obd/processed/windows_10s.csv.gz"
    if not source.is_file():
        pytest.skip(
            "Full research dataset is not required in a backend-only deployment"
        )
    sample = load_sample(SAMPLE_ID)
    with gzip.open(source, "rt", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        original = [
            r for r in reader if r["recording_id"] == sample.manifest["recording_id"]
        ]
    asset = MANIFEST_PATH.parent / sample.manifest["asset_file"]
    with gzip.open(asset, "rt", newline="") as stream:
        assert list(csv.DictReader(stream)) == original
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(original)
    compressed = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9
    ) as stream:
        stream.write(output.getvalue().encode())
    assert compressed.getvalue() == asset.read_bytes()
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == (sample.manifest["provenance"]["prepared_source_sha256"])
    )


@pytest.mark.parametrize("content", ["invalid json", '{"schema_version": 2}', "{}"])
def test_corrupt_or_unsupported_manifest(package, content):
    package.write_text(content)
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=package)


def test_duplicate_manifest_ids_rejected(package):
    catalog = json.loads(package.read_text())
    catalog["samples"].append(catalog["samples"][0])
    package.write_text(json.dumps(catalog))
    with pytest.raises(SampleDataError, match="Duplicate"):
        load_sample(SAMPLE_ID, manifest_path=package)


@pytest.mark.parametrize("sample_id", ["unknown", "../kit-20180320-normal.csv.gz"])
def test_only_manifest_ids_are_accepted(sample_id):
    with pytest.raises(SampleDataError, match="Unknown"):
        load_sample(sample_id)


def test_missing_manifest(tmp_path):
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=tmp_path / "missing.json")


def test_missing_asset(package):
    (package.parent / "kit-20180320-normal.csv.gz").unlink()
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=package)


def test_checksum_mismatch(package):
    with (package.parent / "kit-20180320-normal.csv.gz").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(SampleDataError, match="checksum"):
        load_sample(SAMPLE_ID, manifest_path=package)


def test_invalid_gzip_even_with_matching_checksum(package):
    compressed = b"not gzip"
    (package.parent / "kit-20180320-normal.csv.gz").write_bytes(compressed)
    change_manifest(
        package,
        lambda entry: entry.update(asset_sha256=hashlib.sha256(compressed).hexdigest()),
    )
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=package)


@pytest.mark.parametrize(
    "key,value",
    [
        ("window_seconds", 5),
        ("window_count", 164),
        ("valid_pair_count", 161),
        ("source_split", "train"),
        ("recording_id", "different"),
        ("segment_ids", [1]),
        ("asset_file", "../outside.csv.gz"),
        ("feature_names", []),
        ("target_names", []),
    ],
)
def test_incompatible_manifest_is_rejected(package, key, value):
    change_manifest(package, lambda entry: entry.update({key: value}))
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=package)


@pytest.mark.parametrize("value", ["", "NaN", "inf", "-inf", "missing"])
def test_missing_or_nonfinite_features_rejected(package, value):
    change_asset(package, lambda rows: rows[0].update({FEATURE_NAMES[0]: value}))
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=package)


def test_missing_feature_column_is_rejected(package):
    asset = package.parent / "kit-20180320-normal.csv.gz"
    data = (
        gzip.decompress(asset.read_bytes())
        .decode()
        .replace("coolant_temp_c__median", "unexpected_feature", 1)
    )
    compressed = gzip.compress(data.encode(), mtime=0)
    asset.write_bytes(compressed)
    change_manifest(
        package,
        lambda entry: entry.update(asset_sha256=hashlib.sha256(compressed).hexdigest()),
    )
    with pytest.raises(SampleDataError, match="columns"):
        load_sample(SAMPLE_ID, manifest_path=package)


def test_duplicate_timestamps_rejected(package):
    change_asset(
        package,
        lambda rows: rows[1].update(
            window_start_seconds=rows[0]["window_start_seconds"]
        ),
    )
    with pytest.raises(SampleDataError):
        load_sample(SAMPLE_ID, manifest_path=package)


def test_pairs_never_cross_recordings_segments_splits_or_gaps():
    a, b = load_sample(SAMPLE_ID).windows[:2]
    for changed in (
        replace(b, recording_id="another"),
        replace(b, segment_id=1),
        replace(b, split="train"),
        replace(b, start_seconds=a.start_seconds + 20),
    ):
        assert make_window_pairs((a, changed)) == ()
    assert len(make_window_pairs((a, b))) == 1


def test_known_score_with_existing_optional_model(monkeypatch):
    joblib = pytest.importorskip("joblib")
    pd = pytest.importorskip("pandas")
    pytest.importorskip("xgboost")
    pytest.importorskip("sklearn")
    root = Path(__file__).resolve().parents[2]
    artifact = root / "ml/hf_deployment/model_repository/kit_xgb_forecast.joblib"
    if not artifact.is_file():
        pytest.skip("Optional research artifact is not part of the backend package")
    monkeypatch.syspath_prepend(str(root))
    from ml.scripts.train_kit_xgb_forecast import make_next_window_pairs

    sample = load_sample(SAMPLE_ID)
    asset = MANIFEST_PATH.parent / sample.manifest["asset_file"]
    features_from_training, targets_from_training, _ = make_next_window_pairs(
        # Preserve source decimal precision; this compares the pairing function,
        # not pandas' default CSV float-parser rounding.
        pd.read_csv(asset, float_precision="round_trip")
    )
    assert len(features_from_training) == len(sample.pairs)
    for index, pair in enumerate(sample.pairs):
        request = pair.inference_request()
        assert (
            request["current_window_features"]
            == features_from_training.iloc[index].to_dict()
        )
        assert (
            request["next_window_medians"]
            == targets_from_training.iloc[index].to_dict()
        )
    model = joblib.load(artifact)
    request = sample.pairs[0].inference_request()
    assert list(request["current_window_features"]) == model.feature_names
    assert list(request["next_window_medians"]) == model.target_names
    features = pd.DataFrame([request["current_window_features"]])
    targets = pd.DataFrame([request["next_window_medians"]])
    result = model.predict(features, targets).iloc[0]
    assert result["anomaly_score"] == pytest.approx(3.435043761, abs=1e-6)
    assert model.threshold == pytest.approx(8.083880990992366)
    assert not result["is_novel"]
