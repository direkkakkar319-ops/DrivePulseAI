# DrivePulseAI Hugging Face Inference Endpoint

This folder contains the **custom inference container build context** for a
Hugging Face Inference Endpoint. The KIT fitted artifact and Oxford estimator
configuration are stored under `model_repository/` and are uploaded to the
Hugging Face model repo. For each Oxford request, the estimator fits a trend to
the supplied capacity history; its `.joblib` stores configuration, not learned
weights.

This is not a Docker Space. Build the image from this folder and push it to a
container registry that Hugging Face Inference Endpoints can access. Select the
model repo and custom container image when creating the Endpoint.

## Endpoints

- `GET /health` reports whether both model interfaces loaded.
- `POST /v1/score/kit-window-pair` scores one adjacent pair of prepared KIT
  windows. Send the current window's 30 summaries and the next window's 10
  actual medians. It returns the scale-normalized novelty score, calibrated
  threshold, `is_novel`, and per-signal errors. It cannot score until the next
  window exists.
- `POST /v1/estimate/oxford-rul` estimates cycles to the supplied 75%-capacity
  threshold using the existing Theil–Sen capacity trend estimator.

Configure the Endpoint as **Protected/Authenticated**. The backend calls its
URL with a Hugging Face token stored only as a backend secret. Do not place the
token in the container image, model repository, or Android APK.

## Model status and limits

The KIT artifact is a fitted XGBoost/persistence next-window forecaster with
stored residual scales and a training-calibrated 99th-percentile novelty
threshold. KIT has no verified fault labels. A novelty flag is not a fault
diagnosis or fault probability.

The Oxford endpoint loads a `.joblib` configuration for the project's
Theil–Sen trend baseline, then fits the trend per request. It is not a model
trained once on pooled Oxford rows. Its 75%-capacity first-crossing target is
ambiguous and supported by only two cells. Results are experimental RUL
estimates, not dependable battery-life predictions.

Use these endpoints for recorded-data replay demonstrations, clearly labeled
as such. Do not present their output as validated production predictions.

## Hugging Face setup

1. Create a model repository, for example `direkKakkar/DrivePulseAI`.
2. Upload all three files from `model_repository/`—`README.md`,
   `kit_xgb_forecast.joblib`, and `oxford_rul_theilsen.joblib`—to the model
   repository root. The container expects both artifacts under `/repository/`.
3. Build and push the custom container image from this folder, for example:

   ```bash
   docker build --platform linux/amd64 -t YOUR_REGISTRY/drivepulseai-inference:v1 .
   docker push YOUR_REGISTRY/drivepulseai-inference:v1
   ```

4. In the Inference Endpoints dashboard, deploy the model repository with the
   custom container image. Set container port `8000` and choose protected access.
5. Put the Endpoint URL and a Hugging Face token with endpoint-call permission
   into the Render backend's secrets. Keep the token out of this folder and the
   APK.

The Docker image contains only the serving code and runtime dependencies; both
model artifacts are mounted from the selected model repository at `/repository`.
The endpoint is dedicated compute and is billed while running; review the
[current pricing](https://huggingface.co/docs/inference-endpoints/pricing) and
pause/delete it when it is not needed.

The artifact is a trusted `joblib` pickle and must only be loaded from this
project's checked-in package. Do not replace it with an untrusted upload.

## Local run

```bash
cd ml/hf_deployment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
MODEL_REPOSITORY_DIR=./model_repository uvicorn app:app --host 0.0.0.0 --port 8000
```

## Rebuild the Oxford estimator artifact

From this directory, with the pinned dependencies installed, run:

```bash
python build_oxford_rul_artifact.py
```

This serializes the default estimator configuration. It does not train or
validate an Oxford RUL model.

## Request shapes

KIT request: `schema_version` must be `1`; `current_window_features` must
contain exactly the 30 named fields used by the training artifact, and
`next_window_medians` must contain exactly its 10 target fields. Their names
and order are validated against the loaded artifact.

Oxford request: `schema_version` must be `1`; send `as_of_cycle`,
`eol_threshold_capacity_mah`, and at least four `observations`, each with
`characterization_cycle` and `capacity_1c_discharge_mah`. The caller must use the
same target convention as the Oxford preprocessing/audit and must not describe
the unconfirmed first crossing as a confirmed end-of-life label.
