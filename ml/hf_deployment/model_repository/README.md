---
license: other
library_name: scikit-learn
tags:
  - xgboost
  - anomaly-detection
  - time-series-forecasting
  - research
---

# DrivePulseAI KIT forecast novelty artifact

This repository file is a fitted research artifact for the KIT Automotive
OBD-II next-window novelty experiment.

## Source and attribution

The artifact was trained on prepared windows from the KIT Automotive OBD-II
Dataset by Marc Weber (2023), Karlsruhe Institute of Technology,
[DOI 10.35097/1130](https://doi.org/10.35097/1130). The source dataset is
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please cite
the dataset and retain its attribution when using or redistributing this model
artifact.

## Intended use and limits

The artifact forecasts selected sensor medians in the immediately following
10-second window from the current window's ten sensor medians, standard
deviations, and missing fractions. It contains fitted per-signal XGBoost or
persistence forecasters, residual scales, feature/target order, and a
99th-percentile training calibration threshold.

KIT has no verified mechanical fault labels. A high novelty score means a
forecast residual was unusual relative to calibration data; it is not a fault
probability, diagnosis, or validated fault-detection result. This artifact is
for research and recorded-data replay demonstrations only.

The artifact was serialized with joblib and must only be loaded by the matching
trusted DrivePulseAI serving code. Do not load untrusted pickle/joblib files.

## Oxford RUL estimator configuration

`oxford_rul_theilsen.joblib` contains the configured
`TheilSenCapacityTrendRUL` estimator (1,000-cycle lookback and a four-observation
minimum). It is an algorithm configuration, **not a fitted model learned from
pooled Oxford measurements**. At inference time, the serving API fits a robust
trend to the capacity history supplied in that request and extrapolates to the
caller-supplied capacity threshold.

The estimator is used with Oxford Battery Degradation Dataset 1 for experimental
RUL research: DOI [10.5287/bodleian:KO2kdmYGg](https://doi.org/10.5287/bodleian:KO2kdmYGg).
The source dataset's ODbL/DbCL terms and required citations are documented in
[`data/DATASET_ATTRIBUTION.md`](https://github.com/direkkakkar319-ops/DrivePulseAI/blob/main/data/DATASET_ATTRIBUTION.md).
The dataset itself is not included in this model repository.

The 75% first-crossing target is unconfirmed, only two cells cross it, and
cell-disjoint RUL performance is not established. Outputs are experimental proxy
estimates, not dependable battery-life forecasts.
