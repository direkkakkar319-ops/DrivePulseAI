# Phase 3B: authenticated KIT raw CSV analysis

The [Phase 3C contract](phase-3c-analysis-contract.md) finalizes the shared result
and Android chart/explanation semantics. The CSV input contract below is unchanged.

## API and identity

`POST /api/v1/analysis/upload` requires the same verified Firebase bearer identity
as sample analysis. Send exactly two multipart parts: one binary `file` with a
`.csv` filename, and one text `recording_date` in valid `YYYY-MM-DD` form. The date
is supplied by the caller and is explicitly **unverified**. Authentication runs
before this endpoint consumes the request body. No client-supplied ML key is used.

```bash
curl -X POST http://localhost:8000/api/v1/analysis/upload \
  -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  -F 'recording_date=2018-03-20' \
  -F 'file=@/path/to/2018-03-20_Seat_Leon_KA_KA_Normal.csv;type=text/csv'
```

Use a fresh verified Firebase ID token; do not paste it into source control or
logs. `GET /api/v1/analysis/samples` and
`POST /api/v1/analysis/samples/{sample_id}/analyze` keep their existing contracts.

## Supported format: `kit_obd_raw_v1`

Only the original publisher's comma-delimited, eleven-column KIT OBD recording
layout is supported, with the following **exact ordered header**:

```csv
Time,Engine Coolant Temperature [°C],Intake Manifold Absolute Pressure [kPa],Engine RPM [RPM],Vehicle Speed Sensor [km/h],Intake Air Temperature [°C],Air Flow Rate from Mass Flow Sensor [g/s],Absolute Throttle Position [%],Ambient Air Temperature [°C],Accelerator Pedal Position D [%],Accelerator Pedal Position E [%]
```

| Raw column | Canonical signal | Unit |
| --- | --- | --- |
| Time | Clock used for segmentation/windowing | `HH:MM:SS.f`, 1–6 fractional digits |
| Engine Coolant Temperature | `coolant_temp_c` | °C |
| Intake Manifold Absolute Pressure | `map_kpa` | kPa |
| Engine RPM | `engine_rpm` | RPM |
| Vehicle Speed Sensor | `speed_kmph` | km/h |
| Intake Air Temperature | `intake_air_temp_c` | °C |
| Air Flow Rate from Mass Flow Sensor | `maf_gs` | g/s |
| Absolute Throttle Position | `throttle_pct` | % |
| Ambient Air Temperature | `ambient_air_temp_c` | °C |
| Accelerator Pedal Position D | `pedal_d_pct` | % |
| Accelerator Pedal Position E | `pedal_e_pct` | % |

There are no optional columns. UTF-8, optionally with a BOM, is required. The
publisher archive also contains the literal header spelling `Â°C`; this verified
alias is normalized to `°C`. No other aliases or unit conversions are inferred.
Values are interpreted in the units declared by these headers; the server cannot
prove that a caller has measured or labeled them honestly. Arbitrary OBD-II/EV
CSVs, prepared-window CSVs, semicolon-separated data, ZIP/gzip uploads, UTF-16,
extra metadata columns, and multiline quoted fields are unsupported.

Every row must have eleven bounded fields. A blank telemetry cell represents a
missing reading. A nonblank cell must be numeric, finite and within finite
float32 magnitude. This is a representation bound, not a claim that every finite
reading is physically plausible. Invalid timestamps, malformed rows, NaN and
infinity reject the file. A blank file or a header without readings is rejected.

Rows remain in acquisition order: they are never sorted or deduplicated. Equal
clock times remain separate observations, matching the research recipe. Every
backward clock jump starts a new segment, including a midnight wrap; no next-day
date or UTC timestamp is guessed. A supplied date applies to the entire upload.
No vehicle identifier is required or inferred. A content-derived `upload-…`
recording reference identifies this request's data, not a Garage vehicle.

## Exact preprocessing and shared inference

The statistics kernel is `app/services/kit_preprocessing.py`; the original offline
recipe `ml/scripts/preprocess_kit_obd.py` imports this same standard-library code.
For accepted readings the original recipe is preserved:

1. Parse clock seconds since midnight, timezone unknown.
2. Separate backward jumps and bucket by `floor(seconds / 10)` within each segment.
3. For each of the ten signals, calculate median, **population** standard deviation,
   and `1 - valid_reading_count / bucket_row_count`, in that order.
