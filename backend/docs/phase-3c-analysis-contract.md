# Phase 3C: final KIT analysis contract for Android

This guide describes local implemented behavior, not a claim of Render rollout.
API `schema_version: 1` is retained: existing fields are preserved; the Phase 3C
fields are additive. Clients should tolerate unknown additional response fields.
No Android implementation, database persistence or inference artifact changes
are part of this work.

## Endpoints and requests

All endpoints require `Authorization: Bearer <verified Firebase ID token>` and the
existing email-verification guard. They do not require Garage state or
`X-Account-UID`, and do not accept an ML credential or a vehicle association.

| Method and path | Request | Response |
| --- | --- | --- |
| `GET /api/v1/analysis/samples` | No body | `schema_version`, validated manifest-backed `samples` |
| `POST /api/v1/analysis/samples/{sample_id}/analyze` | No body; allowlisted ID | `SampleAnalysis` |
| `POST /api/v1/analysis/upload` | Multipart: exactly one `file` and text `recording_date` | `UploadedAnalysis` |

Use the catalog ID `kit-20180320-normal` for the packaged recording. Exact raw
CSV headers, units, encoding rules and validation remain unchanged from the
[Phase 3B guide](phase-3b-csv-analysis.md). This is not an arbitrary OBD/EV importer.

```bash
curl -X POST -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  http://localhost:8000/api/v1/analysis/samples/kit-20180320-normal/analyze
curl -X POST -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  -F 'recording_date=2018-03-20' -F 'file=@/path/to/recording.csv;type=text/csv' \
  http://localhost:8000/api/v1/analysis/upload
```

## Common response and source differences

| Field | Meaning / Android use |
| --- | --- |
| `schema_version`, `analysis_type` | Version 1; `kit_telemetry_novelty` |
| `source_type` | `packaged_sample` or `uploaded_csv` |
| `sample` (sample response) | Existing manifest provenance/attribution, recording and model compatibility; retained without duplicating it into a second `source` object |
| `source` (CSV response) | Content-derived recording reference, caller-supplied date, unverified metadata marker, byte/row/missingness/segment audit counts, format/preprocessing versions |
| `model` | Accepted upstream version, assessment type, threshold and unlabeled-dataset disclaimer |
| `window_count`, `pair_count`, `window_seconds` | Retained windows, evaluated adjacent pairs, fixed ten-second duration |
| `summary` | Evaluated/novel/not-novel counts, percentage, finite mean/max score and threshold |
| `predictions` | Ordered pair IDs, input/target window references, score, strict novelty decision, ten normalized errors and top three deviations |
| `flagged_intervals` | Ordered merged target-window ranges with source grouping, contributing pair IDs and peak score |
| `score_series` | Ordered target-window references, pair IDs, score, threshold and flags; no frontend model calculations needed |
| `telemetry` | Ordered window references, actual prepared medians and sparse partial-missingness fractions |
| `signals` | Stable IDs in fitted order, physical units and new readable `display_name` |
| `explanation` | New deterministic summary, signal-scope summary, up to three ranked positive deviations and fixed interpretation/limitation text |
| `time_basis`, `relative_time_basis`, `interval_definition`, `contribution_definition` | Machine-readable contracts' existing descriptive strings |
| `limitations`, `persisted` | Source-specific research caveats; `persisted` is always false |

An uploaded CSV never inherits the packaged sample's DOI, attribution, test-split
status or recording ID. Its date is marked `caller_supplied_unverified`; its split
is `uploaded`. Window/pair IDs identify response-local positions, not database
analysis records or verified vehicle identities.

## Scores: what is calculated and what is available

The saved `kit-xgb-forecast-v1` model forecasts the **next** window's ten sensor
medians from the current window's thirty features. It uses XGBoost for engine RPM,
speed and mass air flow, and persistence for the other seven targets. Persistence
forecasts the current median again; it is still a forecast, not the target reading.
These modes are recorded in `ml/reports/modeling/kit_xgb_forecast_baseline.json`.

For signal j, the model calculates:

```text
signed residual[j] = actual next median[j] - forecast next median[j]
normalized error[j] = abs(signed residual[j] / saved calibration scale[j])
anomaly_score = max(normalized error[all ten signals])
is_novel = anomaly_score > saved threshold
```

