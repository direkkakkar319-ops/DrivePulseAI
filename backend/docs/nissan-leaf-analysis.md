# Nissan Leaf analysis — leaf-csv-v1

This replaces the active KIT analysis contract. The URL paths are retained, but
`analysis_type=nissan_leaf_telemetry` explicitly identifies the new response.
Old KIT clients must not parse this contract. Historical KIT modules/tests are
retained; asset-dependent/obsolete backend suites carry explicit retirement skips.

## Authenticated endpoints

- `GET /api/v1/analysis/samples`: catalog with synthetic/provenance labels.
- `POST /api/v1/analysis/samples/{id}/analyze`: analyze the allowlisted fixture.
- `POST /api/v1/analysis/upload`: multipart with **exactly one `file`**.

All require the existing verified Firebase bearer identity. No `recording_date`,
vehicle ID parameter, model key or KIT window-pair fields are accepted. Mobile
only calls the main backend. The backend holds `X-ML-API-Key` privately.

```bash
curl -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
  -F 'file=@backend/docs/examples/leaf-csv-v1-synthetic.csv;type=text/csv' \
  http://localhost:8000/api/v1/analysis/upload
```

The example is **synthetic integration input**, not real telemetry, scientific
validation, or precomputed model output. Its predictions are computed at request
time. Never store credentials in command scripts or documentation.

## CSV input

UTF-8 (optional BOM), comma-delimited, exact case-sensitive column names. Numeric
measurements may use decimal/scientific notation. Empty cells are missing.
Unknown/duplicate columns and wrong row widths are rejected. This is a selected
Leaf schema, **not** a full publisher CSV or arbitrary OBD/EV CSV importer.

| Capability | Required fields | Units / requirements |
| --- | --- | --- |
| Every accepted row | `Timestamp` | Integral Unix **microseconds**, UTC epoch, from 2000 inclusive to 2100 exclusive; seconds, milliseconds and textual dates rejected |
| Anomaly | `HV_Bat_Voltage`, `Pack_1_C_Temp`, `SOC`, `HV_Bat_Current_2`, `Pack_2_C_Temp`, `Pack_4_C_Temp` | Exact order shown; V, °C, %, A, °C, °C respectively; voltage `(0,500]`, SOC `[0,100]`, all finite |
| Health | `SOH` | Reported %, `[0,100]`; latest valid value by timestamp, last source row breaks timestamp ties |
| RUL | `Timestamp`, `Odometer`, `SOH` | km, %; daily medians, at least 30 observed days spanning 90 days, at least 30 distinct daily odometers; decline needed for ordinary projection |
| Optional telemetry | `Speed`, `Instant_kW`, `kWh_Remaining`, `Pack_Avg_C_Temp` | Speed original unit unverified, kW source-derived, kWh semantics unverified; supplied average temperature in °C is also RUL context |
| Optional single-vehicle marker | `Vehicle_ID` | Must be populated and identical throughout; a user assertion, not authenticated vehicle identification |

`Timestamp` and at least one supported signal column are required. Other columns
are capability-specific: a SOC-only file can display telemetry without anomaly,
health or RUL. No SOH is inferred from SOC. Units follow the existing implementation;
the original workbook is absent locally. Current polarity and optional energy
semantics are unresolved. The service does not guess units or apply an old raw
research scaler. Magnitudes above finite float32 representability are invalid
numerical input, not asserted physical limits. Temperature sentinel codes are not
silently reinterpreted as missing by this version; callers must provide validated
measurements or blank cells.

Synthetic example (not vehicle observations):

```csv
Timestamp,SOC,SOH,HV_Bat_Voltage,HV_Bat_Current_2,Pack_1_C_Temp,Pack_2_C_Temp,Pack_4_C_Temp,Odometer
1704067200000000,70,94,360,10,25,25,25,20000
1704326400000000,70,93.98,360,10,25,25,25,20090
```

Original data-row numbers (1-based, excluding header) are retained as `row_id`.
Invalid timestamps skip the whole row. Invalid/missing measurements become null,
are counted/reported and exclude that row only from affected model inputs. They
are never filled with zero. If no timestamp-valid measurements remain, reject the
file. Issues are summarized with the first 20 details; total counts remain exact.
Source order, duplicate timestamps and backward clocks are retained and warned.
Charts break at nonincreasing timestamps, skipped rows, missing values or gaps over
one second (a display discontinuity policy, not a model sampling assumption).

Only one vehicle per CSV is supported. Mixed populated `Vehicle_ID` values are
rejected. Without a stable identifier, mixed-vehicle data cannot be detected;
format acceptance does not verify vehicle make, identity or ownership. There is
no automatic Garage association.

