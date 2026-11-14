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
| Android app | Firebase sign-in and a clearly labelled demo garage with illustrative vehicle, sensor, insight, and report screens | Live vehicle data, backend-backed vehicle records, and production assessments |
| Backend | FastAPI health route and authenticated Firebase user-profile synchronization with PostgreSQL | Telemetry ingestion, vehicle APIs, prediction services, and report generation |
| Machine learning | KIT OBD-II preprocessing, EDA, and an exploratory XGBoost forecast-based novelty baseline | Validated fault detection, passenger-car RUL, future-failure prediction, or app/API model integration |

The mobile demo uses deterministic, session-only fixtures. Its assessments are
illustrations, not measurements from a real vehicle. See [mobile setup](mobile/README.md)
and [backend setup](backend/README.md) for details on the implemented app and API.

## Current ML experiment: KIT OBD-II

The current model uses unlabeled OBD-II recordings of a Seat Leon. It predicts
the sensor medians in the next 10-second window from the current window's summary
features. Large forecast errors are marked as statistically novel.

- It was calibrated on later training dates and evaluated on chronological
  validation and test dates. The novelty rates were 1.17% and 1.24% respectively.
- Against a simple last-window forecast, XGBoost had lower mean absolute error on
  7 of 10 signals in both splits, and higher error on coolant, throttle, and
  ambient temperature.
- KIT has no verified fault labels or independent vehicle IDs. These figures do
  not measure fault-detection accuracy, and a novelty flag is not a fault
  diagnosis. A score is available only after the following 10-second window
  arrives.

The report is in
[`ml/reports/modeling/kit_xgb_forecast_baseline.md`](ml/reports/modeling/kit_xgb_forecast_baseline.md),
with per-signal results in
[`ml/reports/modeling/kit_xgb_forecast_baseline.json`](ml/reports/modeling/kit_xgb_forecast_baseline.json).
The trained model artifact and raw/processed KIT data are local-only and
gitignored.

### Reproduce the KIT experiment

Obtain the KIT source files and place the recordings at the path documented in
[`data/README.md`](data/README.md). From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements.txt
python3 ml/scripts/preprocess_kit_obd.py
python3 -m ml.scripts.train_kit_xgb_forecast
```

Dataset sources, terms, audit findings, and local file paths are documented in
[`data/README.md`](data/README.md). Dataset rights and terms are separate from
the repository's software license.

## Data and evaluation boundaries

- **KIT OBD-II:** supports exploratory automotive telemetry novelty scoring; it
  has no verified mechanical fault labels, RUL target, or verified vehicle IDs.
- **Oxford battery data:** small laboratory-cell data for limited SOH/RUL method
  exploration; not evidence of passenger-EV fleet performance.
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
- **ML:** Python, pandas, scikit-learn, XGBoost
- **Web frontend:** Next.js and TypeScript

```text
backend/       FastAPI service; user-profile endpoints are implemented
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
