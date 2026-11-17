# Deployment plan

This document describes the planned deployment for the current DrivePulseAI
prototype. It is a plan, not a record of services already deployed. The web app
has Vercel preview deployment automation; the API, model service, cloud database,
and production APK pipeline still need to be configured.

## Proposed layout

```text
Web browser ───────────────> Next.js web app on Vercel

Android APK ── Firebase ID token ──> FastAPI on Render
                                         ├──> Render PostgreSQL
                                         └──> Hugging Face model endpoint

Recorded KIT/Oxford data ── replay tool ──> FastAPI/model API ──> Android app
```

The mobile app should call only the DrivePulseAI API. It must not contain the
Hugging Face token or database credentials. The backend verifies Firebase
identity, validates the request, then calls the model service using a server-side
secret.

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

## Free demo deployment decision

For the current demo, deploy one free Render Web Service that runs both the
FastAPI API and the local KIT/Oxford scorer. Do not create a paid Hugging Face
Inference Endpoint or a separate model service. The mobile app calls only the
Render API; FastAPI verifies Firebase identity, validates the request, and loads
the pinned model artifacts once at startup.

The Hugging Face repository `direkKakkar/DrivePulseAI` remains an artifact
registry only. The deployed backend must package the matching scorer code and
the pinned `kit_xgb_forecast.joblib` and `oxford_rul_theilsen.joblib` artifacts,
or download a fixed Hub revision during the Render build. Do not include raw
research datasets. Record both the application Git SHA and the model revision.

Before provisioning Render, implement `LocalNoveltyScorer` in `backend/` and
wire it through FastAPI's lifespan/dependency setup. Add `numpy`, `pandas`,
`scikit-learn`, `joblib`, and `xgboost` to the backend's production
dependencies. The scorer must return the versioned response documented below;
the Android app must not call a model service directly.

Render should deploy this branch from a root directory that includes both the
backend and packaged model files. If `backend/` remains the Render root, first
move or package the scorer code and artifacts below that directory. Do not
create a second Render service for inference. The free service can sleep after
idle time, so the mobile demo must show a temporary wake-up/unavailable state.

The Hugging Face Endpoint and custom-container instructions below are a paid
alternative only. They are not part of the free demo rollout.

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
- `HF_ENDPOINT_URL` and `HF_TOKEN` — add when the Hugging Face model endpoint is
  deployed. Store the token as a Render secret.

Run `alembic upgrade head` against the production database as a release/migration
step before directing app traffic to the API. Check `/health` for process
liveness, then make authenticated profile and vehicle requests to confirm Firebase
and database connectivity. `/health` alone does not check those dependencies.

