> Current active flow: Nissan Leaf sample/CSV analysis. The earlier KIT sections
> below describe the superseded implementation. See the current Nissan section
> at the end and `backend/docs/nissan-leaf-analysis.md`.

# Phase 4.1: Android analysis integration

## Current status

The Insights route now connects authenticated sample selection and analysis to the
main backend. Native CSV selection is now wired through `pickKitCsv` into the same
controller/client pipeline. `npx expo install expo-document-picker` installed
**57.0.3** (`~57.0.3`), compatible with Expo **57.0.22** and its bundled range
`~57.0.2`. Only DocumentPicker was added; no unrelated dependency versions changed.
No native binaries were rebuilt, backend changed or services deployed.

The native adapter loads only when the user selects a file. An older installed
development client missing `ExpoDocumentPicker` can still open Insights and use
sample analysis; file selection shows an actionable error. Clients built from
the previous dependency set require a later authorized native rebuild to include
the module. JavaScript hot reload alone cannot add native code. The actual phone
binary could not be inspected in this environment (no ADB/device access).

## Architecture

```text
Verified Firebase session
  → existing protected Insights route, keyed by account and explicit Home demo request
  → useAnalysis (transient source/catalog/request/result state)
  → analysisApi (on-demand Firebase ID token, cancellation, response validation)
  → EXPO_PUBLIC_API_URL / main FastAPI
  → existing secured backend-to-ML integration
```

No Android code calls the ML server, receives a model key, associates a dataset
with Garage, or saves a result to History. Existing account APIs and the simulator
provider remain unchanged. No new state framework is introduced.

| Method | Main-backend endpoint | Mobile API |
| --- | --- | --- |
| GET | `/api/v1/analysis/samples` | `analysisApi.samples(context)` |
| POST | `/api/v1/analysis/samples/{id}/analyze` | `analysisApi.sample(id, context)` |
| POST | `/api/v1/analysis/upload` | `analysisApi.upload(file, recordingDate, context)` |

`context.uid` is a local expected-account precondition, never a supplied owner in
an HTTP body. The client subscribes to the native Firebase session during each
request, waits for the matching verified identity, gets the token on demand, and
unsubscribes afterward. A 401 refreshes once; service failures do not automatically
repeat expensive analysis. Logout/account changes abort and invalidate requests.
Tokens stay in request-local variables, not React or persistent storage.

## Input and minimal UI

Open **AI Insights → Prerecorded KIT sample**. Opening the selector loads/refetches
the actual backend catalog; loading/error/Retry/empty states use `AppSelect`.
Select a sample, then press **Analyze KIT sample**. Selection alone does not run
inference. The success card shows evaluated/flagged pairs, maximum score, threshold,
the server summary and model version. Prepared telemetry is acknowledged by window
count. Phase 4.2 now adds detailed score and observed-telemetry plots, interval
inspection and model explanations; see [visualization mapping and verification](ANALYSIS_VISUALIZATION.md).

The existing **Use Demo Data** switch remains explicitly simulated. Switching
source cancels/invalidate real work and clears its results; demo values never
become predictions of the selected recording. Home's existing demo navigation is
preserved. Results stay in the current authenticated screen session only.

For CSV integration, `KitCsvFile` retains native `uri`, original
`name`, optional provider `mimeType`, and optional `sizeBytes`. The adapter requests
one system document, with no JS text/base64 read and no cache copy. Cancellation
keeps the previous selection; permission/provider/missing-module errors are safe
user messages. The picker filters CSV MIME aliases plus text/plain and
application/octet-stream fallbacks needed by Android providers. It does not use a
wildcard; `.csv` extension/size/reference validation still rejects incompatible
selections. Real Android provider behavior and the installed binary remain to be
tested; a MIME label alone never establishes KIT content compatibility.

The upload API constructs native `FormData` with exactly `file` and
`recording_date`; it does not set Content-Type or manufacture a multipart boundary.
The file part is `{uri, name, type:'text/csv'}`; the original provider MIME remains
available in local selection metadata. No raw CSV strings are read into JS.

Recording date is required as a real `YYYY-MM-DD` calendar date, never guessed from
the filename or file modification time. Local preflight accepts `.csv`, file/content
URIs, positive known sizes and up to 2 MiB (the documented backend default). Unknown
size remains unknown; backend streamed size, row/window/segment/batch and content
validation remain authoritative. This is the original UTF-8 KIT eleven-column
format, not arbitrary OBD-II/EV CSV compatibility. See the unchanged
[backend CSV contract](../backend/docs/phase-3b-csv-analysis.md).

