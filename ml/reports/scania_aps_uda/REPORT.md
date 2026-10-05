# Scania APS EDA by UDA

Scope: heavy-truck APS component failure classification, not passenger-car diagnosis.
`pos` denotes a specified APS component failure; `neg` denotes other component failures, not healthy trucks.
Local supplied files are structurally complete; external release checksums are unverified.
Features are 170 anonymized counters/histogram bins. No established vehicle IDs, trip IDs, timeline, or RUL labels exist.

## Procedure and split contract

Raw files and earlier EDA artifacts are untouched. Copyright preambles are skipped by locating `class,`; `na` becomes missing.
The supplied test set is preserved. A seeded five-fold stratified group splitter provides approximately 80/20 train/validation;
predictor rows matching at three significant digits stay in one partition. The manifest uses zero-based data row numbers.
Fingerprints exclude targets; coarse matches are candidate screens, not proof of identical events. Hash collision risk is nonzero.
This screen cannot establish absence of general near duplicates or independent vehicles; vehicle-held-out performance is unverified.

Detailed distributions, missingness, constants and correlations use training only. Test labels are used for final evaluation,
apart from basic integrity counts. No outliers or raw rows are deleted. Confirmed duplicates would require a reviewed policy;
conflicting training labels or cross-split exact/coarse overlap block test scoring.

Median imputation and missingness indicators fit on training only. All-null/constant predictors are excluded using training only.
High-missingness features and outliers are retained in this baseline; there is no evidence for arbitrary deletion.
No target imputation, oversampling, scaling, or future observations are used. Tree models do not require scaling.
Training-only class weighting addresses imbalance. The fixed random-forest baseline uses 100 trees and minimum leaf size 2.
The threshold minimizes validation challenge cost (10 per false positive, 500 per missed APS failure), as specified in the local description.
The fitted pipeline is frozen for a single test evaluation; it is not refit using validation and no test-driven tuning is performed.
This baseline is exploratory, not a deployed or production-qualified model; no trained model artifact is published.

## Findings

Training/validation/test contain 48,000/12,000/16,000 rows.
The supplied training set has 1,000 APS-positive cases among 60,000 rows.
Training feature `br_000` is missing in 82.0% of rows;
constant features excluded from this baseline: ['cd_000'].
There are 0 exact cross-split predictor hash matches,
but 2,362 distinct coarse matches.
`near_duplicate_examples.csv` gives up to 25 candidate pairs with zero-based source row numbers and unrounded differences.
Test scoring is blocked pending overlap investigation.
Validation recall is 96.5%, precision 34.6%,
and average precision 0.869. These are threshold-selection results, not independent test performance.

See `training_feature_profile.csv` for missingness, percentiles and constants, `training_missingness_by_class.csv`
for label-conditional missingness, and `training_high_correlations.csv` for absolute Spearman correlations >= 0.95.
Plots show imbalance, missingness and log-transformed distributions. Histograms describe counters, not physical sensor units.
`summary.json` records source checksums, software versions, leakage screens, partition counts and evaluation metrics.

Leakage screen: `{"training_full_row_duplicates": 0, "test_full_row_duplicates": 0, "training_predictor_duplicate_rows": 0, "test_predictor_duplicate_rows": 0, "cross_split_distinct_predictor_hashes": 0, "cross_split_three_significant_digit_candidates": 2362, "training_conflicting_label_groups": 0}`.

Baseline results: `{"validation": {"average_precision": 0.8693589736108308, "precision": 0.3464991023339318, "recall": 0.965, "tn": 11436, "fp": 364, "fn": 7, "tp": 193, "challenge_cost": 7140}, "threshold": 0.059513986532193586, "test_evaluation_blocked": true}`.

## Next decisions

Review missingness and correlated histogram bins before changing features. Compare preprocessing/model alternatives using
training cross-validation only in a future experiment; any test result must not become a tuning signal.
Obtain vehicle grouping, collection-time definitions and feature availability documentation before claiming event independence
or excluding outcome-derived leakage. Anonymization prevents certifying predictor availability at diagnosis time.
Obtain separately labeled passenger-car data with compatible OBD signals for DrivePulseAI passenger-car classification.

## Reproduce

From the repository root: `MPLCONFIGDIR=/tmp/aps-mpl python ml/notebooks/eda_scania_aps_uda.py`.
Requires pandas, NumPy, scikit-learn and Matplotlib. Optional `--raw` and `--output` override directories.
Reproduction overwrites this analysis's artifacts in the chosen output directory.
Do not repeatedly alter the experiment based on held-out results; overlap remediation requires a separately reviewed policy.