Calibration scales are per-signal root-mean-square residuals from calibration
data (a scale at or below 1e-12 is replaced with 1.0 by the existing model).
The saved threshold is its 99th-percentile calibration score, approximately
8.083880990992366. Equality is **not** novel. No threshold/model change occurs here.

Normalized errors and scores are **dimensionless**: do not attach RPM/°C/% units
to them. Physical units apply only to measured telemetry medians (and would apply
to actual forecasts/residuals if a future serving contract exposed them).
The ML service currently returns scores, flags and normalized errors; it does
**not** return forecasts, signed residuals or calibration scales. This API does
not reconstruct or fabricate those missing values. Absolute normalized errors
also do not establish the direction of a physical change.

The flagged percentage is `novel_pairs / evaluated_pairs * 100`. It is neither
accuracy, a calibrated fault probability nor a vehicle-health percentage. The
finite mean is computed with scaling before summation to avoid overflow; last-bit
roundoff relative to an unscaled historical mean is possible. Scores themselves
are unchanged.

## Explanations and rankings

`explanation.summary` reports the actual evaluated/flagged counts and number of
merged intervals. Zero flags explicitly state that faults are not ruled out.
`signal_summary` names actual returned signals; no generative model or external
service is used.

`strongest_signal_deviations` ranks each signal's maximum normalized error over
flagged pairs when any are flagged, otherwise over all evaluated pairs. This
scope is explicit in `signal_scope`. Up to three **positive** entries are returned;
all-zero errors produce an empty list and a truthful zero-error explanation.
Each pair's existing `top_signal_deviations` remains its own top three (including
zeros, for compatibility). Both rankings use stable fitted-signal order for ties.
No SHAP values, causal importance, broken components, health estimates or severity
classes are inferred.

The KIT recording has no verified mechanical fault labels. Neither a filename
containing `Normal` nor a below-threshold result proves health. This combustion-
engine novelty model is not validated for EV battery diagnosis or RUL.

## Time axes, intervals and missing data

- Each score belongs to `next_window`, also used as `score_series[*].window`.
  `current_window` is the input context, not the scored time interval.
- Bounds are `[start_seconds, end_seconds)`, where end = start + 10. They identify
  aggregation buckets, not verified fault onset/duration. Partial edge buckets
  remain eligible under the original preprocessing recipe.
- Seconds are original source-clock seconds since midnight, timezone unknown.
  A bucket can end at 86400 without inventing a UTC instant or next day's date.
- Array order preserves source group/segment order. Clock seconds can decrease
  after a backward jump. Never globally sort all points by clock seconds.
- Group charts by `(recording_id, recording_date, split, segment_id)`. Within a
  group, `relative_start_seconds` starts at its first retained window. It resets
  at group boundaries and is not a continuous trip-wide clock across segments.
- Break chart lines at group changes or gaps greater than ten seconds. Overlay
  an interval only on the matching group. Pair/window IDs correlate all arrays.
- Intervals merge only directly adjacent flagged target windows in the same
  group. Unflagged pairs, temporal gaps, dates, splits, recordings and segments
  prevent merging. Every interval retains the exact contributing `pair_ids`.
- `telemetry[*].medians` contains observed aggregates. A true zero is a measured
  zero, never a missing-value replacement. Partial missingness appears in
  `missing_fractions`, a **sparse** map: omitted signals have missing fraction 0.
  Fractions are greater than zero and less than one when emitted. A completely
  absent signal rejects that bucket; no fabricated null/zero graph point replaces
  it. Some retained isolated windows can have telemetry but no evaluated pair.

## Genuine-recording response excerpt

The full response retains all predictions and graph points; this is abbreviated:

```json
{
  "schema_version": 1,
  "analysis_type": "kit_telemetry_novelty",
  "source_type": "packaged_sample",
  "window_count": 163,
  "pair_count": 162,
  "summary": {
    "evaluated_pairs": 162,
    "novel_pairs": 2,
    "not_novel_pairs": 160,
    "novel_percentage": 1.2345679012345678,
    "max_anomaly_score": 11.339888612364291,
    "mean_anomaly_score": 1.7949504247994472,
    "threshold": 8.083880990992366
  },
  "persisted": false
}
```