## Contracts, validation and failure behavior

`types/kit-analysis.ts` mirrors the Phase 3C catalog, sample/upload discriminated
responses, windows, predictions, intervals, telemetry, signal definitions and
explanations. These types are separate from demo cards and saved History types.
`lib/kit-analysis.ts` checks schema/model versions, source and recording metadata,
finite values, counts, unique IDs, target references, score/flag/threshold
consistency, rankings, interval traceability and chart references. Unknown additive
fields are preserved; malformed/partial responses never become successful UI.

Scores are dimensionless normalized forecast deviations, not probabilities or
health percentages. KIT is combustion-engine research telemetry, not verified
fault diagnosis or EV battery health. `persisted:false` never creates a History
entry. Clock seconds and segment metadata remain intact; no UTC timestamps or
interpolated readings are created by this phase.

| Operation | Total client deadline | Rationale |
| --- | --- | --- |
| Catalog | 30 seconds | Bounded lightweight lookup; explicit retry for cold/unavailable service |
| Sample analysis | 240 seconds | Existing sample endpoint has six sequential 30-second batch budgets plus overhead |
| CSV upload/analysis | 90 seconds | Existing server has a 60-second overall upload-analysis budget; allow transfer/response overhead |

Deadlines cover identity/token acquisition and response decoding as well as fetch;
the account client's existing 15-second behavior is unchanged. Cancellation is
best effort: it stops accepting the response and aborts transport; it does not
promise to stop backend computation already underway. Newer requests, source/date
changes, unmount and account changes cannot publish an old response.

HTTP 401/403, 404, 408, 413, 415, 422, 429, 502/503/504 and unexpected failures map
to useful safe messages. Raw upstream error bodies, native exception internals,
tokens and file contents are not logged or shown. No fabricated partial success.

## Android verification

1. Use the existing Android development build and a verified Firebase account.
2. From `mobile/`, start Metro with the existing main-backend configuration:

   ```bash
   EXPO_PUBLIC_API_URL=https://drivepulse-backend-91fz.onrender.com npx expo start --dev-client
   ```

3. Open Insights, open the sample selector and choose the returned recording.
   Start analysis and check a real-result badge, model version and summary. For
   the full current sample, the backend regression reference is 163 windows,
   162 pairs and two flags; these are not hardcoded UI values.
4. Change source or cancel during loading; confirm old results do not reappear.
   Test error/Retry, Home demo entry, History staying empty and logout/login to a
   different account. Account/Garage behavior must remain intact.
5. With a binary containing the native module, select a genuine original KIT CSV,
   enter its actual date and run upload. Check replacement/removal, picker
   cancellation, invalid date/file, size limits and safe file-access errors. If
   the picker reports unavailable, obtain approval for a development rebuild
   separately; no rebuild or deployment is performed by this task.

## Automated verification

Run `npm test -- --runInBand`, `npx tsc --noEmit --incremental false`, and
`npm run lint -- --no-cache` in `mobile/`. Focused files cover the analysis client,
controller/UI, native picker boundary, production-route wiring, and existing
Insights/navigation regressions. Focused verification:

```bash
npm test -- --runInBand tests/analysis-api.test.ts tests/analysis-state.test.tsx tests/csv-picker.test.ts tests/analysis-route.test.tsx tests/ai-insights.test.tsx tests/garage-navigation-runtime.test.tsx
```
The test-only first-pair and flagged-pair JSON files are excerpts of genuine stored
backend model output; their reduced sample IDs/counts are fixture metadata, not
new advertised recordings.
Upload fixture metadata is a wire-contract fixture, not claimed raw-to-model proof.

HTTP, native Firebase and picker boundaries are mocked. Multipart tests use the
actual React Native FormData implementation rather than Jest's web FormData.
No successful live Firebase, authenticated deployed analysis or physical-device
verification is claimed. The production route tests exercise the real adapter,
controller, API client, validators and native FormData with only native service
and HTTP boundaries mocked.

Finalization verification: the full suite passed **432 tests in 30 suites**;
the focused command above passed **89 tests in six suites**. TypeScript,
configured Expo lint, lint of changed source/test files and `git diff --check`
passed. An additional broad `eslint .` scan reported four existing display-name
errors in `account-connectivity.test.tsx`, `auth-flow.test.tsx` and
`tab-navigation.test.tsx`, plus 24 warnings. Those unrelated files were preserved.

