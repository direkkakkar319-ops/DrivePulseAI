# Deployment plan

This document describes the planned deployment for the current DrivePulseAI
prototype. It is a plan, not a record of services already deployed. The web app
has Vercel preview deployment automation; the API, model service, cloud database,
and production APK pipeline still need to be configured.

## Proposed layout

```text
Web browser ───────────────> Next.js web app on Vercel

Android APK ── Firebase ID token ──> FastAPI & ML Models on Render
                                         └──> Render PostgreSQL

Recorded KIT/Oxford data ── replay tool ──> FastAPI & ML API on Render ──> Android app
```

The mobile app calls only the DrivePulseAI API hosted on Render. It must not
contain database credentials or internal secrets. The backend on Render verifies
Firebase identity, validates the request, and performs ML inference directly on
Render using the locally packaged model artifacts (`kit_xgb_forecast.joblib` and
`oxford_rul_theilsen.joblib`).

## Deployment branch

Deploy the current working branch, `chore/remove-nissan-leaf-workflow`, as the
source for this rollout. Do not use `main` or require a merge to `main` first.
Configure Render to build this branch, create a Vercel preview/branch deployment
from this branch, and build the APK from the same branch commit. Record the Git
SHA used for each service so the API, model, web app, and APK can be matched.
Use a non-production database and preview/staging URLs during integration; do not
change the `main` production deployment or point it at this branch. Rebuild and
redeploy from this branch whenever its deployment code changes.

## Deployment order

## Render deployment decision

Deploy the FastAPI backend and the machine learning models directly on Render.
Do not deploy on Hugging Face or create Hugging Face Inference Endpoints. The
mobile app and clients call only the Render API; FastAPI verifies Firebase
identity, validates incoming requests, and loads the pinned model artifacts
(`kit_xgb_forecast.joblib` and `oxford_rul_theilsen.joblib`) once at startup.

All inference compute runs on Render. The machine learning models are lightweight
(~3.5 MB total) and run within the FastAPI application process on Render. This
eliminates external network latency, removes extra hosting costs, and simplifies
authentication since no external Hugging Face tokens are required.

Package the scorer code (`XGBoostForecastAnomalyDetector` and `TheilSenCapacityTrendRUL`)
and the pinned artifacts directly with the backend service. Add `numpy`, `pandas`,
`scikit-learn`, `joblib`, and `xgboost` to the backend dependencies. The scorer
returns the versioned response documented below; the Android app calls only the
backend API routes.

Deploy the current working branch `chore/remove-nissan-leaf-workflow` on Render.
Because Render free instances can sleep after 15 minutes of inactivity, the mobile
app and web client should handle a short initial wake-up delay gracefully.

### 1. Prepare and deploy the API on Render

Create a Render Web Service from this repository with `backend/` as its root
directory. Render supports deploying FastAPI as a Python web service. Use the
commands below as a starting point and confirm them against the current backend
dependency and migration setup before the first deployment:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Create a Render PostgreSQL database in the same region as the API and configure
`DATABASE_URL` from its internal connection URL. The backend currently accepts
`postgresql://` and `postgresql+psycopg2://`; if Render supplies a `postgres://`
URL, convert only the scheme to `postgresql+psycopg2://` before setting it. Use
the internal URL for a Render-hosted API and database in the same region.

Set these backend environment values in Render, never in Git:

- `DATABASE_URL` — private database connection string.
- `FIREBASE_PROJECT_ID` — the Firebase project used by the Android app.
- `GOOGLE_APPLICATION_CREDENTIALS` — path to the Firebase Admin service-account
  secret file mounted by Render. Grant that service account only the Firebase
  Auth user-read permissions required by the API.
- `CORS_ORIGINS` — the exact production Vercel origin(s) if browser clients call
  the API. Native Android requests do not use browser CORS.
- `MODEL_REPOSITORY_DIR` — path to the directory containing model artifacts
  (`kit_xgb_forecast.joblib` and `oxford_rul_theilsen.joblib`) if custom path
  is used (defaults to `app/ml/artifacts`).

Run `alembic upgrade head` against the production database as a release/migration
step before directing app traffic to the API. Check `/health` for process
liveness, then make authenticated profile and vehicle requests to confirm Firebase
and database connectivity. `/health` alone does not check those dependencies.

