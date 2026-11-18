# KIT forecast-based novelty model: per-signal selection experiment

**Run date:** 2026-11-14
**Dataset:** KIT Automotive OBD-II, DOI `10.35097/1130`
**Model:** Per-signal selection between multi-output XGBoost and last-window persistence

## Method

The model uses each window's 30 summary features (ten sensor medians, standard
deviations, and missing fractions) to predict the ten sensor medians in the next
consecutive window. Pairs never cross a recording, timestamp-reversal segment,
or date split. Within the first 25 of the 32 training dates, the final five
dates select XGBoost or persistence independently for each signal by MAE. The
selected forecast is then calibrated on the final seven training dates (kept
separate from selection) to set residual scales and the 99th-percentile novelty
threshold. Validation and test dates remain untouched until scoring.

This follows published label-free model-selection research that treats
prediction error as an imperfect surrogate measure ([Goswami et al., ICLR
2023](https://openreview.net/forum?id=gA5W0mOjWvk)). It selects the more accurate
forecast on those training dates; it does not establish anomaly or fault
detection quality.

Selected training-date forecasts: persistence for coolant, MAP, intake-air
temperature, throttle, ambient temperature, and both pedals; XGBoost for RPM,
speed, and MAF.

## Results

| Partition | Windows scored | Above threshold | Rate |
| --- | ---: | ---: | ---: |
| Training calibration | 3,601 | 36 | 1.00% |
| Validation | 3,839 | 57 | 1.48% |
| Test | 3,967 | 91 | 2.29% |

With max aggregation selected, 1.48% of validation windows and 2.29% of test
windows are flagged, compared with 1.17% and 1.24% for the original all-XGBoost,
RMS-scored baseline. The higher test rate may reflect distribution/context
shift or forecast errors; without fault labels, it cannot be called an
improvement or a false-alarm rate.
This describes score behavior over the chronological partitions only. KIT has
no verified fault labels, so the rates are **not** fault-detection precision,
recall, accuracy, or evidence of vehicle health. High scores may reflect normal
operating-context changes or forecast difficulty.

On held-out test dates, the selected hybrid forecast has lower MAE than raw
XGBoost for five signals (coolant, throttle, ambient temperature, and both
pedals), but higher MAE for MAP and intake-air temperature; it ties on the
remaining three by construction. The selected forecast beats persistence on
only RPM, speed, and MAF. This is mixed per-signal performance, not a uniformly
better forecaster. Exact MAE/RMSE comparisons and selection-date results are in
the JSON report.

## Synthetic sparse-shift sensitivity

To compare RMS aggregation with the maximum per-sensor normalized residual, each
validation and test target channel was separately shifted by a fixed multiple of its
training-calibration residual scale; each reported rate is the fraction of
shifted windows above that aggregation's threshold. These are **artificial
perturbations**, not observed faults. On the untouched validation split, a
10×-scale shift was flagged in an average 97.6% of channel-specific runs with
max aggregation versus 92.2% with RMS (range across channels: 96.0–99.7% vs
84.5–99.1%). This is why max aggregation was selected for the experiment. On
test, the corresponding synthetic sensitivity was 97.7% vs 92.0%. At 5× scale,
neither score reliably flags the injected shifts (max: 2.2% average on
validation; RMS: 2.5%). The metric therefore shows sensitivity to large
synthetic deviations only; it does not establish sensitivity to real faults.

The full RMS/max comparison and per-channel rates are recorded in the JSON.
Both aggregations are calibrated to the same nominal 99th percentile on training
calibration dates; the test set is reported after choosing max using validation
synthetic sensitivity.

## Limits and next evaluation

- KIT recording IDs are not verified vehicle identities.
- The threshold comes from seven training dates and may be sensitive to their
  operating contexts.
- A score is available only after the following 10-second window is observed;
  this is not an instantaneous alert model.
- XGBoost does not beat the persistence forecast on every signal.
- Per-signal model selection is based on only five training dates; its surrogate
  can fail to generalize, as the MAP and intake-air results illustrate.
- The higher test novelty rate is not evidence of better detection.
- Training and calibration data may contain unusual but unlabeled behavior.
- This is an exploratory statistical novelty model, not a fault classifier,
  RUL estimator, or production model.
- To assess whether flags correspond to faults, obtain independently verified
  fault events/labels or conduct a documented expert review of flagged windows.

Reproduce from the repository root with
`./.venv/bin/python -m ml.scripts.train_kit_xgb_forecast`. The generated model
artifact is local-only under `ml/artifacts/`; machine-readable run details are
in [`kit_xgb_forecast_baseline.json`](kit_xgb_forecast_baseline.json).
