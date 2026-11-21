# Recorded KIT sample analysis API

For the current additive response contract and Android integration, use the
[Phase 3C guide](phase-3c-analysis-contract.md). CSV analysis is now implemented
as documented in the [Phase 3B guide](phase-3b-csv-analysis.md).

These endpoints are in the main FastAPI backend. All numerical examples below
come from the packaged real KIT test recording and the existing fitted model.
They are not mock/demo health predictions. The frozen ML outputs are under
`tests/fixtures/kit_sample_ml_results.json` solely for tests; runtime never reads
that file. Its provenance records the model and sample hashes and generation
method. No result or analysis is persisted by these endpoints.

## Authentication and requests

Require `Authorization: Bearer <Firebase ID token>` and the existing verified-email
checks. The sample endpoints are independent of account/vehicle database rows and
require no `X-Account-UID` header. They accept only an allowlisted sample ID, not
file paths, user-selected ML URLs, vehicle IDs or inference credentials.

```bash
curl -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  https://drivepulse-backend-91fz.onrender.com/api/v1/analysis/samples
curl -X POST -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  https://drivepulse-backend-91fz.onrender.com/api/v1/analysis/samples/kit-20180320-normal/analyze
```

No POST body is required. These commands describe the reviewed API; they do not
imply these local changes have been deployed. Neither endpoint exposes the
server-to-server key. Responses use `Cache-Control: no-store`.

## Catalog response

The catalog reads manifest IDs and validates each asset through the existing
checksum/schema/window-pair loader before advertising it. Missing/corrupt assets
fail closed rather than producing a misleading available-sample entry.

```json
{
  "schema_version": 1,
  "samples": [
    {
      "id": "kit-20180320-normal",
      "display_name": "KIT recorded OBD sample — 20 March 2018",
      "recording_id": "KIT-2018-03-20_Seat_Leon_KA_KA_Normal",
      "recording_date": "2018-03-20",
      "dataset": "KIT Automotive OBD-II",
      "creator": "Marc Weber",
      "source_doi": "10.35097/1130",
      "license": "CC-BY-4.0",
      "license_url": "https://creativecommons.org/licenses/by/4.0/",
      "source_split": "test",
      "window_count": 163,
      "valid_pair_count": 162,
      "window_seconds": 10,
      "compatible_model_version": "kit-xgb-forecast-v1",
      "limitations": [
        "Research recording, not the user's Garage vehicle or live telemetry.",
        "Filename Normal is recording context, not a verified healthy or fault-free label.",
        "KIT has no verified mechanical fault labels; novelty is not a fault diagnosis.",
        "Combustion-engine OBD data, not EV traction-battery measurements.",
        "Held out from fitting/calibration but already included in historical test evaluation; not a new independent evaluation.",
        "Recording IDs are not verified independent vehicle IDs."
      ]
    }
  ]
}
```

## Analysis response: real-data excerpt

The full response has **162 predictions and score-series points, 163 telemetry
windows**, ten signal/unit definitions, the complete sample metadata and
limitations. Only the first prediction/score point is shown below. The summary
and both intervals are complete. The top-level omitted fields are `sample`,
`telemetry`, `signals`, `limitations` and the explanatory timing/contribution fields.

