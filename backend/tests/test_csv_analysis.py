"""Strict upload validation, reference parity and genuine raw-to-model verification."""

import asyncio
import csv
import gzip
import importlib
import io
import json
import resource
import secrets
import tarfile
import time
import zipfile
from pathlib import Path

import httpx
import pytest
from test_analysis_api import AUTH, check_complete_result, claims
from test_analysis_api import (
    genuine as genuine,  # noqa: PLC0414 -- Re-export pytest fixture.
)
from test_analysis_api import (
    harness as harness,  # noqa: PLC0414 -- Re-export pytest fixture.
)

from app.api import deps
from app.config import Settings
from app.main import create_app
from app.services.inference_service import KITInferenceService
from app.services.kit_samples import FEATURE_NAMES, load_sample
from app.services.kit_upload import UploadError, prepare_csv

UPLOAD = "/api/v1/analysis/upload"
ROOT = Path(__file__).resolve().parents[2]


def test_upload_limits_from_environment(monkeypatch):
    limits = {
        "KIT_UPLOAD_MAX_BYTES": 1048576,
        "KIT_UPLOAD_MAX_ROWS": 1000,
        "KIT_UPLOAD_MAX_WINDOWS": 64,
        "KIT_UPLOAD_MAX_PAIRS": 63,
        "KIT_UPLOAD_MAX_SEGMENTS": 2,
        "KIT_UPLOAD_MAX_BATCHES": 2,
        "KIT_UPLOAD_MAX_CONCURRENT": 1,
        "KIT_UPLOAD_ANALYSIS_TIMEOUT_SECONDS": 15,
    }
    for key, value in limits.items():
        monkeypatch.setenv(key, str(value))
    settings = Settings(
        _env_file=None, database_url="postgresql://unit:unit@localhost/unused"
    )
    assert all(getattr(settings, key.lower()) == value for key, value in limits.items())


def read_raw(name):
    parts = sorted((ROOT / "data/automotive_obd/kit_obd/raw_chunks").glob("*.part-*"))
    if len(parts) != 3:
        pytest.skip("Publisher KIT archive is unavailable")
    with tarfile.open(
        fileobj=io.BytesIO(b"".join(p.read_bytes() for p in parts))
    ) as archive:
        member = next(
            m for m in archive.getmembers() if m.name.endswith("OBD-II-Dataset.zip")
        )
        with zipfile.ZipFile(io.BytesIO(archive.extractfile(member).read())) as source:
            path = next(n for n in source.namelist() if n.endswith(name))
            return source.read(path)


@pytest.fixture(scope="module")
def raw():
    return read_raw("2018-03-20_Seat_Leon_KA_KA_Normal.csv")


@pytest.fixture(scope="module")
def short(raw):
    # Only the first two complete source buckets, without changing any values.
    lines = raw.decode("utf-8-sig").splitlines(keepends=True)
    return (
        lines[0]
        + "".join(line for line in lines[1:] if line.split(",")[0] < "08:28:20.000")
    ).encode()


def post(
    harness, data, *, filename="trip.csv", mime="text/csv", day="2018-03-20", **kwargs
):
    return harness.client.post(
        UPLOAD,
        headers=AUTH,
        files={"file": (filename, data, mime)},
        data={"recording_date": day},
        **kwargs,
    )


def rewritten(data, change):
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    change(rows)
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    return output.getvalue().encode()


def test_authorized_upload_and_known_pair(harness, short):
    response = post(harness, short)
    assert response.status_code == 200
    result = response.json()
    assert result["source_type"] == "uploaded_csv"
    assert result["source"]["accepted_rows"] > 0
    assert result["window_count"] == 2 and result["pair_count"] == 1
    assert result["source"]["input_bytes"] == len(short)
    assert result["source"]["metadata_verification"] == "caller_supplied_unverified"
    assert result["predictions"][0]["next_window"]["split"] == "uploaded"
    assert "sample" not in result and result["persisted"] is False
    assert harness.key not in response.text
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/kit_known_request.json").read_text()
    )
    sent = harness.requests[0]["pairs"][0]
    assert sent["current_window_features"] == pytest.approx(
        fixture["current_window_features"], rel=1e-12, abs=1e-12
    )
    assert sent["next_window_medians"] == pytest.approx(
        fixture["next_window_medians"], rel=1e-12, abs=1e-12
    )
    assert result["predictions"][0]["anomaly_score"] == pytest.approx(
        3.435043761, abs=1e-6
    )