## Shared processing / inference

Both sample and upload use the same bounded parser and orchestrator. Anomaly input
is raw numerical model features, independently scored, no resampling/scaling or
10-second windows. Complete valid inputs are sent sequentially in bounded batches;
returned count, order mapping, model version, threshold consistency, novelty rule
and SHAP structure are validated. A failed anomaly batch discards that capability's
entire partial result; health/RUL can still complete. SHAP failures return a failed
anomaly capability, never invented explanations.

RUL is prepared over **all accepted rows**: UTC daily median SOH/odometer and daily
context means, preserving the estimator's existing aggregation. No arbitrary first
or last 10,000 rows are substituted for history. Daily odometer decreases disable
RUL. The estimator then uses its own 365-day lookback, 30-day/90-calendar-day checks,
Theil–Sen trend and status logic. The RUL current SOH is the latest daily median, whereas the battery overview and
health endpoint use the latest valid individual SOH reading; these may differ.
No trained RUL artifact is loaded in the backend.

## Response / Android contract

See `app/schemas/leaf_analysis.py` for the exact versioned response and
`mobile/src/types/leaf-analysis.ts` plus its runtime validator for the consumer.

- `schema_version: 1`, `analysis_type: nissan_leaf_telemetry`, `persisted: false`.
- `source_type`: `built_in_sample` or `uploaded_csv`; source provenance and synthetic
  label are not copied from the sample onto an upload.
- `recording`: input/accepted/skipped counts, cell issues, start/end Unix microsecond
  timestamps and unverified vehicle-compatibility metadata.
- `battery`: latest valid SOC/SOH and their timestamps; `estimated_range_km: null`,
  `range_status: unavailable`, explanatory reason. No verified usable battery energy
  and defensible consumption estimate exist in this input contract. Even supplied
  `kWh_Remaining` does not establish a reliable consumption rate. No fixed efficiency
  or nominal-capacity assumption is used.
- `anomaly`: availability, six-feature model version, threshold,
  `score_direction: lower_is_more_unusual`, counts/percentage, original row IDs,
  timestamps, actual scores/flags, conditional SHAP. Strict `<` threshold rule.
- `health`, `rul`: `status`, safe `reason`, actual validated upstream `result` when
  available. Availability: completed, unavailable, insufficient_history or failed.
  Inspect the RUL result's own status too: ok, threshold_reached,
  insufficient_history, insufficient_odometer_variation, non_declining_trend,
  no_valid_history. Missing fields remain missing, not numerical zero.
- `telemetry`: retained observations, original row identity/time, nullable measured
  values. `units`, warnings and model limitations accompany them.

SHAP returns baseline and top three absolute score contributions only. Negative
contributions lower the score toward unusual; positive ones raise it. Zero is
neutral although the upstream direction string says toward_typical. They are not
causal fault diagnoses or a complete six-feature additive waterfall.

Health bands: >=95 → 5; >=90 → 4; >=85 → 3; >=80 → 2; below80 → 1. This is a
rule applied to supplied SOH, not a trained prediction. RUL estimates distance to
a project SOH threshold, not charge range. Neither is validated fleet diagnostics.

## Limits, errors and privacy

Defaults: 2 MiB CSV, 256 source rows, 128 characters per field, fixed supported
columns, 32 anomaly observations per batch (maximum 256), two concurrent analyses
and 120 seconds for the full request. Multipart envelope has 64 KiB bounded
overhead. There is no unbounded file read, model retry loop or inference concurrency.
Requests exceeding the input limits are rejected, never silently truncated.

- 401 missing/invalid identity; 403 unverified email.
- 404 unknown sample; 415 unsupported encoding/body format; 422 invalid CSV/form.
- 413 bytes/rows exceeded; 429 analysis capacity busy; 504 whole-request deadline.
- 503 packaged asset missing/corrupt; generic 500 unexpected processing failure.
- Upstream errors become explicit per-capability failed states in a 200 structured
  analysis response; **200 does not mean every capability succeeded**. No partial
  anomaly scores are exposed after batch failure.

Authenticated analysis responses use `Cache-Control: no-store`. Uploads are parsed
from bounded memory without spooled or permanent files. No telemetry/results are
written to PostgreSQL or persistent mobile state. Filename is never a server path.
Exceptions do not expose upstream bodies, filesystem paths or credentials.

## Configuration / local verification / rollout

