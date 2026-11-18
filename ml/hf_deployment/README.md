# Nissan Leaf battery model service

This Docker build context serves the Nissan Leaf anomaly, RUL, and battery
health scoring logic. The previous KIT/Oxford serving bundle and its artifacts
are archived under `older_models/`. The service uses the Nissan Leaf 2018
publisher-preprocessed telemetry. This represents one vehicle and has no
verified fault labels; its anomaly output identifies unusual telemetry, not
confirmed faults.

## Runtime configuration

| Variable | Behavior |
| --- | --- |
| `ML_INFERENCE_API_KEY` | Inference requires a secret of at least 32 UTF-8 bytes with no surrounding whitespace. |
| `MODEL_REPOSITORY_DIR` | Defaults to `model_repository/` beside `app.py`; Docker sets `/app/model_repository`. |
| `PORT` | Render listening port; Docker defaults to 8000. |

Inference uses `X-ML-API-Key`. Missing or invalid caller credentials return 401;
missing/invalid server configuration disables inference with 503. `/health` is
public and reports whether the anomaly artifact and model logic loaded.

## Routes

All three inference routes require the shared API key and `schema_version: 1`.

### `POST /v1/score/nissan-leaf-anomaly`

Accepts `observations`, a list of 1–256 objects with `HV_Bat_Voltage`,
`Pack_1_C_Temp`, and `SOC`. Results include an Isolation Forest score and
`is_unusual`, based on the fixed 0.5th-percentile training threshold. Scores
are not probabilities or fault diagnoses.

### `POST /v1/estimate/nissan-leaf-rul`

Accepts 1–10,000 observations with `Timestamp` (Unix microseconds), `Odometer`,
and `SOH`; `Pack_Avg_C_Temp`, `SOC`, and `HV_Bat_Voltage` are optional context.
`eol_threshold_soh_pct` defaults to 80. The robust Theil–Sen trend estimates
kilometers until the reported SOH reaches that threshold. Context features are
summarized but do not change the SOH slope. This is not remaining driving range
on the current charge. The threshold projection is experimental and is not
validated for unseen vehicles.

### `POST /v1/score/nissan-leaf-health`

Accepts `SOH` from 0 to 100 and returns the project's transparent 1–5 SOH band
score. It is a rule-based score, not a separately trained estimator.

## Artifact and deployment notes

`model_repository/nissan_leaf_anomaly.joblib` is a trusted, fitted Isolation
Forest artifact trained with the chronological Nissan Leaf data split. The
Docker image copies only the serving package and this model artifact; it does
not include the source CSV. Never load untrusted joblib files.

The existing backend still sends KIT window-pair requests. Those calls are
incompatible with this Nissan Leaf service until the backend's telemetry input
flow and request contract are updated. Deploying this service switch before
that backend change will make the existing KIT analysis flow fail, as intended
for this interim model replacement.