The explanation reports two flagged intervals. The actual strongest per-signal
maxima over flagged pairs are intake air temperature (11.339888612364291), engine
RPM (5.578469408459581) and vehicle speed (1.9251802407145282). A listed signal need
not itself exceed the threshold. These are normalized deviations, not faults.
The intervals are `[31660,31670)` (`pair-000117`) and `[31770,31780)`
(`pair-000128`), with their original grouping and contributing IDs.

## Errors, retention and processing boundaries

Existing error behavior is preserved: 401 missing/invalid identity; 403 unverified
email; 404 unknown sample; 408 disconnected upload; 413 upload/parser/workload
limit; 415 unsupported media/encoding; 422 invalid input/insufficient windows;
429 upload capacity busy; 502 invalid/incomplete upstream response; 503 unavailable
sample or ML configuration/auth/connectivity; 504 timeout; 500 unexpected internal
failure. Errors expose only safe `detail` strings. An upstream ML 401 is a backend
503, not a request for the Android user to change Firebase credentials.

Examples: `{"detail":"Invalid analysis service response"}` (502) and
`{"detail":"CSV exceeds row limit"}` (413). No stack traces, internal paths,
raw upstream error bodies, Firebase tokens or shared keys are exposed. Analysis
success/handled route-error responses use `Cache-Control: no-store`; authentication
uses the unchanged existing dependency's response behavior.

Uploads remain memory-only and are not saved. Results are not persisted to
PostgreSQL or linked to Garage. No new database sessions, tables, background jobs,
inference retries or parallel ML calls are introduced. Six sequential requests
score the real 162-pair recording; any failed batch fails the entire analysis.

## Phase 4 Android integration contract

1. Use the existing Firebase API client to list samples, analyze a selected ID or
   send exactly one CSV and its explicitly supplied date via native FormData.
   Let the HTTP client set the multipart boundary. Never send an ML key.
2. Read `source_type`; use `sample` or `source` appropriately. Keep research/sample
   attribution separate from a user's Garage. Do not claim uploaded provenance.
3. Render `explanation`, summary counts and limitations without relabeling novelty
   as a fault/health assessment. The API's text is deterministic English; structured
   values remain available for later localization.
4. Plot `score_series` and `telemetry` using the grouping/gap rules above. Resolve
   display names/units from `signals`; errors are dimensionless. Use provided
   rankings and intervals rather than recalculating the model.
5. Preserve loading/cancellation/error states. Never present partial arrays or demo
   values as successful inference. `persisted:false` means no saved History entry.
6. Expect approximately 308 KB sample / 306 KB CSV for this 162-pair recording,
   uncompressed. Metadata repetition is retained for compatibility; no arrays are
   truncated or duplicated to add a separate chart representation. Missingness is
   sparse to limit overhead. Other allowed inputs can produce larger responses.

## Tests and local performance

`tests/test_analysis_contract.py` tests counts, no/single/all/adjacent/separated
flags, ties, zero measurements, partial missingness, score equality, extreme finite
scores, group/gap boundaries, serialization, invalid mutated inputs and both actual
model workflows. Controlled arithmetic fixtures are clearly marked synthetic
boundary cases, not claimed inference evidence. The real integration test uses
the actual model and raw archive, with remote Firebase verification stubbed only.

Run from the repository root with existing environments/dependencies:

```bash
backend/.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests -q
backend/.venv/bin/ruff check backend/
PYTHONPATH=ml .venv/bin/python -m pytest ml/tests ml/hf_deployment/tests -q
```

Full PostgreSQL tests require an isolated `TEST_DATABASE_URL` ending in `_test`;
they migrate/truncate that test database. Genuine model tests need both backend
and pinned serving dependencies. Backend CI's integration job includes this test.
Do not point tests at a developer's user data or Render PostgreSQL.

Local measurements use in-process ASGI transport after model startup. They do not
measure Render cold starts, TLS, DNS, public networking, proxy limits or live
Firebase certificate verification. Version warnings from the available local
scikit-learn 1.9.0 runtime versus artifact 1.7.2 remain a deployment prerequisite:
use `ml/hf_deployment/requirements.txt` (pins sklearn 1.7.2) in production and CI.
No dependency upgrade or artifact rewrite was performed in Phase 3C.

