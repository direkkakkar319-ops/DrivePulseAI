# KIT XGBoost forecast novelty baseline

**Run date:** 2026-11-14
**Dataset:** KIT Automotive OBD-II, DOI `10.35097/1130`
**Model:** Multi-output XGBoost regression forecasting the next 10-second window

## Method

The model uses each window's 30 summary features (ten sensor medians, standard
deviations, and missing fractions) to predict the ten sensor medians in the next
consecutive window. Pairs never cross a recording, timestamp-reversal segment,
or date split. It was fit on the first 25 of the 32 training dates. The last
seven training dates calibrated per-sensor forecast-error scales and the 99th
percentile novelty threshold. Validation and test dates were scored after this
calibration.

## Results

| Partition | Windows scored | Above threshold | Rate |
| --- | ---: | ---: | ---: |
| Training calibration | 3,601 | 36 | 1.00% |
| Validation | 3,839 | 45 | 1.17% |
| Test | 3,967 | 49 | 1.24% |

The validation and test novelty rates are close to the nominal calibration rate.
This describes score behavior over the chronological partitions only. KIT has
no verified fault labels, so the rates are **not** fault-detection precision,
recall, accuracy, or evidence of vehicle health. High scores may reflect normal
operating-context changes or forecast difficulty.

As a forecasting check, XGBoost had lower per-signal MAE than a last-window
persistence forecast on 7 of 10 sensor medians in both validation and test. It
had higher MAE for coolant temperature, throttle position, and ambient
temperature on both partitions. This mixed result means XGBoost has not shown a
uniform advantage over the simple forecast baseline. Exact per-signal MAE and
RMSE comparisons are in the JSON report.

## Limits and next evaluation

- KIT recording IDs are not verified vehicle identities.
- The threshold comes from seven training dates and may be sensitive to their
  operating contexts.
- A score is available only after the following 10-second window is observed;
  this is not an instantaneous alert model.
- XGBoost does not beat the persistence forecast on every signal.
- Training and calibration data may contain unusual but unlabeled behavior.
- This is an exploratory statistical novelty model, not a fault classifier,
  RUL estimator, or production model.
- To assess whether flags correspond to faults, obtain independently verified
  fault events/labels or conduct a documented expert review of flagged windows.

Reproduce from the repository root with
`./.venv/bin/python -m ml.scripts.train_kit_xgb_forecast`. The generated model
artifact is local-only under `ml/artifacts/`; machine-readable run details are
in [`kit_xgb_forecast_baseline.json`](kit_xgb_forecast_baseline.json).