@pytest.mark.parametrize(
    "headers,status", [({}, 401), ({"Authorization": "Bearer invalid"}, 401)]
)
def test_upload_auth_before_body(harness, short, headers, status):
    response = harness.client.post(
        UPLOAD,
        headers=headers,
        files={"file": ("trip.csv", short, "text/csv")},
        data={"recording_date": "2018-03-20"},
    )
    assert response.status_code == status and harness.requests == []


def test_unauthorized_body_is_not_consumed(harness, short, monkeypatch):
    from starlette.requests import Request

    async def forbidden(_self):
        pytest.fail("Unauthenticated multipart body was consumed")
        yield b""  # pragma: no cover

    monkeypatch.setattr(Request, "stream", forbidden)
    assert (
        harness.client.post(
            UPLOAD, files={"file": ("trip.csv", short, "text/csv")}
        ).status_code
        == 401
    )


def test_unverified_upload(harness, short, monkeypatch):
    monkeypatch.setattr(
        deps,
        "verify_token",
        lambda *_: {"uid": "u", "email": "u@example.test", "email_verified": False},
    )
    assert post(harness, short).status_code == 403
    assert harness.requests == []


@pytest.mark.parametrize(
    "mode,status",
    [
        ("empty", 422),
        ("type", 415),
        ("mime", 415),
        ("encoding", 415),
        ("json", 422),
        ("malformed", 422),
        ("columns", 422),
        ("units", 422),
        ("numeric", 422),
        ("nan", 422),
        ("inf", 422),
        ("timestamp", 422),
        ("long-field", 422),
        ("long-line", 413),
        ("nul", 422),
        ("multiline", 422),
        ("one-window", 422),
        ("no-rows", 422),
    ],
)
def test_invalid_csv(harness, short, mode, status):
    data = short
    filename = "trip.csv"
    mime = "text/csv"
    if mode == "empty":
        data = b""
    elif mode == "type":
        filename = "trip.exe"
    elif mode == "mime":
        mime = "application/json"
    elif mode == "encoding":
        data = short.decode().encode("utf-16")
    elif mode == "json":
        data = b'{"not":"csv"}'
    elif mode == "malformed":
        data = b'"unterminated'
    elif mode == "columns":
        data = rewritten(short, lambda r: r[0].pop())
    elif mode == "units":
        data = short.replace(b"[km/h]", b"[mph]")
    elif mode in {"numeric", "nan", "inf"}:
        data = rewritten(
            short,
            lambda r: r[1].__setitem__(
                1, {"numeric": "=1+1", "nan": "NaN", "inf": "Infinity"}[mode]
            ),
        )
    elif mode == "timestamp":
        data = rewritten(short, lambda r: r[1].__setitem__(0, "24:00:00.000"))
    elif mode == "long-field":
        data = rewritten(short, lambda r: r[1].__setitem__(1, "1" * 129))
    elif mode == "long-line":
        data = b"x" * 2049
    elif mode == "nul":
        data = short.replace(b"Time", b"Ti\x00me", 1)
    elif mode == "multiline":
        data = rewritten(short, lambda r: r[1].__setitem__(1, "1\n2"))
    elif mode == "one-window":
        data = b"\n".join(short.splitlines()[:3])
    elif mode == "no-rows":
        data = short.splitlines()[0]
    response = post(harness, data, filename=filename, mime=mime)
    assert response.status_code == status, response.text
    assert harness.requests == []