```json
{
  "schema_version": 1,
  "analysis_type": "kit_telemetry_novelty",
  "window_count": 163,
  "pair_count": 162,
  "window_seconds": 10,
  "model": {
    "schema_version": 1,
    "model_version": "kit-xgb-forecast-v1",
    "assessment_type": "novelty",
    "threshold": 8.083880990992366,
    "label_status": "unlabeled_dataset_not_fault_diagnosis"
  },
  "summary": {
    "evaluated_pairs": 162,
    "novel_pairs": 2,
    "not_novel_pairs": 160,
    "novel_percentage": 1.2345679012345678,
    "max_anomaly_score": 11.339888612364291,
    "mean_anomaly_score": 1.794950424799447,
    "threshold": 8.083880990992366
  },
  "flagged_intervals": [
    {
      "recording_id": "KIT-2018-03-20_Seat_Leon_KA_KA_Normal",
      "recording_date": "2018-03-20",
      "split": "test",
      "segment_id": 0,
      "start_seconds": 31660,
      "end_seconds": 31670,
      "pair_ids": [
        "pair-000117"
      ],
      "peak_anomaly_score": 11.003060237739609
    },
    {
      "recording_id": "KIT-2018-03-20_Seat_Leon_KA_KA_Normal",
      "recording_date": "2018-03-20",
      "split": "test",
      "segment_id": 0,
      "start_seconds": 31770,
      "end_seconds": 31780,
      "pair_ids": [
        "pair-000128"
      ],
      "peak_anomaly_score": 11.339888612364291
    }
  ],
  "persisted": false,
  "predictions": [
    {
      "pair_id": "pair-000000",
      "current_window": {
        "id": "window-000000",
        "recording_id": "KIT-2018-03-20_Seat_Leon_KA_KA_Normal",
        "recording_date": "2018-03-20",
        "split": "test",
        "segment_id": 0,
        "start_seconds": 30480,
        "end_seconds": 30490,
        "relative_start_seconds": 0
      },
      "next_window": {
        "id": "window-000001",
        "recording_id": "KIT-2018-03-20_Seat_Leon_KA_KA_Normal",
        "recording_date": "2018-03-20",
        "split": "test",
        "segment_id": 0,
        "start_seconds": 30490,
        "end_seconds": 30500,
        "relative_start_seconds": 10
      },
      "anomaly_score": 3.4350437611685285,
      "threshold": 8.083880990992366,
      "is_novel": false,
      "normalized_signal_errors": {
        "coolant_temp_c": 1.4148030227234043,
        "map_kpa": 0.0,
        "engine_rpm": 3.4350437611685285,
        "speed_kmph": 0.19998863630410724,
        "intake_air_temp_c": 0.0,
        "maf_gs": 0.9324217461072069,
        "throttle_pct": 0.0,
        "ambient_air_temp_c": 0.0,
        "pedal_d_pct": 3.306972062409628e-08,
        "pedal_e_pct": 0.0
      },
      "top_signal_deviations": [
        {
          "signal": "engine_rpm",
          "normalized_error": 3.4350437611685285
        },
        {
          "signal": "coolant_temp_c",
          "normalized_error": 1.4148030227234043
        },
        {
          "signal": "maf_gs",
          "normalized_error": 0.9324217461072069
        }
      ]
    }
  ],
  "score_series": [
    {
      "pair_id": "pair-000000",
      "window": {
        "id": "window-000001",
        "recording_id": "KIT-2018-03-20_Seat_Leon_KA_KA_Normal",
        "recording_date": "2018-03-20",
        "split": "test",
        "segment_id": 0,
        "start_seconds": 30490,
        "end_seconds": 30500,
        "relative_start_seconds": 10
      },
      "anomaly_score": 3.4350437611685285,
      "threshold": 8.083880990992366,
      "is_novel": false
    }
  ]
}
```

## Timing, statistics and interpretation

- A pair forecasts the medians of its following window from its current window's
  30 features. The score is assigned to the following/target window.
- Window IDs are stable positions within the returned recording, not database IDs.
  Source clock seconds and filename date are retained; timezone is unknown. Do
  not convert them into UTC instants without additional source information.
- `relative_start_seconds` starts at the first retained window separately for
  each recording/date/segment/split. Do not connect graph points across boundaries.
- `summary` counts evaluated pairs, not raw rows. Novel means the saved model's
  strict score > threshold flag. Novel percentage is `novel_pairs / evaluated_pairs
  * 100`, not a health percentage. Mean uses all returned pair scores.
- `flagged_intervals` merges directly adjacent flagged target windows only, within
  matching recording/date/segment/split. Bounds are **[start, end)**. Unflagged
  pairs, gaps and group boundaries break intervals. Original predictions remain.
- `top_signal_deviations` ranks the three largest normalized forecast errors;
  ties follow fitted signal order. These are not SHAP values, fault diagnoses,
  failure probabilities or causal claims.
- `score_series` gives target-window time/identity, score, threshold and novelty
  flag without requiring model recalculation in Android.
- `telemetry` contains actual prepared ten-second medians with per-window identity;
  units are in `signals`. These are aggregated readings, not instantaneous samples.

KIT uses combustion-engine OBD signals, not EV traction-battery measurements.
`Normal` in the original filename is context, not a verified healthy/fault-free
label. The recording was already part of historical test evaluation; this is a
research demonstration, not new independent validation or a Garage association.

## Error behavior