4. Drop a bucket if any signal has no valid reading. Keep partial edge buckets;
   there is no interpolation, filling, smoothing or resampling.
5. Construct pairs only when retained windows have the same recording/date/split/
   segment and their starts differ by exactly ten seconds. Do not bridge gaps.
6. Pass thirty current-window features and ten following-window medians through
   the existing `KITInferenceService`, with deterministic ordered pair IDs.

The upload validator is intentionally stricter than the offline ingestion script:
the script skips invalid timestamps/treats invalid numeric cells as missing,
whereas this public endpoint rejects them. Blank missing cells share the same
aggregation semantics. Upload split metadata is `uploaded`, never `test`.

Sample and upload analysis converge in `analysis_service.analyze_prepared`, then
reuse the existing authenticated sequential batch client and `build_analysis`.
No model is loaded into the main backend. There are no retries, fabricated
predictions, partial successful analyses, or new database records.

## Response

The response extends the same prepared-analysis core used by Phase 3A. It has
`source_type: "uploaded_csv"` and `source` instead of manufactured sample
provenance. Existing sample responses are unchanged. An abbreviated excerpt from
the real 2018-03-20 recording integration test is:

```json
{
  "schema_version": 1,
  "analysis_type": "kit_telemetry_novelty",
  "source_type": "uploaded_csv",
  "source": {
    "kind": "uploaded_csv",
    "format_version": "kit_obd_raw_v1",
    "preprocessing_version": "kit-10s-window-recipe-v1",
    "recording_date": "2018-03-20",
    "metadata_verification": "caller_supplied_unverified",
    "input_bytes": 1196414,
    "accepted_rows": 19070
  },
  "window_count": 163,
  "pair_count": 162,
  "window_seconds": 10,
  "summary": {
    "evaluated_pairs": 162,
    "novel_pairs": 2,
    "not_novel_pairs": 160,
    "novel_percentage": 1.2345679012345678,
    "max_anomaly_score": 11.339888612364291,
    "mean_anomaly_score": 1.794950424799447,
    "threshold": 8.083880990992366
  },
  "persisted": false
}
```

This excerpt omits fields for readability. The actual response also includes
model metadata, source audit counts and reference, all per-pair predictions,
normalized signal errors and their largest contributors, flagged intervals,
score series, signal units, prepared-window medians, time definitions and
limitations. Intervals cover flagged **target** windows `[start, end)` and merge
only adjacent flagged targets within the same recording/date/split/segment.
These are statistical deviations, not confirmed mechanical faults, causal
explanations, health percentages, EV battery diagnoses or RUL estimates. KIT is
combustion-engine research telemetry; generalization to other vehicles is not
established by a successful API call.

## Security, bounds, retention and configuration

| Main-backend environment variable | Default | Allowed configuration range |
| --- | --- | --- |
| `KIT_UPLOAD_MAX_BYTES` | 2097152 (2 MiB) | 1024–16777216 |
| `KIT_UPLOAD_MAX_ROWS` | 50000 | 2–200000 |
| `KIT_UPLOAD_MAX_WINDOWS` | 256 candidate buckets | 2–1024 |
| `KIT_UPLOAD_MAX_PAIRS` | 256 | 1–1024 |
| `KIT_UPLOAD_MAX_SEGMENTS` | 16 | 1–64 |
| `KIT_UPLOAD_MAX_CONCURRENT` | 2 per process | 1–4 |
| `KIT_UPLOAD_MAX_BATCHES` | 8 sequential requests | 1–32 |
| `KIT_UPLOAD_ANALYSIS_TIMEOUT_SECONDS` | 60 | positive finite, at most 180 |

The candidate-window cap includes buckets later dropped for missing signals.
Exceeding any workload bound rejects the complete input; no truncation occurs.
The existing `KIT_ML_BATCH_SIZE=32` and `ML_REQUEST_TIMEOUT_SECONDS=30` remain
unchanged. Uploads must also fit `ceil(pair_count / batch_size)` within the batch
budget. The real 162-pair recording uses `[32,32,32,32,32,2]`.

The multipart parser counts actual streamed bytes, independent of Content-Length.
Total body overhead is capped at 16 KiB in addition to the file bound. It allows
two parts, four headers per part, and 2048 header bytes. CSV lines are at most
2048 characters and fields at most 128 characters. Filename paths are ignored;
filenames are neither opened nor echoed. No expression evaluation occurs.

