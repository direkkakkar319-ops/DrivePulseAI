# Oxford capacity-trend RUL baseline

**Run date:** 2026-11-14
**Dataset DOI:** `10.5287/bodleian:KO2kdmYGg`
**Model:** local Theil–Sen robust linear trend extrapolation

**Status:** historical exploratory baseline against an unconfirmed first-crossing
proxy. A later two-consecutive-reading screen confirms no EOL events in this
release; the metrics below are not validation against confirmed EOL RUL.

## Why this model

Only two cells have first-observed crossings of the exploratory 75%-capacity
threshold, and Cell2's crossing is followed by a rebound. A learned pooled model
such as XGBoost would have too few independent event cells to learn or validate
cross-cell RUL. Theil–Sen was chosen as a transparent method-development
baseline: for each prediction cutoff, it fits a robust slope to that cell's
recent capacity observations and extrapolates the slope to that cell's threshold.
It uses a 1,000-drive-cycle lookback and requires at least four observed points.

The procedure does not learn a transferable global model. It must be evaluated
as an exploratory per-cell trend rule, not as a passenger-EV model.

## Evaluation protocol

At each observed cycle strictly before the first measured threshold crossing,
the estimator uses only that cell's observations at or before the cutoff. The
observed target is `first_crossing_cycle - cutoff_cycle`. Origins with fewer than
four observations in the lookback or a non-declining fitted trend are skipped.
These are rolling origins from the same two cells, not independent test cells.
This is a same-cell trend diagnostic only. It must not be reported as a
cell-disjoint generalization evaluation; the later two-reading target audit
finds no confirmed event cells, so confirmed-EOL cross-cell evaluation cannot
be performed on this release.

## Results

| Cell | Origins | MAE (cycles) | RMSE (cycles) | Mean error (cycles) |
| --- | ---: | ---: | ---: | ---: |
| Cell2 | 65 | 1,426 | 2,819 | -476 |
| Cell5 | 42 | 1,408 | 1,566 | +1,151 |
| Pooled rolling origins | 107 | 1,419 | 2,406 | +163 |

The predictions are poor and differ substantially by cell. At cycle 7,300,
Cell2's predicted RUL is about 518 cycles versus 100 cycles to its first
observed crossing. At cycle 4,800, Cell5's prediction is about 2,968 cycles
versus 200 cycles to its endpoint crossing. The pooled metrics summarize these
correlated origins only; they do not estimate performance on a new cell.

No confidence interval or prediction interval is reported: the 107 origins are
repeated points from two cells, not independent units, and two cells are
insufficient for stable cell-level uncertainty estimation. The Theil–Sen rule
was not compared with a train-cell median baseline; that comparison requires
independent training cells and is not validly estimable from this two-cell
proxy setup. On a future eligible dataset, compare against a training-cell
median-RUL predictor and report per-cell MAE, RMSE, median absolute error, signed
bias, cell-level spread, and prediction-interval coverage plus width. Do not
bootstrap rolling origins as if they were independent cells.

Full per-origin results are in
[`oxford_rul_trend_baseline.json`](oxford_rul_trend_baseline.json). Reproduce
with `./.venv/bin/python -m ml.scripts.evaluate_oxford_rul_trend` after running
the Oxford preprocessing script.

## Interpretation and limits

- The baseline is **not accurate enough for RUL use**. The results support
  rejecting this simple trend extrapolator as a usable estimator in its current
  form.
- The target itself remains ambiguous: Cell2's first crossing is transient, and
  Cell5 has no post-crossing follow-up. Errors against these targets are not a
  reliable assessment of true EOL RUL.
- Six cells are right-censored at the chosen threshold. They cannot be treated as
  exact RUL examples in ordinary regression.
- No cell-disjoint train/validation/test evaluation or passenger-EV generalization
  claim is supported. SMOTE would not add independent cell trajectories or fix
  censoring.
- The model is a reproducible method-development baseline only; it is not
  integrated into the app or API and should not be used for vehicle advice.