@pytest.mark.parametrize(
    "mode",
    [
        "missing-file",
        "missing-date",
        "invalid-date",
        "extra-field",
        "multiple-files",
        "truncated",
        "headers",
    ],
)
def test_invalid_multipart(harness, short, mode):
    files = [("file", ("trip.csv", short, "text/csv"))]
    data = {"recording_date": "2018-03-20"}
    if mode == "missing-file":
        files = []
    elif mode == "missing-date":
        data = {}
    elif mode == "invalid-date":
        data["recording_date"] = "not-a-date"
    elif mode == "extra-field":
        data["ml_api_key"] = "client-must-not-send-this"
    elif mode == "multiple-files":
        files.append(("file", ("other.csv", short, "text/csv")))
    if mode in {"truncated", "headers"}:
        body = (
            b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="trip.csv"\r\nContent-Type: text/csv\r\n\r\n'
            + short
        )
        if mode == "headers":
            body = b"--boundary\r\nX-Header: " + b"a" * 3000 + b"\r\n\r\n"
        response = harness.client.post(
            UPLOAD,
            headers={**AUTH, "Content-Type": "multipart/form-data; boundary=boundary"},
            content=body,
        )
    elif mode == "missing-file":
        response = harness.client.post(
            UPLOAD, headers=AUTH, files={"recording_date": (None, "2018-03-20")}
        )
    else:
        response = harness.client.post(UPLOAD, headers=AUTH, files=files, data=data)
    assert response.status_code == 422
    assert harness.requests == []


@pytest.mark.parametrize(
    "limit,value",
    [
        ("kit_upload_max_bytes", 1024),
        ("kit_upload_max_rows", 2),
        ("kit_upload_max_windows", 2),
        ("kit_upload_max_pairs", 1),
    ],
)
def test_resource_limits(harness, raw, limit, value):
    settings = harness.client.app.state.settings
    setattr(settings, limit, value)
    response = post(harness, raw)
    assert response.status_code == 413
    assert harness.requests == []


def test_streaming_limit_without_content_length(harness, short):
    harness.client.app.state.settings.kit_upload_max_bytes = 1024
    request = httpx.Request(
        "POST",
        "https://test/upload",
        files={"file": ("trip.csv", short, "text/csv")},
        data={"recording_date": "2018-03-20"},
    )
    content = b"".join(request.stream)
    response = harness.client.post(
        UPLOAD,
        headers={**AUTH, "Content-Type": request.headers["Content-Type"]},
        content=iter([content[i : i + 256] for i in range(0, len(content), 256)]),
    )
    assert response.status_code == 413 and harness.requests == []


def test_inference_batch_budget_checked_before_requests(harness, raw):
    harness.client.app.state.settings.kit_ml_batch_size = 1
    assert post(harness, raw).status_code == 413
    assert harness.requests == []


def test_upload_capacity_limit(harness, short):
    harness.client.app.state.kit_upload_slots = asyncio.Semaphore(0)
    assert post(harness, short).status_code == 429
    assert harness.requests == []


def test_memory_cleanup_and_filename_never_used_as_path(harness, short, monkeypatch):
    import tempfile

    from app.services.kit_upload import _MultipartUpload

    clears = []
    original = _MultipartUpload.clear

    def clear(self):
        original(self)
        assert not self.data
        clears.append(True)

    monkeypatch.setattr(_MultipartUpload, "clear", clear)
    monkeypatch.setattr(
        tempfile,
        "SpooledTemporaryFile",
        lambda *_args, **_kwargs: pytest.fail("Disk spooling must not occur"),
    )
    assert post(harness, short, filename="../../private/trip.csv").status_code == 200
    assert post(harness, b"bad", filename="trip.csv").status_code == 422
    assert len(clears) == 2


def test_utf8_bom_and_verified_mojibake_alias(harness, short):
    alias = b"\xef\xbb\xbf" + short.decode().replace("°C", "Â°C").encode()
    response = post(harness, alias, mime="application/octet-stream")
    assert response.status_code == 200