| Status | Meaning |
| --- | --- |
| 401 | Missing/invalid Firebase identity |
| 403 | Email verification required |
| 404 | Unknown sample ID |
| 422 | Malformed sample ID or rejected prepared inference input |
| 503 | Missing/corrupt/incompatible sample or missing ML configuration/authentication/availability |
| 504 | ML batch request timeout |
| 502 | Invalid upstream status, malformed/incomplete/mismatched inference results |
| 500 | Unexpected internal processing failure |

Errors contain only a safe `detail`. No filesystem paths, tokens, shared keys,
upstream response bodies or stack traces are returned. A later batch failure
fails the whole request; there is no partial success or fabricated fallback.

## Processing and reuse

`analysis_service.load_analysis_sample()` uses the existing `kit_samples` loader.
`analyze_sample()` calls the existing `KITInferenceService`; the 162 pairs are
processed sequentially as **32, 32, 32, 32, 32, 2**. All input validation precedes
network calls. `build_analysis(windows, pairs, inference)` is the source-independent
postprocessing core also used by the validated Phase 3B CSV adapter.
The main backend never loads model artifacts or imports scientific ML packages.

## Deployment review

Main backend variables:

| Variable | Value/policy |
| --- | --- |
| `ML_SERVICE_URL` | HTTPS ML base URL, normally `https://drivepulseai.onrender.com` |
| `ML_INFERENCE_API_KEY` | Same private server-managed key as ML service; never Android |
| `KIT_ML_BATCH_SIZE` | Default 32; must not exceed ML `KIT_MAX_BATCH_SIZE` |
| `ML_REQUEST_TIMEOUT_SECONDS` | Default 30 seconds per batch; connect/pool at most 5 |

ML service variables: `ML_INFERENCE_API_KEY` and `KIT_MAX_BATCH_SIZE` (default 32).
Its existing `PORT` and `MODEL_REPOSITORY_DIR` packaging remain unchanged.

1. Review all current callers and provision the matching shared key securely.
2. Prepare authorized callers to send the header; the old ML app ignores it.
3. Deploy secured Step 2 ML batch inference and verify health, key rejection and a
   small authorized real request. `/health` alone does not prove auth is configured.
4. Include all new main-backend modules and `app/data/samples/kit/` assets in the
   backend-root source deployment. No repository-root dataset/model is needed.
   A future wheel/image build must explicitly include non-Python assets.
5. Configure the backend key/URL/limits, deploy only after approval, then perform
   an authorized smoke test of the new main-backend endpoints.
6. Measure actual Render cold starts, network latency, memory and concurrent load
   before exposing broad app traffic or raising limits. Keep sequential batches.

The currently deployed ML service may not have Step 2. A missing batch route fails
safely; no downgrade to unauthenticated single-pair inference occurs. No deployment
was performed by this implementation. Files remain local until reviewed/committed.

Thirty seconds is a **per-batch** deadline, not a whole-analysis deadline; six
batches can consume roughly 180 seconds plus local work in a failure scenario.
Actual Render/client request budgets are unverified. Rate limits, per-user quotas,
a total endpoint deadline and real-host capacity testing remain production rollout
considerations; no queues, background jobs or uncontrolled concurrency were added.

## Tests

From the repository root:

```bash
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q
backend/.venv/bin/ruff check backend/
PYTHONPATH=ml .venv/bin/python -m pytest ml/tests ml/hf_deployment/tests -q
```

PostgreSQL regression tests need an isolated `TEST_DATABASE_URL` whose database
name ends in `_test`. Never point them at production: existing fixtures truncate
records and exercise migrations. Optional model tests skip if scientific packages
or artifacts are unavailable in the backend-only environment.

`test_analysis_api.py` runs real Firebase guard logic with only remote token
verification stubbed. Deterministic HTTP mocks use genuine recorded ML outputs,
including the two flagged windows. Boundary tests vary metadata to test grouping;
those variants are not presented as actual recordings or predictions.

The optional `test_real_full_sample_both_apps_and_existing_client` uses the real
main application, client, ML application, artifact and all 162 real pairs with an
ephemeral test credential. It checks fixture parity, counts, ordering, timing and
summaries. It prints local timing/response-size/process-memory observations under
pytest `-s`. It does not test production Firebase, TLS, Render or network latency.
The backend CI adds a dedicated integration job with the pinned ML runtime so
these tests can run without adding ML dependencies to the production backend.

No Android changes, Oxford integration, model training, model artifact
updates, database schema changes, commits, pushes or deployments belong to this step.
