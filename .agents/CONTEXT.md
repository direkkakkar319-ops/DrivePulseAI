# CONTEXT.md — DrivePulse AI

Full project context. Read this to understand *what* this project is and *why* it's built this way. For *how to behave as an agent working in this repo*, see `AGENTS.md`.

## What this project is

**DrivePulse AI — Explainable Vehicle Health Digital Twin and Predictive Maintenance Platform.**

A system that ingests simulated (or public) vehicle sensor data, builds a live "digital twin" of the vehicle, and:

- Monitors RPM, speed, battery voltage, coolant temperature, vibration, and fuel/energy consumption
- Detects abnormal behavior
- Predicts component-failure risk
- Estimates remaining useful life (RUL)
- Computes an overall vehicle health score
- **Explains** every prediction/alert with the underlying evidence (never a bare percentage)
- Displays everything on a dark, premium, Mercedes-style dashboard
- Generates a maintenance report for a technician or driver

This is a portfolio/demonstration project intentionally scoped to look like real Digital Twin / predictive maintenance platform work (it's aligned with roles like MBRDI's Digital Twin AI openings), not a toy "car price prediction" script. Code quality, explainability, and architecture matter as much as raw model accuracy.

## Data honesty (important, not just a formality)

All simulator-generated telemetry must be clearly labeled as simulated (e.g. a `"source": "simulated"` field on every payload/row). Never imply simulated data came from a real Mercedes vehicle or real fleet. This applies to code, docs, UI copy, and sample outputs.

## Example of expected output quality

The dashboard/report should look like this — evidence-first, not a bare number:

```
Vehicle health: 73/100
Battery failure risk: 68%
Detected behaviour: abnormal voltage drop during ignition
Likely causes: ageing battery, alternator instability, or loose connection
Recommended action: inspect charging voltage within 7 days
Model confidence: 86%
```

Every alert or prediction the system surfaces should be traceable back to specific sensor evidence (via SHAP or deviation-from-baseline), not just a model output number.

## Tech stack (decided — see AGENTS.md for the rule about changing it)

**Backend:** Python + FastAPI (not Go — the ML stack, SHAP, and model inference are Python-native; keeping backend and ML in the same language avoids a cross-language serving layer). Pydantic for schemas, SQLAlchemy + PostgreSQL for persistence, Alembic for migrations, native FastAPI WebSockets for live telemetry streaming.

**ML:** Python, Pandas, NumPy, scikit-learn, XGBoost, PyTorch only if a model genuinely needs it (not by default), SHAP for explainability, MLflow for experiment tracking.

**Frontend:** Next.js + TypeScript, Tailwind CSS, Recharts or Apache ECharts for live charts, dark premium automotive visual style (serves as the Product Showcase).

**Mobile:** React Native (Expo) + TypeScript + NativeWind for the end-user Android application.

**Optional/stretch:** A Go-based version of the telemetry simulator is an acceptable stretch add-on (goroutines per simulated vehicle) but is not required, and must talk to the FastAPI backend over the same WebSocket/HTTP contract as the Python simulator — it doesn't change backend language.

**Engineering:** Docker + Docker Compose, Pytest, GitHub Actions CI, Ruff for Python linting.

## Models (three, in build-priority order)

1. **Anomaly detection** — Isolation Forest, unsupervised, trained directly on sensor data (no failure labels required). Explained via `deviation_explainer.py` (z-score / baseline deviation), since SHAP doesn't map cleanly onto unsupervised models.
2. **Failure prediction** — XGBoost or Random Forest, supervised, predicts probability a component will fail. Requires labeled failure data (from AI4I / C-MAPSS, or engineered labels). Explained via `shap_explainer.py`.
3. **Remaining useful life (RUL)** — regression, estimates operating hours/km remaining before maintenance is needed.

All three models share a common interface (`ml/src/models/base.py`) so `ml/src/inference/predictor.py` can load and call them uniformly, and the backend only ever talks to `predictor.py` — never to individual model files directly.

## Vehicle health score

A single 0–10 (displayed as /100 on the dashboard per the example) score combining:
- Normalized sensor sub-scores (battery voltage, coolant temp, vibration, RPM, engine load) weighted by how strongly each indicates early failure (battery voltage and coolant temp weighted highest)
- Model-derived sub-scores (anomaly score, failure probability, RUL urgency)

Weights live in one config location (`ml/src/scoring/health_score.py`) so they can be tuned later. Each sub-score's contribution to the final number must be stored alongside the score so the UI can show point deductions per factor (e.g. "battery_voltage: −1.8"), consistent with the project's explainability requirement.

## Data sources

- **AI4I 2020 Predictive Maintenance Dataset** — industrial, not automotive; used for failure classification technique, fields relabeled/mapped to automotive equivalents in `data/README.md`.
- **NASA C-MAPSS turbofan degradation dataset** — used for RUL regression technique, similarly relabeled.
- **Simulator output** (`simulator/`) — generates automotive-specific fields directly, is the primary source for anomaly detection and dashboard demo data.

Example simulated payload shape:
```json
{
  "vehicle_id": "SIM-001",
  "speed_kmph": 62,
  "engine_rpm": 2250,
  "coolant_temp_c": 103,
  "battery_voltage": 11.7,
  "engine_load_pct": 76,
  "vibration": 0.68,
  "timestamp": "2026-08-05T10:30:00Z",
  "source": "simulated"
}
```

## Repo structure and file purposes

High-level module map:
- `ml/` — model training, inference, explainability (standalone-installable, no backend dependency)
- `simulator/` — generates and streams fake telemetry, tags it `source: simulated`
- `backend/` — FastAPI app; owns the DB, REST/WebSocket API, and calls `ml/` for predictions
- `frontend/` — Next.js Product Showcase; talks to `backend/` over REST + WebSocket
- `mobile/` — React Native Android app; serves as the end-user product interface
- `data/` — raw/processed/simulated datasets, gitignored where large
- `docs/`, `scripts/`, `.github/workflows/` — supporting docs, dev scripts, CI

## Build/integration order

1. `ml/` — train and validate all three models standalone in notebooks, then promote to `src/`
2. `simulator/` — build against the fixed payload schema above, independent of `ml/`
3. `backend/` — integration point; wires `ml/` inference and `simulator/` stream together via WebSocket
4. `frontend/` — can start against mocked JSON matching the example output, then switch to live backend endpoints
5. `mobile/` — Android application; integrates with backend authentication and telemetry endpoints