Main backend: `ML_SERVICE_URL` (HTTPS), `ML_INFERENCE_API_KEY`,
`ML_REQUEST_TIMEOUT_SECONDS` (30 default), `LEAF_ML_BATCH_SIZE` (32 default),
`LEAF_UPLOAD_MAX_BYTES` (2097152), `LEAF_UPLOAD_MAX_ROWS` (256),
`LEAF_ANALYSIS_TIMEOUT_SECONDS` (120). `LEAF_ANALYSIS_MAX_CONCURRENT` controls
the admission semaphore (2 default); KIT workload options are legacy.
ML service: matching private `ML_INFERENCE_API_KEY`, `MODEL_REPOSITORY_DIR`, `PORT`.
No new dependency is needed. Backend never loads model artifacts.

Backend tests: from `backend/`, use the existing Python environment's `pytest tests`.
Real model integration is optional when ML dependencies are absent and explicitly
skipped. With both existing environments available, from repository root:

```bash
PYTHONPATH=backend:.:backend/.venv/lib/python3.12/site-packages \
  PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/drivepulse-numba \
  .venv/bin/pytest backend/tests/test_leaf_analysis.py -q -s
.venv/bin/pytest ml/tests -q
cd mobile
npx tsc --noEmit
npm run lint
npm test -- --runInBand
```

The additional Python path above is an explicit local verification bridge between
already installed environments, not a production dependency recommendation.
Serving pins scikit-learn1.7.2, matching the artifact. The local research environment
uses1.9.0 and emits persistence warnings; pinned-container inference still needs
verification. No dependency was installed or model retrained for this integration.

Measured local synthetic integration: 40 rows, 40 genuine anomaly scores, zero
flagged; both workflows equal. Separate 32-row deliberately unusual synthetic
SHAP stress workload took ~13.7s in the local mixed-version environment. This is
not fault-detection evaluation or Render performance. Default256 rows may still
exceed deadlines on SHAP-heavy/cold services; reduce inputs/limits and measure the
actual deployment before increasing capacity. Deadline failure is honest failure,
not permission to return partial scores.

Deploy only after review: verify ML current Nissan routes and pinned environment,
configure matching server-only keys, then deploy main backend, verify Firebase and
TLS with test data, and only then ship the matching mobile client. Retire existing
KIT callers deliberately. Repository files cannot prove live Render settings.
No deployment, build or production request was performed in this task.

Android: native Firebase and DocumentPicker require a compatible installed client.
Run the existing dev-client workflow; select the synthetic fixture, then the same
CSV; compare scores and statuses. Verify file cancellation, errors, Retry, logout,
account switching, graphs, missing-data and RUL states. Native module availability,
physical-device behavior and live Render behavior remain pending.

## Local verification record

Step 4 verification: 88 backend tests passed; 255 skipped (206 explicitly retired
KIT tests and 49 PostgreSQL tests without a dedicated TEST_DATABASE_URL). 35 ML
tests passed. Mobile: 477 tests across32 suites; TypeScript and configured Expo lint
passed. Changed Python Ruff checks and formatting passed. Full backend Ruff still
reports the pre-existing DTZ007 in inactive `kit_preprocessing.py:16`; it was not
changed to disguise that issue. Model and packaged sample checksums were verified.
Real local main-backend → ML-app testing used the actual artifact with stubbed
Firebase verification and no database operations or production networking.
Physical Android, pinned serving-container execution and live Render remain pending.

## Reconciliation with partner ML update

The deployment branch was merged non-destructively with remote commit `9565dcb`.
Isolation Forest and SHAP remain the active anomaly path. The added ML endpoint
`POST /v1/score/nissan-leaf-trend-anomaly` and its rolling Z-score implementation
are preserved and tested. The follow-up trend integration below now connects
this independent detector through the shared backend pipeline and mobile results.
It does not replace point anomalies; unverified or missing signals remain unavailable.

The updated RUL service defaults to 100 bootstrap fits and an 80% interval. The
backend preserves optional `rul_km_p10`, `rul_km_p50`, `rul_km_p90`, corresponding
`estimated_days_to_threshold_p10/p50/p90`, and `confidence_interval` with
`level_pct`, distance bounds, `estimated_days_p10/p50/p90`, valid-fit count and
optional interpretation. Absent/null intervals remain valid for older compatible
responses and insufficient-history/failed bootstrap outcomes. Bounds must be
finite, nonnegative and ordered; duplicate flat/nested values must agree.

Mobile uses the declared interval level and lower/median/upper values, without
turning bootstrap uncertainty into fault probability. This is finite-sample
uncertainty under the estimator assumptions, not validated coverage on unseen
vehicles or protection against unobserved late-life acceleration. The upstream
field names p10/p90 reflect the default80% setting; retain the supplied level when
interpreting another level. Current backend callers leave the ML defaults intact.
Bootstrap fitting adds request-time CPU work and does not remove existing limits.

