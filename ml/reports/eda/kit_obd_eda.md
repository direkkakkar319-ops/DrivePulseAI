# KIT Automotive OBD-II — exploratory data analysis

**Analysis date:** 2026-11-14. **Source:** locally retained KIT/RADAR release, DOI `10.35097/1130`.
**Inputs:** 81 original CSV recordings and the local 10-second window output from `ml/scripts/preprocess_kit_obd.py`. The raw files were not modified. No models were trained.

## Summary

The KIT data is an unlabeled set of Seat Leon OBD-II trips. It can support exploratory unsupervised novelty/anomaly experiments, but this EDA found no ground-truth mechanical fault or healthy/faulty class label. Filename words such as `Normal`, `Stau` (traffic jam), `Frei` (free-flow), and `Messfehler` (measurement error) describe recording/road context; they are not verified vehicle-health labels.

There is therefore **no labeled class balance to correct**. SMOTE is not applicable to this dataset as it stands. The counts by filename context are imbalanced, but resampling them would incorrectly turn road/recording context into fault classes. KIT cannot currently support supervised anomaly scoring or class-based evaluation.

## Inventory and split

| Item | Finding |
| --- | ---: |
| Recordings | 81 |
| Filename dates | 46 (2017-07-05 to 2018-04-23) |
| Raw rows | 2,693,824 |
| Raw fields | Time plus 10 OBD signals |
| Generated non-overlapping 10-second windows | 25,069 |
| Backward timestamp jumps | 5, each 42–466 ms |
| Median / 95th percentile positive sample interval | 90 / 149 ms |
| Missing raw signal cells | 3,653 / 26,938,240 (0.0136%) |

The generated windows use a chronological date-grouped split. Dates and every trip on a date stay in one split; it is a temporal holdout, not an official split or vehicle-disjoint evaluation. The source does not establish that the recordings represent independent vehicles.

| Filename road/recording context (not a health label) | Recordings | Raw rows | Windows | Window share |
| --- | ---: | ---: | ---: | ---: |
| `Normal` | 56 | 1,975,592 | 18,177 | 72.5% |
| `Stau` (traffic jam) | 10 | 420,440 | 3,743 | 14.9% |
| `Frei` (free-flow) | 14 | 238,158 | 2,622 | 10.5% |
| `Messfehler` (measurement error) | 1 | 59,634 | 527 | 2.1% |

| Split | Windows | Normal context | Traffic-jam context | Free-flow context | Measurement-error context |
| --- | ---: | ---: | ---: | ---: | ---: |
| Train | 17,238 | 11,945 | 2,389 | 2,377 | 527 |
| Validation | 3,851 | 3,720 | 0 | 131 | 0 |
| Test | 3,980 | 2,512 | 1,354 | 114 | 0 |

This split has a strong context shift: validation has no traffic-jam trips, and the only `Messfehler` recording is in train. These categories cannot be used as anomaly labels, and the split cannot measure detection of those contexts as faults. Any future experiment should report per-context behavior as descriptive only and use fault-labeled data for actual fault evaluation.

## Signal quality and distributions

Missing percentages below use the full raw row count. Ranges are exact; 5th/50th/95th percentiles are approximate deterministic reservoir-sample quantiles (up to 10,000 readings per signal, Python `random.Random(42)`).

| Signal | Missing | Range | Approx. p05 / p50 / p95 |
| --- | ---: | ---: | ---: |
| Coolant temperature (°C) | 7 (0.0003%) | -1 to 103 | 37 / 90 / 92 |
| Manifold pressure (kPa) | 88 (0.0033%) | 36 to 247 | 98 / 114 / 196 |
| Engine speed (RPM) | 169 (0.0063%) | 0 to 4,315 | 769 / 1,537 / 2,189 |
| Vehicle speed (km/h) | 240 (0.0089%) | 0 to 218 | 0 / 60 / 129 |
| Intake-air temperature (°C) | 321 (0.0119%) | -40 to 150 | -3 / 18 / 41 |
| Mass airflow (g/s) | 402 (0.0149%) | 0 to 129.22 | 6.88 / 18.52 / 54.61 |
| Throttle position (%) | 483 (0.0179%) | 13.7 to 89 | 83.1 / 83.5 / 89 |
| Ambient temperature (°C) | 564 (0.0209%) | -14 to 33 | -7 / 11 / 25 |
| Accelerator pedal D (%) | 654 (0.0243%) | 14.1 to 85.1 | 14.1 / 14.5 / 48.6 |
| Accelerator pedal E (%) | 725 (0.0269%) | 14.1 to 84.3 | 14.5 / 14.5 / 48.6 |

Overall missingness is low, but missing readings are concentrated in the later-updating PID signals (pedal D/E). The preprocessor does not impute: it discards a 10-second window only if an entire signal is absent in that window, and includes each signal's missing fraction as a feature. This preserves missingness rather than fabricating sensor values.

Zero speed occurs in 11.46% of raw readings; RPM and MAF are zero in 3.58% and 3.47%, respectively. These can represent stopped/idle behavior and are retained as values, not treated as missing. The observed intake-air temperature extrema (-40°C and 150°C) and coolant minimum (-1°C) merit source/vehicle plausibility review before physical interpretation. They were retained; this EDA does not declare them errors or remove them. Throttle values are concentrated around 83.5% in the sampled raw distribution, so verify the source PID interpretation before interpreting throttle features as driver demand.

## What this dataset can support

- Unsupervised novelty experiments over its available OBD signals, with train-only scaling and date-grouped holdout. Because there are no verified fault labels, anomaly scores can be inspected or compared across contexts but cannot be scored as fault recall/precision.
- Descriptive trip/context analysis. It does not establish independent vehicle identities or generalization across cars.
- It does **not** support RUL, future-failure prediction, or supervised fault classification. The data has no verified event outcomes or EOL labels.

## Balancing recommendation

Do not apply SMOTE or any class-resampling method to KIT now. SMOTE requires a labeled minority class, and KIT has no fault labels. Its filename context counts are not classes. If a later dataset supplies verified anomaly labels, first split by recording/vehicle to prevent leakage, then consider training-only class weights or resampling as a separate supervised experiment. For KIT-only unsupervised detection, keep the source distribution intact and report that labeled evaluation is unavailable.

## Reproducibility

The raw inventory and known timestamp/missingness audit are recorded in [`data/README.md`](../../../data/README.md). Preprocessed local windows are at `data/automotive_obd/kit_obd/processed/windows_10s.csv.gz`; their generation recipe and split metadata are in `ml/scripts/preprocess_kit_obd.py` and the local `preprocessing_summary.json`. Raw and processed data are gitignored and are not included in this report PR.
