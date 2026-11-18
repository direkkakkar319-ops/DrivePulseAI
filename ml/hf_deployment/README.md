# KIT inference service on Render

This directory is the Docker build context for the existing research inference
service. This change adds secured, bounded KIT batch transport; it does not
retrain, replace or recalibrate the model. The existing legacy Oxford route is
not integrated with the application and only receives the same authentication
guard as the other inference routes. Its algorithm/artifact remain unchanged.

## Server configuration

| Variable | Behavior |
| --- | --- |
| `ML_INFERENCE_API_KEY` | Required for inference. Supply a high-entropy server-managed secret of at least 32 UTF-8 bytes, without surrounding whitespace. No default or bypass. |
| `KIT_MAX_BATCH_SIZE` | Default 32; integer from 1 through 256. Invalid settings fail startup. The ceiling is an input bound, not a measured Render capacity guarantee. |
| `MODEL_REPOSITORY_DIR` | Defaults to `model_repository/` next to `app.py`; the Docker image sets `/app/model_repository`. |
| `PORT` | Render listening port; Docker command falls back to 8000. |

Read configuration at startup; changing a credential or limit requires process
restart/redeployment. Never commit, log, print, embed in an image, or put an
inference credential in the Android app. No production secret is provided here.

Every inference request must include the header `X-ML-API-Key` with the configured
secret. Comparison uses `hmac.compare_digest` on UTF-8 bytes. Missing or incorrect
caller credentials return generic HTTP 401. Missing, blank, short or
whitespace-padded server configuration disables inference with generic HTTP 503.
Neither error includes credentials. There is no unauthenticated inference mode.

`GET /health` remains public and returns the existing model-readiness response.
It deliberately does not certify authentication configuration. Check both health
and an authenticated inference request before directing caller traffic.
Swagger/OpenAPI remain available and declare API-key authorization; they do not
expose the configured credential. All validation responses omit raw input values.

## API contracts

### Existing single-pair route

`POST /v1/score/kit-window-pair` retains its original body and response:

- `schema_version`: 1.
- `current_window_features`: exactly the 30 fitted feature names and finite values.
- `next_window_medians`: exactly the ten fitted target names and finite values.

Authentication is now required. JSON object order is irrelevant; the service
constructs columns in saved model order. Scores, threshold comparison and signal
errors use the unchanged maximum normalized forecast-error calculation.

### New batch route

`POST /v1/score/kit-window-pairs` accepts:

- `schema_version`: 1.
- `pairs`: a nonempty array, limited by `KIT_MAX_BATCH_SIZE` (hard ceiling 256).
- Each item: `pair_id`, `current_window_features`, `next_window_medians`.
- `pair_id`: unique within the request, 1–128 ASCII characters; first character
  alphanumeric, subsequent characters alphanumeric or `.`, `_`, `:`, `-`.
- Feature dictionaries follow the same contract as the single route. Do not
  include `schema_version` inside an item. Extra envelope/item fields are rejected.

The response has `schema_version`, `model_version`, `assessment_type`, `threshold`,
`label_status`, and `results`. Each result has the submitted `pair_id` plus the
complete existing single-pair response fields: score, threshold, novelty flag,
per-signal normalized errors and model metadata. Result order matches input order.
The whole batch is validated before inference; invalid input yields no partial
results. An empty/oversized/duplicate-ID/incompatible-feature request returns 422.
Inference failure or nonfinite output returns generic 503.

The loaded model is reused. A batch creates one ordered feature matrix and makes
one model forecast call, then computes normalized residuals and scores across all
rows. No model loading, fitting or calibration occurs per request.

KIT novelty is not mechanical fault diagnosis. `is_novel` is strictly
`anomaly_score > threshold`; scores are not probabilities. The request contains
prepared windows, not raw CSV, and the caller remains responsible for real source,
segment, unit and ten-second adjacency validation. No history is persisted here.

The existing `/v1/estimate/oxford-rul` route also requires the shared credential,
preventing an unprotected compute endpoint. No new Oxford capability was added.

## Deployment and coordinated authentication rollout

Do not deploy this change until all existing callers are inventoried. It changes
unauthenticated single-pair calls into authenticated calls intentionally.

1. Generate/store the shared secret through the operational secret manager, not
   this repository. Configure it in both the ML service and authorized backend.
2. Prepare callers to send `X-ML-API-Key` before enforcing it. The old service
   ignores the additional header, allowing this caller-first rollout. Main-backend
   integration is a later step and is not implemented by this change.
3. Review and deploy the secured ML service with `KIT_MAX_BATCH_SIZE=32` initially.
4. Verify public health, missing/wrong-key rejection, correct-key single inference,
   and a small real batch. Verify the known score around 3.435043761.
5. Measure on the actual Render instance before raising batch limits or concurrency.
   Coordinate credential rotation/restarts with every caller; only one key is
   active per process. Do not roll back to public inference to resolve a mismatch.

The existing Dockerfile remains valid: it installs the same pinned requirements,
loads both existing artifacts, runs non-root and uses Render's `PORT`. No new
runtime dependency or Docker change is needed. Artifact paths and model code
copies are unchanged. Sample datasets are not added to the image.

The current main backend does not call this service yet. Later it must verify
Firebase identity, resolve validated samples, chunk pairs into bounded requests,
add the server credential over HTTPS, and validate returned IDs/versions/counts.
It must never pass this credential to mobile clients or treat it as a Firebase token.

## Capacity and operational limits

Default 32 is a conservative initial bound, not a proven safe production load.
The model uses up to four XGBoost threads. Concurrent requests can oversubscribe a
small instance; additional workers duplicate scientific-runtime/model memory.
Matrix size grows with batch rows, as do Python/Pydantic/DataFrame/response objects.
A 3.46 MB artifact does not represent total process memory. Cold starts, peak RSS,
latency, repeated requests and concurrent load require Render measurements.

A full 162-pair recording is not approved as one request by the default limit;
it needs six requests of at most 32 pairs. Future callers should bound concurrent
requests, use timeouts and avoid retry storms. This change does not add rate
limiting, a global inference concurrency cap, or an HTTP body-byte limit; configure
edge limits and evaluate these before broad public traffic. The batch ceiling
limits validated items, not JSON parser allocation for an arbitrarily large body.

## Local verification

Use the existing environment with the inference runtime, pytest and httpx available:

```bash
PYTHONPATH=. python -m pytest ml/hf_deployment/tests -q
PYTHONPATH=ml python -m pytest ml/tests -q
ruff check ml/
```

CI has a separate serving test job using `requirements.txt` from this directory,
plus pytest/httpx, so artifact tests run with the pinned deployment environment.
Local environments with newer NumPy/scikit-learn can produce persistence warnings;
a passing local test does not replace testing the pinned runtime.

Tests use real prepared KIT test windows and the trusted existing artifact. They
never contact Render, retrain models, write artifacts or generate analysis files.