## Environment verification and remaining acceptance checks

An existing Metro process was left running. `http://127.0.0.1:8081/status` returned
`packager-status:running`. Requesting its Android development JavaScript bundle
returned HTTP 200 (6,634,688 bytes). This verifies module resolution/bundling, not
native module availability or execution on a phone. No second Metro process or
native build was started. The debugger target list was empty and ADB was absent;
no APK/module list was available to identify the installed phone build.

One live unauthenticated `GET /health` probe to the configured Render backend
timed out after approximately 20 seconds. This does not establish a backend outage
or a code incompatibility. Later unauthenticated probes of all three analysis
routes returned the expected HTTP 401 (catalog 583 ms, sample analysis 910 ms,
upload 385 ms). No authenticated session/token was available for successful live
catalog/sample/upload checks; successful response handling was verified with
mocked HTTP. Repeat actual login, sample and CSV acceptance checks on the
phone when its native build and service connectivity are available.

Installation reported the existing test-renderer/React peer-version warning and
87 npm audit advisories (11 moderate, 75 high, one critical). DocumentPicker has no
entry in that audit report; no other package version changed. No audit-fix command
or unrelated dependency upgrade was performed.

Official SDK reference: [Expo SDK 57 DocumentPicker](https://docs.expo.dev/versions/v57.0.0/sdk/document-picker/).

## Current Nissan Leaf integration (supersedes KIT sections above)

The active Insights route uses `use-leaf-analysis`, `api/leaf-analysis.ts`,
`types/leaf-analysis.ts` and `lib/leaf-analysis.ts`. It retains native Firebase
refresh/account isolation, cancellation and native DocumentPicker references.
Multipart now contains only `file`; timestamps are supplied within leaf-csv-v1,
not via a recording-date field. See `backend/docs/nissan-leaf-analysis.md` and the
clearly synthetic CSV under `backend/docs/examples/`.

Sample and upload render through the same Leaf result components: battery overview,
negative-direction novelty score chart, paginated unusual readings/top-three SHAP,
health bands, experimental RUL availability, quality warnings and recorded telemetry.
SVG charts use 48 points/page and break across missing/discontinuous readings;
SHAP cards use eight unusual readings/page. Demo mode remains separate and transient.
No model key reaches mobile and no analysis is saved to History/Garage.

No new native dependency was added. Existing Firebase/DocumentPicker development
client requirements still apply. Verify with `npx tsc --noEmit`, `npm run lint`,
`npm test -- --runInBand`; physical Android and live Render verification remain
pending. Old KIT utility tests are historical; active route tests now use Leaf
protocol fixtures, explicitly artificial rather than evaluation/model results.

### Partner RUL confidence intervals

The reconciled response accepts optional RUL percentile fields and nested
`confidence_interval`, including absent/null intervals. Runtime checks reject
nonfinite, negative, unordered, partial or inconsistent populated bounds. Results
show the supplied level, lower/median/upper distance, available calendar bounds,
and valid bootstrap-fit count with explicit experimental limitations.
The follow-up Battery Trend Analysis section now integrates rolling Z-score results
as a separate capability. Isolation Forest remains the point-anomaly detector;
trend alerts never replace its scores, flags or SHAP explanations.

## Battery Trend Analysis

`leaf-trend-results.tsx` displays the independent capability status and source
coverage, actual drift flags/counts, warning/critical alerts, measured daily values,
rolling baselines, Z-scores and per-signal availability. `lib/leaf-trend.ts` validates
this optional additive response before rendering. Missing older response fields
produce an unavailable section without breaking existing point charts or RUL.

Trend data does not share Isolation Forest scores or SHAP semantics. Baselines and
persistence refer to observed UTC daily points and assess the latest daily point;
calendar gaps are not interpolated. Missing average/ambient data is never invented.
The source picker, native URI upload, Firebase refresh, account isolation, request
cancellation and transient results still use the same controller/client.

RUL retains its original point estimate and separately displays optional lower,
median and upper bootstrap estimates using the supplied confidence level. Missing
intervals do not hide a valid point estimate. Uncertainty is experimental, not a
battery-failure probability or guaranteed lifetime bound.

See `backend/docs/nissan-leaf-analysis.md` for the exact history, signal-availability,
resource and deployment contract. Physical Android and live Render checks remain
pending; no APK or native rebuild was generated.