Render documents [FastAPI web service deployment](https://render.com/docs/deploy-fastapi),
[environment variables and secret files](https://render.com/docs/configure-environment-variables),
and [PostgreSQL connection URLs](https://render.com/docs/postgresql-creating-connecting).
Keep the API and database in the same region and use their private connection
where available. Confirm current service and database pricing before provisioning.

### 2. Deploy machine learning models on Render

The machine learning models are deployed and served directly on Render alongside
the FastAPI backend. The current KIT model is a custom XGBoost forecaster with
residual calibration, and the Oxford model is a Theil–Sen capacity trend
estimator. Both artifacts are compact (~3.5 MB total) and load directly into
memory when the Render service starts.

#### Model serving architecture on Render:

1. **Artifact packaging**:
   The model files `kit_xgb_forecast.joblib` and `oxford_rul_theilsen.joblib`
   and their estimator code (`XGBoostForecastAnomalyDetector` and
   `TheilSenCapacityTrendRUL`) are packaged inside the backend service under
   `backend/app/ml/` (or referenced via `MODEL_REPOSITORY_DIR`).

2. **Lifespan loading**:
   FastAPI's `@asynccontextmanager` `lifespan` hook loads the `.joblib`
   artifacts once on service startup:
   - Verifies that artifact files exist and match the expected class types.
   - Stores the loaded model instances in `app.state.kit_model` and
     `app.state.oxford_model`.
   - `/health` verifies that models are loaded and ready in memory.

3. **Inference endpoints**:
   The backend exposes the versioned inference routes directly on Render:
   - `POST /v1/score/kit-window-pair` — accepts 30 KIT summary features from
     the current 10-second window and 10 actual medians from the following
     window; calculates residuals, normalizes by scale, and evaluates novelty
     against the calibrated threshold.
   - `POST /v1/estimate/oxford-rul` — accepts battery characterization cycle
     observations and caller EOL threshold; fits Theil-Sen regression and returns
     remaining useful life cycle estimates.

4. **Resource and performance profile on Render**:
   - Model memory footprint: ~150 MB RAM in the Python process.
   - Inference latency: <15 ms per window pair evaluation (no outbound HTTP calls).
   - Render Web Service RAM limit: 512 MB on free tier (sufficient for FastAPI +
     PostgreSQL connection + XGBoost/scikit-learn inference).

### 3. Connect model inference to the backend

Implement the model connection directly in `backend/`; the mobile app calls
only the authenticated backend API on Render. The backend uses an in-process
scorer (`LocalNoveltyScorer` / `InferenceService`):

- `LocalNoveltyScorer` loads the pinned `joblib` artifacts once when the FastAPI
  process starts on Render. All inference executes in-process with minimal latency.
- No third-party model inference hosting or tokens are required.

Add the scorer through FastAPI's lifespan/dependency setup and include the
prediction router in `backend/app/main.py`. Keep existing Firebase authentication
and vehicle-owner checks in front of telemetry and prediction routes.

Suggested request flow:

1. A signed-in app or replay client sends timestamped KIT readings to an
   authenticated backend telemetry route for a vehicle/replay session.
2. The backend validates timestamp ordering and signal names/types, then groups
   readings using the same 10-second window rules as KIT preprocessing.
3. When a window closes, the backend creates its 30 summary features and retains
   that window until the following window is complete.
4. The backend pairs current-window features with the next window's 10 actual
   medians, then calls the scorer. This preserves the trained model's input and
   scoring contract; it cannot produce the score before the next window arrives.
5. The scorer returns the numeric novelty score, calibrated threshold,
   `is_novel`, model/version identifier, and per-signal normalized errors. The
   backend validates the response and sends it to the mobile app.

Use a versioned JSON contract between the backend and model service, for example
`POST /v1/score/kit-window-pair`. Its request should contain `schema_version`,
`model_version`, `current_window_features` (all 30 named summaries), and
`next_window_medians` (the 10 targets). Its response should contain
`anomaly_score`, `threshold`, `is_novel`, `normalized_signal_errors`, and an
explicit `assessment_type: "novelty"`. Reject unknown schema/model versions,
missing fields, non-finite numbers, and mismatched feature order. Set a request
timeout and return a clear temporary-unavailable response if the model endpoint
is down; do not silently mark that window normal.

The mobile should display this as an **unexpected-pattern score**, not a fault
diagnosis. Include a clear state for “waiting for next window” and an error state
for unavailable inference. Do not turn the score into a health score or fault
probability without a separately validated method and labeled evaluation data.

The Oxford RUL prototype needs a separate backend contract and route because its
inputs are battery cycle/capacity history, not KIT OBD windows. Keep its scorer,
request schema, replay data, result status, and UI distinct; label its result
experimental. Do not pass KIT telemetry to the Oxford model.

### 4. Add recorded-data replay

Do not copy entire research datasets into the mobile app or production database.
Keep the licensed source data and provenance in the repository's documented data
locations. Build a replay tool that reads a selected recording and sends events
to the API at a configurable rate, preserving their order and timing. Mark every
response and screen as **Recorded data replay** or **Simulated live data**.

#### Mobile demo flow

Add a dedicated **Demo / Replay** entry in the mobile app, separate from the
normal active-vehicle and Insights flows. The user should be able to choose a
dataset and sample recording, start/pause/resume/stop the replay, and select a
playback speed. Show the source recording date, dataset name, current replay
time, and an always-visible **Recorded data replay** label. Do not present these
values as measurements from the user's saved vehicle.

For the first demo, keep a short, attributed KIT sample on the backend and let
the app control a replay session. This avoids bundling the full research dataset
into the APK. A session API could look like:

- `POST /api/v1/demo/replays` — select `dataset: "kit_obd"`, an allowed
  `recording_id`, and playback speed; return a user-scoped `session_id`.
- `POST /api/v1/demo/replays/{session_id}/control` — pause, resume, or stop.
- `GET /api/v1/demo/replays/{session_id}/events?after={cursor}` — return the
  latest replayed sensor values and any completed model assessment.

The backend replay worker reads the recording in timestamp order and sends
readings through the same telemetry-window and model-scoring services used by
the authenticated inference API. The mobile app polls the session event route at
a modest interval (or uses a streaming connection later), updates the telemetry
display with each returned event, and displays a score when its window pair has
been processed. Polling is sufficient for the first demo and easier to resume
after a mobile network interruption.

Tie every session to the authenticated Firebase UID, validate the selected
recording against an allowlist, cap session duration and playback speed, and
prevent one user from reading or controlling another user's session. Keep replay
state temporary for the demo unless persistent history is explicitly designed.
Use an idempotent cursor so retrying a poll does not duplicate chart points or
assessments. If inference is unavailable, continue to show incoming
replay telemetry with an explicit inference-unavailable state; never substitute
a normal score.

The demo should show the selected sensor values changing over time, the replay
clock and playback controls, a waiting state while the next 10-second window
arrives, and then the novelty score with its threshold and `is_novel` result.
Explain in the UI that a novelty flag means an unexpected pattern, not a
confirmed vehicle fault. Do not attach replay scores to the user's real Garage
vehicle or save them as real vehicle history.

The KIT replay should send timestamped OBD readings. The backend must group them
into the same 10-second windows used by preprocessing. The forecasting novelty
score is available only after the following window arrives, because the score
compares the forecast with that window's actual readings.

Oxford battery-cycle data has different inputs from KIT OBD telemetry. If the
RUL prototype is demonstrated, give it a separate battery-data replay route and
screen. The same demo controls may be reused, but the selected data, API schema,
model service, chart labels, and result card must identify Oxford battery
capacity/cycle data; do not imply those measurements came from the KIT vehicle.
The Oxford model is experimental and must be labeled as such.

KIT has no verified mechanical-fault labels. A novelty score is not a fault
probability or diagnosis. The replay demonstrates data transport, inference, and
UI behavior only; it does not validate live-vehicle accuracy.

### 5. Connect and distribute the Android app

Set `EXPO_PUBLIC_API_URL` to the HTTPS Render API URL in the production Expo
build environment. Verify that Firebase uses the same project configured on the
backend. Build a release APK after setting the production API URL, then install
and exercise it on a test device. Expo public environment values are bundled into
the client build; changing the API URL requires creating a new APK.

For a demo, distribute the signed APK privately to testers and provide the
recorded-data replay instructions. For public Play Store distribution, prepare a
production signing key, privacy disclosures, store listing, and release process
separately. Do not commit signing keys or service credentials.

### 6. Keep the web app on Vercel

Continue deploying the Next.js frontend to Vercel. Set its server-side API base
URL to the Render API URL. If browser code calls the API directly, add the exact
Vercel production origin to the backend CORS allowlist. Vercel preview deployments
are already described in `.github/workflows/vercel-ci.yml`; production environment
variables and domain settings still need verification.

## Release checks

Before inviting users to the demo, confirm:

- The Render API is reachable over HTTPS and protected endpoints reject invalid
  Firebase tokens.
- Database migrations ran successfully and account/vehicle data persists across
  API restarts.
- Both model artifacts (`kit_xgb_forecast.joblib` and `oxford_rul_theilsen.joblib`)
  load cleanly during Render startup and `/health` confirms `models: loaded`.
- Model inputs are validated and responses identify the model/version and replay
  status.
- The model scorer handles malformed requests with clear 422 errors and reports
  failures as unavailable rather than normal.
- Replay sessions keep each recording isolated and never combine KIT OBD and
  Oxford battery examples.
- KIT and Oxford replays use their separate data contracts and are labeled as
  recorded experiments.
- The APK uses the deployed API URL and can sign in, call the API, and display
  replay results on a clean device.
- Error logging excludes Firebase service account credentials, tokens, and personal data.
- Render and database service budgets and usage limits are reviewed.

## Current limitations

The mobile app's generic Insights currently uses illustrative fixtures. The
backend does not yet expose a connected telemetry-to-model inference flow, and
the models are not validated fault diagnoses or dependable vehicle-life
predictions. Complete the replay API and UI integration before presenting the
deployment as a working model demonstration.