def test_full_raw_preparation_matches_existing_reference(raw, harness):
    prepared = prepare_csv(
        raw, "2018-03-20", harness.client.app.state.settings, time.monotonic() + 60
    )
    original = load_sample("kit-20180320-normal")
    assert prepared.accepted_rows == 19070
    assert len(prepared.windows) == 163 and len(prepared.pairs) == 162
    for a, b in zip(prepared.windows, original.windows, strict=True):
        assert tuple(a.features) == FEATURE_NAMES
        assert a.start_seconds == b.start_seconds and a.segment_id == b.segment_id
        assert a.features == pytest.approx(b.features, rel=1e-12, abs=1e-12)
    for a, b in zip(prepared.pairs, original.pairs, strict=True):
        for field in ("current_window_features", "next_window_medians"):
            assert a.inference_request()[field] == pytest.approx(
                b.inference_request()[field], rel=1e-12, abs=1e-12
            )


def test_offline_recipe_and_upload_share_exact_kernel(raw, harness, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "kit_offline_recipe", ROOT / "ml/scripts/preprocess_kit_obd.py"
    )
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    file = tmp_path / "2018-03-20_Seat_Leon_KA_KA_Normal.csv"
    file.write_bytes(raw)
    expected, _ = recipe.process_file(file, "test")
    prepared = prepare_csv(
        raw, "2018-03-20", harness.client.app.state.settings, time.monotonic() + 60
    )
    for a, b in zip(prepared.windows, expected, strict=True):
        assert a.features == {name: b[name] for name in FEATURE_NAMES}


def test_real_backward_jump_recording_matches_frozen_windows(harness):
    name = "2017-07-11_Seat_Leon_KA_S_Normal.csv"
    data = read_raw(name)
    settings = harness.client.app.state.settings
    settings.kit_upload_max_bytes = 16 * 1024 * 1024
    settings.kit_upload_max_rows = 200000
    settings.kit_upload_max_windows = 1024
    settings.kit_upload_max_pairs = 1024
    settings.kit_upload_max_batches = 32
    prepared = prepare_csv(data, "2017-07-11", settings, time.monotonic() + 60)
    source = ROOT / "data/automotive_obd/kit_obd/processed/windows_10s.csv.gz"
    with gzip.open(source, "rt") as stream:
        expected = [
            r
            for r in csv.DictReader(stream)
            if r["recording_id"] == "KIT-" + name.removesuffix(".csv")
        ]
    assert prepared.backward_jumps == 1
    assert {w.segment_id for w in prepared.windows} == {0, 1}
    for window, row in zip(prepared.windows, expected, strict=True):
        assert window.segment_id == int(row["segment_id"])
        assert window.start_seconds == int(row["window_start_seconds"])
        assert window.features == pytest.approx(
            {n: float(row[n]) for n in FEATURE_NAMES}, rel=1e-12, abs=1e-12
        )
    assert all(p.current.segment_id == p.following.segment_id for p in prepared.pairs)


def test_duplicate_timestamps_preserved_and_backward_jumps_segmented(short, harness):
    def change(rows):
        # Policy fixture uses genuine sensor cells; only clock metadata is varied.
        rows.insert(2, rows[1].copy())
        rows.extend(copy_row.copy() for copy_row in rows[1:])

    duplicate = rewritten(short, change)
    prepared = prepare_csv(
        duplicate,
        "2018-03-20",
        harness.client.app.state.settings,
        time.monotonic() + 60,
    )
    assert prepared.duplicate_timestamps >= 2 and prepared.backward_jumps == 1
    assert {w.segment_id for w in prepared.windows} == {0, 1}
    assert all(p.current.segment_id == p.following.segment_id for p in prepared.pairs)
    assert all(
        p.following.start_seconds - p.current.start_seconds == 10
        for p in prepared.pairs
    )
    harness.client.app.state.settings.kit_upload_max_segments = 1
    assert post(harness, duplicate).status_code == 413


def test_missing_signal_window_dropped_and_gap_never_bridged(raw, harness):
    data = rewritten(
        raw,
        lambda rows: [
            r.__setitem__(1, "")
            for r in rows[1:]
            if "08:28:10.000" <= r[0] < "08:28:20.000"
        ],
    )
    prepared = prepare_csv(
        data, "2018-03-20", harness.client.app.state.settings, time.monotonic() + 60
    )
    assert prepared.discarded_windows == 1
    assert not any(p.current.start_seconds == 30480 for p in prepared.pairs)


