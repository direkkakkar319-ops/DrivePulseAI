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
| Machine learning | KIT OBD-II preprocessing, EDA, and an exploratory XGBoost novelty baseline; Oxford battery capacity/RUL target audit and historical trend baseline | Validated fault detection, reliable passenger-EV RUL, future-failure prediction, or app/API model integration |

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

## Current ML experiment: KIT OBD-II

The current model uses unlabeled OBD-II recordings of a Seat Leon. It predicts
the sensor medians in the next 10-second window from the current window's summary
features. Large forecast errors are marked as statistically novel.

- It selects XGBoost or a last-window persistence forecast per signal using
  training dates, then calibrates on later training dates. A maximum normalized
  per-sensor residual is used to give sparse, single-sensor deviations more
  influence. It flagged 1.48% of validation and 2.29% of test windows.
- The selected forecast improves test MAE over XGBoost on five signals but is
  worse on two and ties three; forecast quality is mixed. Synthetic 10x-scale
  single-sensor shifts were flagged in about 98% of validation cases, but these
  are artificial sensitivity checks, not real fault examples.
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

The full KIT source archive is published in repository-sized parts under
[`data/automotive_obd/kit_obd/raw_chunks/`](data/automotive_obd/kit_obd/raw_chunks/).
Its publisher checksum, citation, license, download link, and reconstruction
steps are documented in [`data/README.md`](data/README.md). The Oxford source
dataset is also available in parts; see its [official Oxford source page](https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac).
KIT's publisher record is [RADAR4KIT](https://radar.kit.edu/radar/en/dataset/bCtGxdTklQlfQcAq).

From the repository root, reconstruct and unpack KIT before running its
preprocessing script:

```bash
python3 data/automotive_obd/kit_obd/reassemble_source.py
mkdir -p data/automotive_obd/kit_obd/raw
tar -xf data/automotive_obd/kit_obd/raw/KIT_Automotive_OBD-II_Dataset.tar \
  -C data/automotive_obd/kit_obd/raw
unzip -q data/automotive_obd/kit_obd/raw/10.35097-1130/data/dataset/OBD-II-Dataset.zip \
  -d data/automotive_obd/kit_obd/raw/recordings
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
- **Oxford battery data:** supports capacity/SOH exploration. The historical
  Theil–Sen trend experiment used an unconfirmed first-crossing proxy and had
  large errors. A stricter two-reading 75% screen confirms no EOL events, so this
  release currently has no defensible supervised RUL target and is not evidence
  of passenger-EV fleet performance. A separate exponential trend comparison
  modestly improved proxy error on later cutoffs within the same two cells, but
  remains experimental and does not establish new-cell RUL performance; see the
  [method comparison](ml/reports/modeling/oxford_rul_method_comparison.md).
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
