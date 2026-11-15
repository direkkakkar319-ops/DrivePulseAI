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

| Cell | Records | Last cycle | Last SOH | First observed ≤75% | First-crossing proxy rows | EDA note |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Cell1 | 78 | 8,200 | 0.759 | — | 0 | Right-censored under the 75% rule |
| Cell2 | 73 | 7,700 | 0.742 | 7,400 | 70 | Rebounds above threshold at 7,500 and 7,600 |
| Cell3 | 76 | 8,100 | 0.770 | — | 0 | Right-censored under the 75% rule |
| Cell4 | 47 | 5,100 | 0.792 | — | 0 | Right-censored under the 75% rule |
| Cell5 | 46 | 5,000 | 0.620 | 5,000 | 46 | First observed crossing is the final record |
| Cell6 | 46 | 5,000 | 0.790 | — | 0 | Right-censored under the 75% rule |
| Cell7 | 77 | 8,100 | 0.800 | — | 0 | Right-censored under the 75% rule |
| Cell8 | 76 | 8,100 | 0.768 | — | 0 | Right-censored under the 75% rule |

There are **116 non-null first-crossing proxy rows** and 403 blank proxy rows.
These are not confirmed EOL labels. The separate persistent-rule target is
missing for all 519 records because no cell has two consecutive readings at or
below 75%.
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

## EOL rule decision and verification

Literature does not define one universal capacity cutoff: mobile battery EOL
thresholds are use-case dependent and often fall around 70–80% remaining
capacity ([Paarmann et al., 2024](https://doi.org/10.1002/batt.202300594)). The
Oxford release does not specify its own cutoff. The project's 75% value therefore
remains an **exploratory convention**, not a source- or industry-validated rule.

For a stricter event label, this project now requires **two consecutive
characterization records at or below 75%**. This persistence check is a
conservative project screening choice, not a rule established by that literature
or by Oxford. The audit finds **zero confirmed events and zero persistent-rule
RUL labels**: Cell2 has only one below-threshold reading before recovering, and
Cell5's single below-threshold reading is its final record. The former
first-crossing column remains available only to reproduce the explicitly
exploratory trend baseline; it must not be described as confirmed EOL RUL.

Consequently, this dataset has no confirmed EOL target for supervised RUL
training under the selected rule. Use its trajectories for capacity/SOH work or
find a dataset with event labels and follow-up; do not train a supervised RUL
model from the unconfirmed first-crossing proxy as though it were ground truth.

## Independent event count (readiness step 2)

The strict screen leaves **0 confirmed event cells out of 8**, hence **0
confirmed supervised RUL examples**. Even the weaker proxy leaves only Cell2
and Cell5 as event cells. That is insufficient for a useful cross-cell
training/validation/test experiment: cell-level separation is needed because
cycles within one cell are autocorrelated and sharing a cell across splits can
make results optimistic. Battery RUL studies explicitly use cell-level holdouts
for this reason ([Scientific Reports LOCO study](https://www.nature.com/articles/s41598-026-58379-0)).

This is a data/label limitation, not a class imbalance that can be repaired with
SMOTE. Synthetic rows would not add independently observed cell trajectories or
confirmed EOL outcomes. Step 2 therefore fails for this Oxford release; no
supervised RUL model should be fit from it under the selected target rule.

## Evaluation protocol (readiness step 3)

For a future cross-cell RUL claim, assign whole cells to train, validation, and
test before window generation or preprocessing. Fit feature transforms and tune
only on training/validation cells; reserve test cells until the protocol and
model are frozen. Report per-cell MAE/RMSE and the distribution across held-out
cells, with uncertainty intervals where the number of independent cells allows
them. A leave-one-cell-out design is another cell-disjoint option when there are
enough event cells to train meaningfully in each fold. This follows published
Oxford LOCO practice; cycle-level random splits are unsuitable because a cell's
trajectory would appear on both sides of the split
([Scientific Reports LOCO study](https://www.nature.com/articles/s41598-026-58379-0)).

This protocol **cannot be run for confirmed EOL RUL here**: there are zero
confirmed events. Even on the first-crossing proxy, holding out one of two event
cells leaves one event cell for training and one test cell, with no independent
event cell for validation or credible uncertainty estimates. The existing
rolling-origin results are a same-cell trend extrapolation diagnostic against
the proxy; they are not a cell-disjoint evaluation and do not estimate
new-cell performance.

## Baselines, metrics, and uncertainty (readiness step 4)

The historical proxy report already gives per-cell MAE, RMSE, mean error, and
example predictions for the Theil–Sen trend rule. Its 107 prediction origins
are highly correlated observations from just two cells. Treating origins as
independent bootstrap samples would understate uncertainty; bootstrapping two
cells also cannot produce a stable generalization interval. The strict target
has no observations, so neither a benchmark score nor calibrated prediction
uncertainty can be estimated against confirmed EOL.

For a future dataset with enough event cells, compare at least a training-cell
median-RUL predictor and a simple causal capacity-trend extrapolator against the
candidate model using identical cell-held-out folds. Report MAE, RMSE, median
absolute error, signed bias, results for each test cell, and cell-level spread.
If predictions include intervals, report both cell-level coverage and interval
width, calibrated on training/validation cells only. Recent battery evaluation
work likewise calls for censor-aware, battery-disjoint evaluation and warns
against treating cycle rows as independent
([framework paper](https://www.mdpi.com/2313-0105/12/11/484)). These comparisons
are requirements for a later eligible dataset; they are not fabricated for
Oxford's unconfirmed target.

Use cycle-level features available at the prediction cutoff only. Keep all rows
from a cell together. No event cells are confirmed under the selected rule. Do
not claim passenger-EV fleet RUL performance from this eight-cell laboratory
dataset.

An exploratory Theil–Sen capacity-trend baseline was evaluated against the
unconfirmed first-crossing proxy before this stricter rule was added. Its
rolling-origin errors were large and differed by cell; it is retained only as a
historical method-development comparison. Details are in
[`ml/reports/modeling/oxford_rul_trend_baseline.md`](../modeling/oxford_rul_trend_baseline.md).
It does not establish a usable RUL model or validate the proxy target.

## Better-data path (readiness step 5)

The strongest next candidate found in this research pass is the MIT/Stanford/TRI
Severson battery-life dataset. The original *Nature Energy* study reports 124
commercial LFP/graphite cells with cycle lives spanning roughly 150–2,300 cycles
([paper](https://doi.org/10.1038/s41560-019-0356-8)); the research data portal is
[MATR](https://data.matr.io/1/projects/5c48dd2bc625d700019f3204). This offers
many more independent cell trajectories than Oxford and published cycle-life
labels, making it a stronger candidate for battery-cell lifetime method
development.

Before using it, verify the current portal download, exact label/EOL definition,
batch IDs, official train/test split, and data license/redistribution terms.
Its controlled LFP fast-charge experiment is still not passenger-EV fleet data;
it can support only a clearly scoped cell-level benchmark. Do not pool it with
Oxford or use SMOTE. If access or terms do not permit use, seek another public
run-to-EOL battery dataset with explicit labels, cell IDs, and permissible
research use. Oxford itself remains useful for capacity/SOH trajectories, not
confirmed RUL training under the selected rule.