@pytest.mark.parametrize(
    "mode,status",
    [
        ("auth", 503),
        ("unavailable", 503),
        ("timeout", 504),
        ("invalid", 502),
        ("later", 503),
    ],
)
def test_upload_upstream_failures(harness, raw, genuine, mode, status):
    def handler(request, payload, count):
        if mode == "later" and count == 1:
            return httpx.Response(
                200,
                json={
                    **genuine["response"],
                    "results": genuine["response"]["results"][:32],
                },
            )
        if mode == "auth":
            return httpx.Response(401, text=harness.key)
        if mode == "timeout":
            raise httpx.ReadTimeout("private data", request=request)
        if mode == "invalid":
            return httpx.Response(200, json={"invalid": True})
        return httpx.Response(503, text="private data")

    harness.plan["handler"] = handler
    response = post(harness, raw)
    assert response.status_code == status
    assert set(response.json()) == {"detail"} and harness.key not in response.text
    assert len(harness.requests) == (2 if mode == "later" else 1)
    assert harness.client.app.state.kit_upload_slots._value == 2


def test_preparation_deadline(short, harness):
    with pytest.raises(UploadError) as error:
        prepare_csv(
            short, "2018-03-20", harness.client.app.state.settings, time.monotonic() - 1
        )
    assert error.value.status_code == 504


def test_whole_upload_deadline_cancels_slow_body(harness):
    harness.client.app.state.settings.kit_upload_analysis_timeout_seconds = 0.01

    # Real-time read cancellation is tested via direct ASGI receive.
    async def exercise():
        app = harness.client.app

        async def content():
            await asyncio.sleep(0.1)
            yield b"incomplete"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client:
            return await client.post(
                UPLOAD,
                headers={**AUTH, "Content-Type": "multipart/form-data; boundary=test"},
                content=content(),
            )

    result = asyncio.run(exercise())
    assert result.status_code == 504


@pytest.mark.asyncio
async def test_genuine_full_csv_both_apps(raw, genuine, monkeypatch):
    for package in ("joblib", "numpy", "pandas", "sklearn", "xgboost"):
        pytest.importorskip(package)
    monkeypatch.syspath_prepend(str(ROOT))
    serving = importlib.import_module("ml.hf_deployment.app")
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("ML_INFERENCE_API_KEY", key)
    monkeypatch.setenv("KIT_MAX_BATCH_SIZE", "32")
    monkeypatch.setattr(deps, "verify_token", claims)
    settings = Settings(
        _env_file=None,
        database_url="postgresql://unit:unit@localhost/unused",
        ml_service_url="https://local-ml.test",
        ml_inference_api_key=key,
    )
    main = create_app(settings)
    batches = []
    transport = httpx.ASGITransport(app=serving.app)

    async def forward(request):
        batches.append(len(json.loads(request.content)["pairs"]))
        return await transport.handle_async_request(request)

    async with (
        serving.lifespan(serving.app),
        main.router.lifespan_context(main),
        httpx.AsyncClient(transport=httpx.MockTransport(forward)) as upstream,
    ):
        main.state.kit_inference = KITInferenceService(settings, upstream)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main), base_url="https://main.test"
        ) as client:
            start = time.perf_counter()
            response = await client.post(
                UPLOAD,
                headers=AUTH,
                files={"file": ("trip.csv", raw, "text/csv")},
                data={"recording_date": "2018-03-20"},
            )
            elapsed = (time.perf_counter() - start) * 1000
    assert response.status_code == 200, response.text
    data = response.json()
    check_complete_result(data, genuine)
    assert batches == [32, 32, 32, 32, 32, 2]
    assert (
        data["source"]["accepted_rows"] == 19070
        and data["source"]["input_bytes"] == 1196414
    )
    assert key not in response.text
    print(
        {
            "input_bytes": len(raw),
            "accepted_rows": data["source"]["accepted_rows"],
            "windows": data["window_count"],
            "pairs": data["pair_count"],
            "batches": batches,
            "flagged_pairs": data["summary"]["novel_pairs"],
            "response_bytes": len(response.content),
            "elapsed_ms": round(elapsed, 3),
            "process_peak_rss_mib": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
            ),
        }
    )
