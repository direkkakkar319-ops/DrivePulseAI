# Machine-learning workspace

This directory contains exploratory data preparation and model work. It is not
the production inference service; no trained model is currently connected to
the mobile app through the backend.

## Directory map

| Path | Responsibility |
| --- | --- |
| `src/data/` | Dataset loaders and shared data contracts |
| `src/models/` | Model implementations, including KIT forecasting and Oxford trend estimators |
| `src/nissan_leaf_preparation/` | Nissan Leaf dataset-specific preparation and validation logic |
| `src/nissan_leaf_isolation/` | Nissan Leaf Isolation Forest experiment logic |
| `scripts/` | Reproducible command-line dataset audits, preprocessing, EDA, training, and comparisons |
| `notebooks/nissan_leaf_2018/config/` | Frozen, versioned experiment configurations |
| `notebooks/nissan_leaf_2018/scripts/` | Nissan Leaf experiment entry points; reusable implementation stays in `src/` |
| `tests/` | ML/data contract and experiment checks |
| `reports/data_validation/` | Dataset readiness and provenance audits |
| `reports/eda/` | Exploratory data analysis outputs |
| `reports/modeling/` | Method, metric, and limitation reports |
| `reports/nissan_leaf_2018/` | Source-specific preparation/model reports and tabular evidence |
| `artifacts/` | Local generated datasets, fitted models, and outputs; not source-controlled |

## Follow the work

1. Read [`../data/README.md`](../data/README.md) and the relevant source
   release README before selecting a dataset.
2. Use the source-specific script/config to prepare data; do not edit raw files.
3. Read the matching report under `reports/` for target assumptions, splits,
   results, and caveats.
4. Keep each experiment's inputs, config, code identity, outputs, and manifest
   together under a distinct run ID in local `artifacts/`.
5. Do not expose a model to the app until a backend inference contract and
   validated model/data contract exist. The current API status is in
   [`../docs/architecture/api-flow.md`](../docs/architecture/api-flow.md).

## Current model boundaries

- KIT XGBoost/persistence forecasting provides an unlabeled novelty score, not
  fault-detection accuracy.
- Nissan Leaf Isolation Forest is a single-vehicle research baseline. Candidate
  intervals are not verified faults.
- Oxford RUL trend comparisons use an unconfirmed first-crossing proxy from two
  cells. They do not validate RUL on unseen cells.

Use `python -m ml.scripts.<script_name>` for package scripts when available.
Nissan Leaf commands and pinned environment details are documented in its
source-specific reports. Never assume that local data or model artifacts are
present in a clean checkout.