Processing is bounded in memory: no permanent or temporary upload files are
created, parser buffers are cleared on all exit paths, and raw bytes are released
before remote inference. Analysis is not saved, and no Garage association occurs.
The request deadline includes upload reception, preparation, capacity waiting
and inference, beginning after Firebase authentication. CPU preparation checks
the deadline cooperatively in a worker thread; it is not a hard process kill.
Response serialization and external proxy/client limits are separate. Capacity
waits at most one second. Limits are per backend process, not a global rate limit;
production ingress/rate controls and realistic Render load testing remain needed.

| HTTP status | Meaning |
| --- | --- |
| 401 / 403 | Existing Firebase identity/verification rejection |
| 408 | Disconnected upload |
| 413 | Byte, parser or workload bound exceeded |
| 415 | Unsupported multipart/media type, filename type or encoding |
| 422 | Missing/duplicate parts, invalid date/schema/value/time, or insufficient adjacent windows |
| 429 | Per-process upload capacity busy |
| 502 | Invalid/incomplete/inconsistent ML response |
| 503 | Missing ML configuration, upstream authentication/configuration/connectivity failure |
| 504 | Upload-analysis deadline or ML request timeout |
| 500 | Unexpected internal processing failure (generic response) |

Examples: `{"detail":"Unsupported KIT columns, order or units"}` (422),
`{"detail":"CSV exceeds row limit"}` (413), and
`{"detail":"CSV analysis timed out"}` (504). No credentials, file contents,
private paths, upstream bodies or stack traces are returned. Responses use
`Cache-Control: no-store` at this route's success/error boundary.

## Verification and deployment prerequisites

Install the updated backend requirements: the only added runtime package is
`python-multipart>=0.0.34,<1`, used directly for bounded streaming callbacks.
The main backend needs no scientific ML packages. Its backend deployment root
contains the shared preparation module; the repository-root research package is
not required on Render.

Run the backend tests with the existing dedicated `TEST_DATABASE_URL` convention:

```bash
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q
backend/.venv/bin/ruff check backend/
```

The real-model integration test is
`backend/tests/test_csv_analysis.py::test_genuine_full_csv_both_apps`. It requires
the existing ML serving dependencies/artifact and tracked publisher archive parts
in addition to backend dependencies. It reads the raw recording from the archive
without modifying it, stubs external Firebase verification only, and exercises
both real FastAPI apps over in-process HTTP. It compares all 162 results with the
established reference. A second real recording verifies backward-jump segmentation
against frozen prepared windows. CI's KIT integration job includes the CSV tests
using the pinned ML serving runtime. Standard backend-only runs skip optional
real-model tests when scientific dependencies are unavailable.

Local verification on this development machine: 276 backend tests passed (using
an isolated temporary PostgreSQL database); the ML suite passed 93 and skipped
five dataset-dependent tests. The genuine CSV integration accepted 1,196,414
bytes / 19,070 rows, produced 163 windows and 162 pairs in six batches, and returned
two flagged pairs. Its response was 300,183 bytes; one measured request took
372.506 ms after application/model startup. Peak RSS was 369.59 MiB for the entire
Python test process, including the existing ML application's loaded models and
libraries, **not** incremental upload memory. This was in-process transport,
without TLS/public networking or remote Firebase, not a Render capacity result.
The available local model runtime emitted a scikit-learn version warning
(artifact 1.7.2, installed 1.9.0) and NumPy/Starlette deprecation warnings. The known
scores still matched, but the pinned serving runtime configured in CI should be
used for deployment; that remote CI job was not executed here.

No Render operation was performed. Before deploying the backend, deploy the
secured batch-capable ML service and coordinate the same private
`ML_INFERENCE_API_KEY` on both services. ML also requires `KIT_MAX_BATCH_SIZE`
(default 32); backend requires `ML_SERVICE_URL`, the same key, compatible
`KIT_ML_BATCH_SIZE`, and its timeout configuration. Health endpoints alone do not
prove that batch authentication works. Verify one authorized analysis afterward.
Cold starts, public-network latency, sustained concurrency and Render proxy limits
were not measured locally; the 60-second default can legitimately return 504.

For later Android integration, submit the selected file with FormData and the
explicit recording date through the **main backend** authenticated API client;
allow the native HTTP client to set the multipart boundary. Do not send an ML key,
call the ML service directly, automatically attach a Garage vehicle, or persist
results as genuine history. Display compatibility/novelty limitations and handle
the documented statuses. Android UI and CSV selection are unchanged in Phase 3B.
