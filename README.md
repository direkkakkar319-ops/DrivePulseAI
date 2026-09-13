# DrivePulse AI
### Enterprise Explainable Vehicle Health Digital Twin & Predictive Maintenance Platform

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2014-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Python](https://img.shields.io/badge/ML-Python%203.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![XGBoost](https://img.shields.io/badge/Models-XGBoost%20%7C%20IsolationForest-eb5e28?style=flat)](https://xgboost.readthedocs.io/)
[![SHAP](https://img.shields.io/badge/XAI-SHAP-brightgreen?style=flat)](https://shap.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**DrivePulse AI** is an enterprise-ready, explainable vehicle health **Digital Twin and Predictive Maintenance platform** designed for commercial fleets, telematics operators, and automotive service networks. 

By continuously ingesting high-frequency time-series telemetry, DrivePulse AI builds an active digital twin for every vehicle in a fleet—detecting multivariate anomalies, predicting component failures before roadside breakdowns occur, and **explaining every alert with clear, interpretable sensor evidence (XAI)**.

---

## 🚀 The Problem & SaaS Value Proposition

| The Industry Pain Point | The DrivePulse AI Solution |
| :--- | :--- |
| **Costly Unplanned Downtime:** Commercial vehicles out of service cost between $500–$1,000+ per vehicle/day in delayed deliveries and emergency repairs. | **Predictive Failure Detection:** Identifies degrading components (battery, cooling systems, mechanical wear) days before catastrophic failure. |
| **The "Black-Box" AI Dilemma:** Generic models output opaque risk percentages (e.g., *"78% Risk"*), leading technicians to disregard alerts due to lack of diagnostic context. | **First-Class Explainability (XAI):** Powered by SHAP and baseline z-score deviation, every alert pinpoints exact root causes (e.g., *“−0.42V ignition voltage drop”*). |
| **Fragmented Fleet Visibility:** Fleet dispatchers see GPS; technicians see OBD fault codes only after a warning light illuminates. | **Unified Digital Twin Cockpit:** Real-time health scoring (0–100), automated technician work orders, and streaming telemetry in one dashboard. |

---

## 🌟 Key Capabilities

### 1. Real-Time Digital Twin Engine
* **High-Frequency Ingestion:** Streams speed, engine RPM, coolant temperature, battery voltage, engine load, and vibration via high-performance WebSocket & REST channels.
* **Transparent 0–100 Vehicle Health Score:** Continuous single-index health rating with visible per-sensor point deductions (e.g., `battery_voltage: -1.8 pts`).

### 2. Three-Tier Predictive Machine Learning
* **Unsupervised Anomaly Detection:** Scikit-learn **Isolation Forest** trained to detect unexpected multivariate deviations without requiring historical failure tags.
* **Component Failure Risk Classifier:** **XGBoost** classifier calibrated for imbalanced predictive maintenance data to forecast failure probabilities.
* **Remaining Useful Life (RUL) Regressor:** Degradation model predicting operating hours/cycles remaining before required servicing.

### 3. First-Class Explainability (Never a Bare Number)
Every prediction surfaces its underlying evidence:
* **SHAP (Shapley Additive Explanations):** Feature-importance waterfall and bar contributions quantifying which sensors drove the failure probability upward.
* **Z-Score Deviation Explainer:** Calculates standard deviations away from normal vehicle operating baselines for clear, plain-language diagnostics.

```
Vehicle Health: 73/100
Battery Failure Risk: 68% (High)
Detected Behaviour: Abnormal voltage drop during engine start
Likely Root Causes: Ageing cell, alternator instability, or loose terminal
Recommended Action: Inspect charging voltage within 7 days
Model Confidence: 86%
```

---

## 👥 Multi-Persona Workflows

* **Fleet Dispatcher Portal:** High-level fleet health index, live vehicle map, operational readiness, and high-priority maintenance alerts.
* **Technician Diagnostics Workbench:** In-depth sensor time-series charts, SHAP root-cause breakdown, threshold violation history, and printable maintenance reports.
* **Driver Cockpit:** Streamlined mobile-friendly health status (0–100), urgent warnings, and safety advisories.
* **MLOps & Engineering Hub:** Drift monitoring, model accuracy/recall tracking, and scenario fault injection.

---

## 🏗️ System Architecture

DrivePulse AI is architected in four strictly decoupled layers following a clean build order (**`ml/` $\rightarrow$ `simulator/` $\rightarrow$ `backend/` $\rightarrow$ `frontend/`**):

```
                                    +-----------------------------+
                                    |    Data Sources / Telemetry |
                                    | AI4I | C-MAPSS | Simulator  |
                                    +--------------+--------------+
                                                   |
                                                   v
+------------------------+          +--------------+--------------+
|  Frontend Application  |  REST /  |     FastAPI Backend API     |
|   (Next.js 14 + TS)    |<-------->|   WebSockets & REST Layer   |
| Dark Luxury Automotive |  WS      +--------------+--------------+
+------------------------+                         |
                                                   v
                                    +--------------+--------------+
                                    |  Predictor Inference Engine |
                                    |  (Isolation Forest, XGBoost)|
                                    |  (SHAP & Deviation XAI)     |
                                    +--------------+--------------+
                                                   |
                                                   v
                                    +-----------------------------+
                                    |    PostgreSQL Persistence   |
                                    | Telemetry, Predictions, DB  |
                                    +-----------------------------+
```

### Complete Five Data Flows
1. **Offline Training Pipeline:** Automated data ingestion, leakage-guarded preprocessing, time-ordered train/val splits, and artifact logging via MLflow.
2. **Live Telemetry WebSocket Stream:** High-throughput streaming from edge simulators/OBD devices to the backend with sub-100ms inference broadcast.
3. **REST Telemetry Ingest:** Synchronous batch ingestion for historical uploads and mobile integrations.
4. **Dashboard State Reads:** REST endpoints for vehicle catalogs and prediction histories coupled with live WebSocket state updates.
5. **Maintenance Report Generation:** Aggregated fleet health summaries, alert resolution workflows, and printable maintenance briefs.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend API** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Native WebSockets |
| **Database** | PostgreSQL 15+ (Time-series telemetry, vehicle registry, alerts) |
| **Machine Learning & XAI** | Scikit-learn, XGBoost, SHAP, Pandas, NumPy, Joblib, MLflow |
| **Frontend Web App** | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts / Lucide Icons |
| **Simulator & Telematics** | Python AsyncIO Telemetry Streamer (with optional Go high-concurrency client) |
| **DevOps & Infrastructure** | Docker, Docker Compose, GitHub Actions CI, Ruff linter, Pytest |

---

## 🔒 Data Honesty, Safety & Benchmark Integrity

> **Important Disclosure:**  
> DrivePulse AI is an engineering and predictive maintenance demonstration prototype. It is independent and is not affiliated with, sponsored by, or deploying proprietary data from any automotive manufacturer.
> 
> * All simulated telematics payloads generated by the platform carry an explicit `"source": "simulated"` tag.
> * Training leverages recognized public predictive maintenance benchmarks ([UCI AI4I 2020](https://archive.ics.uci.edu/dataset/601/ai4i) for classification and [NASA C-MAPSS](https://data.nasa.gov/dataset/cmapss-jet-engine-simulated-data) for degradation curves) mapped to automotive equivalents for validation.
> * The platform serves as decision-support guidance for drivers and technicians; it does not issue vehicle-control or override commands.

---

## 📁 Repository Structure

```text
DrivePulseAI/
├── backend/                 # FastAPI service: schemas, WebSocket routes, DB services
│   ├── app/                 # Core application logic, routers, and database models
│   └── tests/               # Backend API and WebSocket integration tests
├── frontend/                # Next.js 14 web dashboard: dark luxury UI, real-time gauges
│   └── src/                 # React components, hooks, Tailwind styling, and API clients
├── ml/                      # Standalone machine learning package
│   ├── src/data/            # Unified data loaders and leakage-free preprocessing
│   ├── src/models/          # Isolation Forest, XGBoost classifier, RUL regressor
│   ├── src/explainability/  # SHAP TreeExplainer and baseline deviation explainers
│   ├── src/inference/       # Unified Predictor gateway
│   └── artifacts/           # Serialized model binaries (.joblib)
├── simulator/               # Vehicle telemetry generator with fault injection profiles
├── data/                    # Dataset loaders, schemas, and mapping documentation
├── docs/                    # Architecture diagrams and system flow specifications
├── docker-compose.yml       # Production/local multi-container orchestration
└── requirements.txt         # Root Python dependencies
```

---

## 💼 Commercial SaaS Model & Go-To-Market (GTM)

DrivePulse AI is positioned as a **B2B Vertical Telematics & AI SaaS** platform.

### 1. Target Customers (Ideal Customer Profile — ICP)
* **Mid-Market Commercial Fleets (20–250 Vehicles):** Last-mile delivery, field service contractors, and regional freight operators where an unscheduled breakdown disrupts delivery commitments and triggers customer SLA penalties.
* **Car Rental & Carsharing Fleets:** High-turnover operations requiring real-time mechanical health tracking to protect residual vehicle value and prevent roadside breakdowns.
* **Commercial EV Fleets:** Specialized operators requiring proactive monitoring of battery cell degradation, charging thermals, and regenerative braking health.
* **Automotive Dealership & Service Networks:** Service centers offering proactive remote diagnostics and recurring maintenance subscription tiers to commercial customers.

### 2. Telemetry Ingestion Architecture (No Proprietary Hardware Lock-In)
* **Plug-and-Play OBD-II Telematics (BYOD):** Standard cellular telematics hardware (e.g., Teltonika, CalAmp, Geotab GO) plug into standard J1962 / CAN ports and forward time-series data to the DrivePulse REST/WebSocket endpoints.
* **OEM Cloud-to-Cloud Integrations:** Ingest directly from connected-vehicle manufacturer APIs (e.g., Ford Pro, Mercedes-Benz Developers, Smartcar, Tesla Fleet API).
* **Enterprise Webhook Gateway:** Direct HTTP ingestion for third-party telematics service providers (TSPs).

### 3. Subscription & Pricing Architecture (Per Vehicle / Month)

| Tier | Price | Ideal For | Features Included |
| :--- | :--- | :--- | :--- |
| **Starter** | **$12** / veh / mo | Small fleets (10–30 vehicles) | Real-time telemetry ingestion, deterministic threshold alerts, 0–100 health score, driver mobile cockpit. |
| **Pro** | **$25** / veh / mo | Mid-market logistics (30–150 vehicles) | **Everything in Starter +** Isolation Forest Anomaly Detection, XGBoost Component Failure Classifier, SHAP root-cause diagnostic panels, automated technician work-order reports. |
| **Enterprise** | **$40+** / veh / mo | Large fleets & OEM networks (150+ vehicles) | **Everything in Pro +** Remaining Useful Life (RUL) regression, ERP/CMMS maintenance dispatch webhooks, custom feature engineering, dedicated SLAs, multi-tenant sub-fleet isolation. |

### 4. Quantified Downtime ROI
> **The Financial Case for Fleet Directors:**  
> Unscheduled roadside breakdowns cost commercial fleet operators an average of **$500 to $1,200 per day** in emergency towing, expedited labor, and missed delivery SLA fines.  
> 
> For a typical fleet of **50 delivery vans**, preventing just **2 catastrophic roadside failures per year** yields approximately **$10,000–$15,000 in net savings**—more than paying for the entire annual DrivePulse AI Pro subscription.

---

## 🚦 Getting Started

### 1. Prerequisites
* **Python 3.11+**
* **Node.js 20+**
* **PostgreSQL 15+** (or Docker)

### 2. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/direkkakkar319-ops/DrivePulseAI.git
cd DrivePulseAI

# Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# Set up Frontend dependencies
cd frontend
npm install
cd ..
```

### 3. Running with Docker Compose (Planned for full integration)
```bash
docker compose up --build
```

---

## 👨‍💻 Authors & Core Contributors

* **Direk Kakkar** — [GitHub](https://github.com/direkkakkar319-ops)
* **Rudraksh Gupta** — [GitHub](https://github.com/rudraksh6)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