Verification on this machine: **305 backend tests passed**, including dedicated
temporary PostgreSQL tests; **93 ML tests passed, five skipped** for missing
APS/Tongji data. Ruff, formatting and Git whitespace checks passed. In a measured
real-model cross-workflow run, sample and CSV responses were 308,409 and 306,337
bytes; requests took 110.896 ms and 336.694 ms respectively. One Pydantic JSON
serialization of the already-built sample result took 0.994 ms. Whole-process
peak RSS was 369.48 MiB, including the existing ML application's libraries/models;
this is not incremental upload memory. Both workflows returned identical scores
(maximum difference 0.0), rankings, explanations and graph data after excluding
the intentional recording-ID/split source differences. Both produced 163 windows,
162 pairs, six sequential batches and the two expected intervals. The measured
known score remained 3.4350437611685285. These timings are observations from one
warm local run, not throughput benchmarks or Render guarantees.

## Deployment checklist — not executed

- Review diffs and test results before any commit/push. The GitHub Actions deploy
  workflow for the legacy KIT/Oxford ML serving app has been removed; do not use
  that app as the Nissan Leaf production deployment. Render dashboard auto-deploy
  settings were not inspected. No backend deploy workflow is defined; do not assume
  a backend deployment gate/sequence is enforced by CI.
- Inventory existing ML callers before enforcing authentication. Configure the
  **same private** `ML_INFERENCE_API_KEY` on ML and backend, outside source/mobile.
  Deploy the secured batch-capable ML service first; migrate old callers to the
  header. Health endpoints alone do not prove authentication/batch readiness.
- ML: `ML_INFERENCE_API_KEY`, `KIT_MAX_BATCH_SIZE=32`; preserve existing artifact
  paths and pinned dependencies. Verify an unauthorized batch is rejected, then
  one authorized real pair returns the known score/threshold.
- Main backend: `ML_SERVICE_URL` (HTTPS), `ML_INFERENCE_API_KEY`,
  `KIT_ML_BATCH_SIZE=32` (no larger than ML limit),
  `ML_REQUEST_TIMEOUT_SECONDS=30`; existing Firebase/PostgreSQL configuration.
- Preserve Phase 3B controls: `KIT_UPLOAD_MAX_BYTES=2097152`,
  `KIT_UPLOAD_MAX_ROWS=50000`, `KIT_UPLOAD_MAX_WINDOWS=256`,
  `KIT_UPLOAD_MAX_PAIRS=256`, `KIT_UPLOAD_MAX_SEGMENTS=16`,
  `KIT_UPLOAD_MAX_CONCURRENT=2`, `KIT_UPLOAD_MAX_BATCHES=8`,
  `KIT_UPLOAD_ANALYSIS_TIMEOUT_SECONDS=60`. See Phase 3B for hard validation ranges.
- Include `app/data/samples/kit/` and new modules in the backend deployment root;
  install existing updated requirements, including python-multipart. No schema
  migration is needed. Verify model/sample checksums.
- CSV has a 60-second overall request budget after authentication plus per-batch
  network bounds. Sample analysis retains its existing per-batch deadline only;
  six batches can approach 180 seconds. Neither response serialization nor external
  proxy limits are a hard CPU/process deadline. Cold starts can legitimately fail.
- Before public rollout, measure actual Render cold/warm latency, memory, sustained
  load and client/proxy timeouts; establish appropriate ingress/per-user limits.
  Upload concurrency limits are per process, not global quotas. Sample analysis
  does not acquire the upload semaphore; the shared HTTP pool limits connections
  but is not a global request admission policy. No broader capacity is claimed.
- Verify real Firebase signup/login/verified identity on the deployed backend;
  test public TLS/network calls through the main API, both source workflows,
  malformed/oversized files, cancellation and failure states. Ensure secrets never
  reach Android or error/log bodies. Preserve ordinary account/Garage behavior.

Phase 4 can consume this contract after review and coordinated deployment. No
deployment, environment update, commit or push is part of Phase 3C.
