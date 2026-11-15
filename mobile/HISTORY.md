Analysis History presentation and future persistence boundary (Phase 4.5).

Current backend inspection
--------------------------

`backend/app/main.py` registers user/profile and onboarding/vehicle routes, plus
health. No analysis-history list/detail endpoint is implemented. The files
`backend/app/api/routes/reports.py`, `backend/app/api/routes/telemetry.py`, and
`backend/app/models/maintenance_report.py` contain comments, not working history
routes or a mapped persistence model. Local recorded clips and their frozen
experimental results are research assets, not account-owned saved analyses.

Production behavior
-------------------

The existing History tab renders `HistoryScreen` with its explicit
`not-integrated` resource state. It makes no network request, creates no record,
and shows no simulated loading/error state. It displays the requested empty text
and a primary Explore AI Insights action. Navigation occurs only on a press.
The screen does not depend on Garage, onboarding data, demo mode, or replay state.
Existing parent Firebase verification and onboarding guards still apply.

History has no import from demo fixtures, no local persistence, and no connection
to Phase 4.4 demo selection. Entering demo mode never creates History entries.
There is no details route or clickable record in the production empty state.
The original recorded telemetry/replay/results/detail routes remain separate.

Reusable presentation
---------------------

- `types/analysis-history.ts` defines UI view models, not an agreed API schema.
  Records require an ID; optional server metadata includes timestamp, source,
  status, and summary. Source categories support CSV upload, recorded dataset,
  and other sources. Demo is intentionally not a source category.
- `AnalysisHistoryCard` displays only supplied metadata. Its optional `onOpen`
  callback enables View analysis and receives the record ID. No callback means
  no detail action; it does not invent a route or serialize a record into params.
- `HistoryScreen` supports supplied loading, error, ready-empty, and populated
  resources. Retry is rendered only for an error with a supplied callback.
- `AnalysisDetailsScreen` is an unrouted reusable screen. It accepts a resource
  containing a record, optional generic labeled results/explanations and telemetry
  metadata, plus Back/Retry callbacks. Missing records, fields, values, results,
  explanations, and telemetry metadata have explicit fallbacks.
- Dates use the device locale/time zone, including a time-zone label. Missing or
  invalid timestamps are unavailable rather than replaced with the current time.
  Status and summary are never inferred. No Garage relationship is inferred.
- Typed example records live exclusively in tests; application code contains no
  history fixtures, invented predictions, default health values, or scores.

Missing contract for Phase 6
---------------------------

The backend must first define durable account-owned analyses and authenticated
list/detail responses, including ID, timestamp/time-zone semantics, supported
source provenance, status semantics, optional summary/results/explanations,
telemetry metadata, and pagination. This phase does not prescribe endpoint paths
or implement that backend. A future validated adapter must map genuine responses
to these UI view models, using Firebase authentication and owner enforcement.
It must not import demo or replay results to fill missing API fields.

The future adapter must scope requests/state to the current account, discard
stale responses on logout/account switching, distinguish failed requests from
empty results, and connect real retry/loading state. Only an explicit backend
vehicle relationship may attach an analysis to a saved Garage vehicle. Register
a protected detail route only when records can be fetched by ID with ownership
checks, and wire the card callback then. No database/backend work or adapter is
implemented here.

Android checks
--------------

Reload the existing development build. Open History from its tab and from Home's
View History action; confirm the empty state. Press Explore AI Insights, enable
demo mode, return to History, and confirm it stays empty. Repeat tab switching
and Android Back (the tab navigator returns to Home). Check large font sizes,
safe areas, and scrolling, including on a completed account with an empty Garage.
There is no native dependency change or new APK requirement. Physical Android
verification remains necessary; this phase does not fix the separately reported
intermittent Garage navigation crash.