Render documents [FastAPI web service deployment](https://render.com/docs/deploy-fastapi),
[environment variables and secret files](https://render.com/docs/configure-environment-variables),
and [PostgreSQL connection URLs](https://render.com/docs/postgresql-creating-connecting).
Keep the API and database in the same region and use their private connection
where available. Confirm current service and database pricing before provisioning.

### 2. Paid alternative: deploy model inference on Hugging Face

The current KIT model is a custom XGBoost forecaster with residual calibration;
it is not a standard text or image inference model. If hosted on Hugging Face,
use an Inference Endpoint with a custom container that loads a pinned model
artifact and exposes a small, versioned JSON request/response API. Keep the
endpoint protected and let only the Render backend call it using `HF_TOKEN`.

The model repository `direkKakkar/DrivePulseAI` has been uploaded with the KIT
and Oxford `.joblib` files and model card. The current custom Inference Endpoint
container build context is under
[`ml/hf_deployment/`](ml/hf_deployment/). It contains the serving API, Oxford
Theil–Sen estimator code, version-pinned dependencies, and Dockerfile. The
Oxford `.joblib` stores its algorithm configuration; Oxford capacity history is
still fit per request. Do not upload the whole ML workspace or raw research
datasets as part of model serving.

Complete the Endpoint setup in this order:

1. Build the container from `ml/hf_deployment/` for `linux/amd64`, then push it
   to a registry Hugging Face can access (for example Docker Hub, GHCR, ECR,
   ACR, or GCR):

   ```bash
   docker build --platform linux/amd64 \
     -t YOUR_REGISTRY/drivepulseai-inference:v1 ml/hf_deployment
   docker push YOUR_REGISTRY/drivepulseai-inference:v1
   ```

2. In the Hugging Face Inference Endpoints dashboard, select model
   `direkKakkar/DrivePulseAI`, choose the custom container image you pushed, set
   its port to `8000`, and enable **Protected/Authenticated** access.
3. Wait until the Endpoint is **Running**, then copy its base URL. The model
   routes are `/v1/score/kit-window-pair` and `/v1/estimate/oxford-rul`.
4. Add `HF_ENDPOINT_URL` and an endpoint-call `HF_TOKEN` to the Render backend's
   secrets. The backend calls the Hugging Face URL with the token; the mobile
   app calls only the backend. Never include `HF_TOKEN` in the APK.
5. Send one authenticated request to each model route from the backend or a
   secure admin client and confirm the response includes its model version and
   expected experimental/novelty status before enabling the mobile replay UI.

Hugging Face Inference Endpoints use dedicated compute billed while the endpoint
is running. Review [current Endpoint pricing](https://huggingface.co/docs/inference-endpoints/pricing)
before deployment; using model hosting does not make inference compute free.
Pause or delete the Endpoint when the replay demo is not in use.

Before deploying, define and version the exact feature names, order, types,
window duration, missing-value rules, model artifact, residual scales, and
calibrated threshold. Reject incompatible or non-finite inputs. Load the model
once when the inference process starts rather than once per request.

Hugging Face documents [custom containers](https://huggingface.co/docs/inference-endpoints/engines/custom_container)
and [endpoint security](https://huggingface.co/docs/inference-endpoints/security).

### 3. Connect local model inference to the backend

Implement the model connection in `backend/`; the mobile app must never call
Hugging Face directly. Keep a backend interface such as `NoveltyScorer` with two
possible implementations:

- `LocalNoveltyScorer` loads the pinned `joblib` artifact once when the FastAPI
  process starts. Use this first for a small demo if the artifact and dependencies
  fit the Render service.
- `HuggingFaceNoveltyScorer` sends the same versioned request to the protected
  Hugging Face endpoint using `HF_ENDPOINT_URL` and `HF_TOKEN`. Use this when
  model serving is separated from the API.

Both implementations must return the same backend response shape so switching
the serving location does not require mobile UI changes. Add the scorer through
FastAPI's lifespan/dependency setup and include the prediction router in
`backend/app/main.py`. Keep existing Firebase authentication and vehicle-owner
checks in front of telemetry and prediction routes.

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
assessments. If the model endpoint is unavailable, continue to show incoming
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
- Hugging Face credentials exist only in Render secrets, if that service is used.
- Model inputs are validated and responses identify the model/version and replay
  status.
- The model adapter works against a fixed sample request, validates malformed
  responses, and reports endpoint timeouts as unavailable rather than normal.
- Replay sessions keep each recording isolated and never combine KIT OBD and
  Oxford battery examples.
- KIT and Oxford replays use their separate data contracts and are labeled as
  recorded experiments.
- The APK uses the deployed API URL and can sign in, call the API, and display
  replay results on a clean device.
- Error logging excludes Firebase tokens, Hugging Face tokens, and personal data.
- Render, database, and inference service budgets and usage limits are reviewed.

## Current limitations

The mobile app's generic Insights currently uses illustrative fixtures. The
backend does not yet expose a connected telemetry-to-model inference flow, and
the models are not validated fault diagnoses or dependable vehicle-life
predictions. Complete the replay API and UI integration before presenting the
deployment as a working model demonstration.
