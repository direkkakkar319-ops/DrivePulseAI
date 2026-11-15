# Oxford RUL method comparison

**Run date:** 2026-11-15
**Dataset DOI:** `10.5287/bodleian:KO2kdmYGg`
**Target:** unconfirmed first-observed crossing of 75% of each cell's first measured capacity

## Decision

The development cutoffs selected an exponential capacity-fade trend with a
2,000-cycle lookback. It reduced macro-cell MAE on the later temporal cutoffs
from 1,590 cycles for the existing Theil–Sen/1,000-cycle baseline to 1,368
cycles (about 14%). Keep it as an **experimental candidate** in
`ExponentialCapacityTrendRUL`; retain Theil–Sen as the existing default. The
result is not strong or independent enough to replace the default or describe
the model as ready for RUL use.

| Method | Development macro-cell MAE | Later-cutoff macro-cell MAE | Later-cutoff coverage |
| --- | ---: | ---: | ---: |
| Theil–Sen, 1,000-cycle lookback (existing baseline) | 1,131 | 1,590 | 95.3% |
| Exponential trend, 2,000-cycle lookback (selected candidate) | 1,108 | 1,368 | 100% |

Later-cutoff scores by cell:

| Cell | Theil–Sen baseline MAE | Exponential candidate MAE |
| --- | ---: | ---: |
| Cell2 | 1,012 | 561 |
| Cell5 | 2,168 | 2,175 |

The selected model improves the Cell2 proxy score and leaves Cell5's already
large error essentially unchanged. Another candidate can score better on the
temporal holdout, but choosing among candidates using that holdout would tune to
the evaluation data. The candidate was therefore selected only on the earlier
development cutoffs.

## Comparison protocol

Compared ordinary least-squares linear, Theil–Sen robust linear,
recency-weighted linear, and exponential capacity trends with fixed lookbacks of
500, 1,000, 2,000 cycles, or all available history. Fits use only records at or
before each prediction cutoff and require four observations. For each of the
two cells with proxy crossings, origins at or before 60% of the proxy crossing
cycle form the development set; later origins form a temporal holdout. The
selection score is mean per-cell development MAE, with missing development
predictions counted as zero-RUL estimates; candidates must cover at least 75%
of development origins. The current Theil–Sen/1,000-cycle rule is included as a
reference candidate.

Reproduce with `./.venv/bin/python -m ml.scripts.compare_oxford_rul_methods`
after running `ml/scripts/preprocess_oxford_battery.py`. The command writes the
full candidate metrics and per-origin scores to
[`oxford_rul_method_comparison.json`](oxford_rul_method_comparison.json).

## Limits and next step

- The two-reading 75% screen confirms zero EOL events in this Oxford release.
  All scores here use the ambiguous first-crossing proxy; they are not errors
  against confirmed RUL labels.
- There are only two proxy-event cells. Temporal cutoffs within a cell are
  correlated, and this is not a cell-disjoint evaluation.
- Cell5's temporal holdout MAE remains about 2,175 cycles. The apparent overall
  gain is mainly Cell2-specific and may reflect its transient threshold
  crossing and rebound.
- The estimator gives a point prediction only. Two cells cannot support a
  credible uncertainty interval or an unseen-cell performance claim.
- Keep the exponential implementation experimental and do not change the
  default model until confirmed EOL labels and additional independent cells are
  available. On a suitable dataset, repeat cell-disjoint evaluation and report
  per-cell error and calibrated uncertainty.
