# Oxford Battery Degradation Dataset 1 — EDA for RUL method development

**Analysis date:** 2026-11-14
**Dataset DOI:** `10.5287/bodleian:KO2kdmYGg`
**Scope:** verify processed cell trajectories and assess whether the existing
exploratory 75%-capacity target is suitable for an RUL model. No model was
trained.

## Preprocessing status

Preprocessing is already implemented in
[`ml/scripts/preprocess_oxford_battery.py`](../../scripts/preprocess_oxford_battery.py).
I reran it from the retained source MAT file. It reproduced a table of **519
characterization records from 8 cells**, with no duplicate cell/cycle keys. The
median spacing is 100 drive cycles; intervals range from 100 to 300 cycles.
The processed CSV and summary are local-only and gitignored.

The follow-up audit is reproducible with
[`ml/scripts/eda_oxford_battery.py`](../../scripts/eda_oxford_battery.py). Its
machine-readable output is
[`oxford_battery_eda.json`](oxford_battery_eda.json).

## Per-cell summary

| Cell | Records | Last cycle | Last SOH | First observed ≤75% | RUL rows | EDA note |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Cell1 | 78 | 8,200 | 0.759 | — | 0 | Right-censored under the 75% rule |
| Cell2 | 73 | 7,700 | 0.742 | 7,400 | 70 | Rebounds above threshold at 7,500 and 7,600 |
| Cell3 | 76 | 8,100 | 0.770 | — | 0 | Right-censored under the 75% rule |
| Cell4 | 47 | 5,100 | 0.792 | — | 0 | Right-censored under the 75% rule |
| Cell5 | 46 | 5,000 | 0.620 | 5,000 | 46 | First observed crossing is the final record |
| Cell6 | 46 | 5,000 | 0.790 | — | 0 | Right-censored under the 75% rule |
| Cell7 | 77 | 8,100 | 0.800 | — | 0 | Right-censored under the 75% rule |
| Cell8 | 76 | 8,100 | 0.768 | — | 0 | Right-censored under the 75% rule |

There are **116 non-null threshold-derived RUL rows** and 403 blank target rows.
The missing labels include all six right-censored cells and Cell2 observations
after its first crossing.

## Target-quality finding

The 75% cutoff is an exploratory choice, not an EOL rule supplied by Oxford. More
critically, the two nominal crossings do not establish a persistent threshold
event:

- **Cell2:** capacity falls from 557.12 mAh (75.8% SOH) at cycle 7,300 to
  501.44 mAh (68.2%) at cycle 7,400, then rises to 562.23 mAh (76.5%) and
  558.63 mAh (76.0%) at the next two characterizations. The 7,400 source curve
  has 2,442 samples and spans 0.02824 days, versus 2,709–2,738 samples and
  0.03134–0.03167 days for the neighboring 7,100, 7,300, and 7,500 records.
  This appears to be a transient or shortened characterization and needs
  interpretation before being treated as EOL.
- **Cell5:** its first below-threshold measurement is at cycle 5,000, the final
  available record. There is no later observation to verify persistence.

No cell has two consecutive below-threshold characterization records beginning
at its first crossing. That two-record rule is only a diagnostic check, not an
official EOL definition, but it shows that the current first-passage labels are
not robustly confirmed. The derived RUL for Cell2 may treat one anomalous
measurement as the endpoint; Cell5 has no post-crossing follow-up.

Capacity is not perfectly monotone. Cell2 has 13 increases between adjacent
records, including a 60.80 mAh rebound after cycle 7,400. Other cells have
smaller rebounds. Do not smooth or discard these points without a documented
measurement-quality rule.

## Modeling readiness

**Preprocessing is complete; the data EDA is complete for this stage; a
defensible supervised RUL target is not yet established.** Only two cells have
any first-passage RUL rows, and neither has a confirmed persistent event under
the diagnostic check above. Randomly splitting the 116 rows would leak cell
trajectories. A cell-disjoint test with one event cell held out would leave only
one event cell for fitting and would not support a meaningful performance
claim. SMOTE would not fix the event count, censoring, or cell-level dependence.

Before fitting an RUL regressor, decide whether to:

1. retain the **first observed 75% crossing** as a clearly exploratory proxy and
   build a demonstration with no generalization claim; or
2. define a defensible persistent EOL rule and confirm that the source records
   support it; if no events remain, stop RUL training on this release and use it
   for capacity/SOH experiments instead.

Use cycle-level features available at the prediction cutoff only. Keep all rows
from a cell together, and report the two event cells separately. Do not claim
passenger-EV fleet RUL performance from this eight-cell laboratory dataset.