### CI deployment protection

`.github/workflows/ci.yml` previously allowed same-repository PRs to trigger both
Render deploy hooks. Deployment detection/triggers now require **push to main**,
service-path changes and successful existing prerequisite checks. Deploy refs and
verification commits use `github.sha`. Both verification jobs additionally require
the corresponding deployment-trigger job to have succeeded. PR and merge-group
validation jobs still run, but cannot invoke those deployment jobs.

`deploy-database.yml` allows main migration pushes/manual main runs, not PRs.
`render-health.yml` only checks deployment status/health; it does not deploy.
`vercel-ci.yml` can deploy frontend previews for matching frontend PR changes and
was deliberately left unchanged. Render Auto-Deploy, external hooks, branch
protection and manual approvals are external settings: repository changes cannot
verify or disable them. Confirm Render Auto-Deploy remains disabled before a
subsequent authorized push. Previously queued/running jobs use their old workflow
revision; this change does not cancel them. Manual Render deployment is untouched.

No push, workflow dispatch, PR merge, credential change or Render deployment was
performed during reconciliation. Tests in `test_deployment_workflow.py` guard the
PR/main-event conditions and verification dependencies.

### Reconciled verification record

After incorporating `9565dcb`: 99 backend tests passed, 255 skipped (206 retired
KIT cases; 49 unavailable PostgreSQL checks), and 40 ML tests passed, including
trend tests. Mobile:484 tests across32 suites passed; TypeScript and Expo lint
passed. Five deployment-workflow regression tests passed. All workflow YAML parsed;
ML lint and changed-file Python lint/format checks passed. Full backend Ruff still
reports five pre-existing issues in untouched files: DTZ007 in inactive
`app/services/kit_preprocessing.py` and import sorting in `migrations/env.py` and
migrations0001–0003. These are not claimed as passing CI checks.

A fresh real-artifact integration run returned identical sample/upload results,
including actual optional bootstrap intervals, 40 scores and zero unusual readings.
The two normal workflows together took~2.19s with default bootstrap enabled; sample
response18406bytes. A separate32-observation unusual synthetic SHAP batch took~11.74s.
These are local mixed-version measurements, not Render performance. The original
model/sample checksums and the remote RUL/trend algorithm ASTs were preserved.

The two project-authored CSV fixtures retain their original CRLF bytes. Scoped
`.gitattributes` entries disable text conversion and recognize CR at end of line;
this preserves checksums without suppressing other whitespace checks.

## Battery Trend Analysis integration

The current additive schema1 response includes `trend` independently of `anomaly`,
`health` and `rul`. Older responses without `trend` remain accepted by mobile.
The existing three main-backend routes and Firebase authorization are unchanged.

`services/leaf_trend.py` prepares the history from the same validated readings for
sample and CSV uploads. The existing server-only HTTP client sends one request to
`POST /v1/score/nissan-leaf-trend-anomaly` with `schema_version:1` and `observations`.
Do **not** split this history into point-anomaly batches: its rolling baseline
needs the complete accepted history. The current ML endpoint permits1–10000 rows;
the tighter backend256-row limit remains authoritative. No SOC, row ID, user ID,
Garage ID or Firebase token is sent in this model payload.

The input keeps original Unix-microsecond timestamps and supplied measured pack
temperatures, reported SOH and odometer. The ML implementation performs its own
UTC-day aggregation: means for temperatures, medians for SOH/odometer. The backend
never derives an average temperature from missing channels. `Pack_Avg_C_Temp` is
now explicitly accepted as an optional finite °C column (the earlier guide listed
it, but the parser allowlist had omitted it; a regression test covers this).

`Ambient_C_Temp` remains outside leaf-csv-v1 because its original units are
ambiguous. Consequently temperature-rise-over-ambient is explicitly unavailable,
not assumed zero and not silently converted from a guessed unit. A later explicit
ambient-unit contract is required. The other three signals can be supported by
supplied pack sensors, average temperature and SOH/odometer respectively.

A pack spread requires at least two measured pack channels on every supplied
trend day. If any such day lacks that coverage, all pack channels are excluded
from this detector request with a warning; the original telemetry and point
anomaly inputs remain untouched. This conservative policy prevents pandas'
missing-value-skipping max/min from presenting a single sensor's spread as a
measured zero. Available average-temperature and SOH-rate analyses still proceed.

### Response shape

`trend` contains:

- `status`: completed, insufficient_history, unavailable or failed; safe `reason`.
- `prepared_readings`, `analyzed_readings`, `skipped_readings`, `observed_days`.
  Prepared readings have usable trend input fields. Analyzed readings are counted
  only after a validated model response; failed/unrequested work is not counted.
