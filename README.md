# DrivePulseAI

**A research prototype for passenger-car and passenger-EV health monitoring.**

DrivePulseAI explores how vehicle telemetry could support understandable
maintenance decisions. The repository contains an Android application, a small
FastAPI account service, dataset preparation tools, and exploratory ML work. The
product is not connected to live vehicle telemetry and does not provide
production diagnostics or maintenance predictions.

## Current status

| Area | Implemented | Not implemented |
| --- | --- | --- |
| Android app | Firebase sign-in, one-time onboarding, PostgreSQL-backed Garage, five-tab light UI, demo Insights, honest History, Profile/Settings | Live vehicle data, native CSV upload/processing, persisted analysis history, durable profile photos, and production assessments |
| Backend | FastAPI health, Firebase identity verification, PostgreSQL profile/onboarding storage, owner-scoped vehicle APIs, and persistent active selection | Live telemetry ingestion, analysis-history APIs, production prediction services, and report generation |
| Machine learning | Nissan Leaf anomaly scoring, experimental SOH/odometer RUL estimation, and rule-based battery health score | Verified fault diagnosis, fleet-level RUL accuracy, or completed backend integration |

Saved vehicle metadata, profile names, and onboarding completion persist through
the authenticated backend; the backend must be reachable to restore account state.
Removing all vehicles does not restart completed onboarding. Profile photo
selection is a temporary local preview.

Generic AI Insights uses clearly labeled illustrative fixtures, not actual model
outputs or measurements from a saved vehicle, and never adds records to History.
The older session-only simulated Garage remains separate from saved account
vehicles. Demo results are illustrative and are not analyses of the active Garage
vehicle. See [mobile setup](mobile/README.md) and
[backend setup](backend/README.md) for details.

## How the application currently connects

```text
Mobile app ── Firebase ID token ──> FastAPI ──> PostgreSQL
     │
     └── Demo Insights (illustrative fixtures)

ML preparation and experiments ──> reports/local artifacts
                                   (no inference API connection yet)
```

The implemented API flow covers authenticated profile, onboarding, and owned
vehicle data. Telemetry ingestion, model inference, saved assessments, and
analysis history are not yet connected. The detailed [API-flow diagram](docs/architecture/api-flow.md)
and [project map](docs/PROJECT_MAP.md) show the current boundaries and where
each part of the repository lives.

Docker Compose is optional for ML work and mobile UI development. The current
Compose file starts local PostgreSQL for backend development; it does not
containerize FastAPI or model inference. See [backend setup](backend/README.md).

## Current ML models: Nissan Leaf

The active ML service uses the preprocessed Nissan Leaf 2018 telemetry. Its
Isolation Forest scores six measured battery signals and returns the top three
SHAP contributions for unusual observations. The RUL estimator fits a robust
SOH-versus-odometer trend and projects kilometers to a configurable SOH
threshold; it requires at least 30 observed days across 90 calendar days. The
battery health score is a rule-based 1–5 mapping from reported SOH.

These are exploratory outputs from data representing one vehicle. The data has
no verified fault labels and no observed crossing of the configured RUL
threshold. Novelty flags are not fault diagnoses, SHAP contributions do not
prove physical causes, and the RUL projection is not validated for unseen
vehicles. The ML service currently accepts Nissan Leaf-specific inputs; the
backend still has a legacy KIT request contract and needs a separate integration
update.

## Data and evaluation boundaries

- **Nissan Leaf:** current model data is single-vehicle telemetry; use the
  limits above when interpreting novelty, SHAP, health, or RUL results.
- **Tongji EV data:** candidate for vehicle-disjoint SOH experiments; SOH is not
  observed RUL or a future-failure label.
- **Scania APS and Component X:** heavy-truck datasets. They must not support
  passenger-car or passenger-EV performance claims.
- **Other EV fault and capacity sources:** have unresolved access, label, join,
  vehicle-class, or data-rights questions documented in `data/`.

There is not yet a validated passenger-car/EV run-to-failure source or an
acquired, audited forward-failure dataset. The full anomaly → RUL/health → failure
chain is therefore not trained or validated. Keep each dataset as a separate
benchmark; do not combine results across different vehicles and targets into an
end-to-end claim.

## Technology and repository map

- **Android:** Expo, React Native, TypeScript, Firebase Authentication
- **Backend:** FastAPI, PostgreSQL, Firebase token validation
- **ML:** Python, pandas, scikit-learn, SHAP
- **Web frontend:** Next.js and TypeScript

```text
backend/       FastAPI service; profiles, onboarding, and owned vehicle APIs
data/          Dataset provenance, audits, and local-data rules
docs/          Product and integration notes, including Graphify documentation
frontend/      Next.js web application
ml/            Dataset preprocessing, models, training scripts, and reports
mobile/        Expo/React Native Android application
simulator/     Synthetic telemetry tools; not a source of vehicle evidence
```

The generated code relationship map is under [`graphify-out/`](graphify-out/).
Its inferred links are navigation hints and should be checked against source.
See [`docs/graphify.md`](docs/graphify.md).
The [ML workspace guide](ml/README.md) maps experiment code, reports, and
artifacts. The [dataset catalog](data/README.md) records source status and rights.

## Safety and scope

DrivePulseAI is an independent research and software prototype. It is not
affiliated with an automotive manufacturer, does not control vehicles, and
does not replace professional diagnosis. Simulated data, demo fixtures, and
statistical novelty scores must be identified as such; they are not proof of a
real vehicle fault or condition.

## Contributors

- Direk Kakkar — [GitHub](https://github.com/direkkakkar319-ops)
- Rudraksh Gupta — [GitHub](https://github.com/rudraksh6)

## License

The repository software is licensed under MIT; see [LICENSE](LICENSE). Dataset
licenses and reuse restrictions are recorded separately in the dataset
documentation.