- Source start/end timestamps, actual `source_fields`, `signal_availability` with
  per-signal input availability/reasons, backend warnings and limitations.
- `result`: the validated ML response or null; never fabricated normal output.

The actual model response includes version`nissan-leaf-rolling-zscore-v1`,
assessment`rolling_zscore_drift_detection`, status`ok`, `insufficient_history` or
`empty_input`, `is_drift_detected`, `drift_alerts_count`, `alerts` and
`signal_details`. Successful results include `days_evaluated`, `window_size_days`,
`warning_z_threshold`, `critical_z_threshold`. Short histories instead report
`days_available` and `min_days_required`.

The defaults require eight observed UTC days: seven prior points plus the latest.
A baseline uses up to14 prior finite observed daily values. Warning Z threshold2.5
and critical3.5 require at least two persistent abnormal observed points. The
SOH-rate signal can require additional data because the first difference is
missing; distance change must exceed0.01km. A sufficient overall day count does
not guarantee that each signal has enough finite history.

Signal statuses include normal, warning, critical, insufficient_baseline_points
and non_finite_current_reading. Usable signals return measured daily value,
baseline mean/std, Z-score, observed baseline count and persistence. Alerts retain
the supplied severity, signal identity, measurements, Z-score and explanation.
The backend/mobile validate counts, identities, finite numbers, coverage and
alert/detail agreement. They **do not recalculate severity from rounded Z-scores**.

This detector assesses the **latest daily point**, not every historical interval.
Its fields and explanation strings saying 'days' mean observed daily points,
which can span calendar gaps. There is no invented daily interpolation, trend
chart, mechanical diagnosis, probability or merged Isolation Forest/trend score.
Signal input availability does not imply successful analysis; inspect the actual
signal status and whole capability status too.

### Resources and verification

One extra sequential HTTP request is added, using the existing private key,
30-second upstream timeout,120-second overall deadline, admission semaphore and
byte/row limits. None was increased. The sample uses two point batches32+8, then
health, RUL and trend requests. Inference is still remote; no model is loaded by
the main backend. Invalid, unavailable or unauthorized trend responses become an
independent failed capability; other completed analyses remain available. If the
whole deadline expires, the route returns504 without misleading partial success.

The sample remains the unchanged40-row synthetic fixture over117 calendar days.
It supplies pack spread and SOH-rate inputs, but no average or verified ambient
measurement. Those missing signals are explicitly unavailable. Test coverage
compares sample/upload through the actual ML app, including point scores, health,
RUL point/bootstrap estimates and trend results. Artificial warning/critical test
patterns are separate from the built-in sample; they are protocol/threshold tests,
not battery-failure evaluation.

Physical Android, live Firebase/Render/TLS and the pinned serving environment are
not verified locally. The documented scikit-learn version warning and existing
PostgreSQL/legacy test skips still apply. Old perfect synthetic trends and narrow
bootstrap intervals establish no real battery-lifetime accuracy.

The deployment gates secured in`bd29b13` remain main-push-only. Full mobile Jest
regressions now also run in the existing mobile CI job on PR/merge-group checks.
No deployment hooks, secrets, Render settings, build profiles or production URLs
were changed.

### Completed trend verification

Local checks for this follow-up:118 backend tests passed,255 skipped (206 retired
KIT cases and49 PostgreSQL-dependent checks),45 ML tests passed, and503 mobile
tests passed across33 suites. TypeScript, Expo lint, ML lint, changed-file Python
lint, formatting and Git whitespace passed. Six CI workflow regression checks
passed; all workflow YAML parsed. Full backend Ruff retains five documented,
pre-existing findings in untouched legacy KIT/migration files.

A fresh genuine main-backend→ML-app test compared sample and upload results,
including trends and bootstrap intervals:40 readings over40 observed UTC days,
zero point flags, zero trend alerts; pack spread and SOH-rate signals normal.
SOC70%, SOH93.22%, health band4; experimental RUL point~59490km with100 valid
bootstrap fits and an80% interval. This very regular synthetic fixture is not a
battery-life benchmark. Average and ambient signals remain unavailable for this
fixture; range remains null. Both workflows together took~2.43s locally, with a
20826-byte sample response. The separate32-row synthetic SHAP stress batch took
~10.64s. These do not establish Render performance or justify higher limits.

No ML algorithms, artifacts, original sample bytes, production credentials or
Render settings were changed. Physical Android, live Firebase/Render and pinned
serving-environment verification remain pending. No push, deployment or APK build
was performed.
