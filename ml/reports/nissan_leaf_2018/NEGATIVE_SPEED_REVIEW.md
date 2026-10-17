# Negative-speed investigation and fixed-split policy comparison

Purpose: investigate unavailable-looking telemetry and quantify alternative preparation policies. Existing source files, split assignments and prepared artifacts were not modified. No models were trained, no new training records or fault labels were invented, and no alternative feature dataset was exported.

## Exact values, frequency and trips

All **266,235** negative-speed readings are exactly **-1 km/h**, representing **11.465244%** of the 2,322,105 raw rows. There are **32 affected trips**, of which **26 have -1 for every row**. Full counts, dates, longest runs, gear context and other-channel variability are in [negative_trips.csv](tables/negative_speed/negative_trips.csv).

| Trip | split | rows | negative_rows | negative_pct | original_retained_rows |
| --- | --- | --- | --- | --- | --- |
| 10 | train | 83329 | 83329 | 100.0 | 0 |
| 146 | train | 14285 | 3 | 0.021001050052502624 | 14267 |
| 153 | validation | 12400 | 2 | 0.016129032258064516 | 12391 |
| 154 | validation | 14760 | 12 | 0.08130081300813008 | 14706 |
| 175 | validation | 16958 | 2 | 0.011793843613633684 | 16949 |
| 202 | test | 1462 | 2 | 0.13679890560875513 | 1460 |
| 210 | test | 13772 | 100 | 0.7261109497531223 | 13672 |
| 211 | test | 6760 | 6760 | 100.0 | 0 |
| 212 | test | 3514 | 3514 | 100.0 | 0 |
| 213 | test | 1971 | 1971 | 100.0 | 0 |
| 214 | test | 1877 | 1877 | 100.0 | 0 |
| 215 | test | 5839 | 5839 | 100.0 | 0 |
| 216 | test | 6041 | 6041 | 100.0 | 0 |
| 217 | test | 201 | 201 | 100.0 | 0 |
| 218 | test | 22298 | 22298 | 100.0 | 0 |
| 219 | test | 14261 | 14261 | 100.0 | 0 |
| 220 | test | 4407 | 4407 | 100.0 | 0 |
| 221 | test | 10528 | 10528 | 100.0 | 0 |
| 222 | test | 742 | 742 | 100.0 | 0 |
| 223 | test | 1751 | 1751 | 100.0 | 0 |
| 224 | test | 14028 | 14028 | 100.0 | 0 |
| 225 | test | 774 | 774 | 100.0 | 0 |
| 226 | test | 10782 | 10782 | 100.0 | 0 |
| 227 | test | 5452 | 5452 | 100.0 | 0 |
| 228 | test | 4296 | 4296 | 100.0 | 0 |
| 229 | test | 18434 | 18434 | 100.0 | 0 |
| 230 | test | 3077 | 3077 | 100.0 | 0 |
| 231 | test | 15859 | 15859 | 100.0 | 0 |
| 232 | test | 390 | 390 | 100.0 | 0 |
| 233 | test | 7344 | 7344 | 100.0 | 0 |
| 234 | test | 9185 | 9185 | 100.0 | 0 |
| 235 | test | 12974 | 12974 | 100.0 | 0 |

## Meaning: reverse gear versus unavailable measurement

The parameter workbook documents speed in km/h but does **not** define negative speed or a -1 speed sentinel. Gear codes are 0 not read, 1 Park, 2 Reverse, 3 Neutral, 4 Drive and 7 B/Eco; Gear=-1 is undocumented. Gear polling is documented at 100 seconds and speed at 1 second, so a same-row gear code may be stale.

| Gear | documented_meaning | rows |
| --- | --- | --- |
| -1 | Undocumented | 83355 |
| 1 | Park | 9159 |
| 2 | Reverse | 1093 |
| 3 | Neutral | 341 |
| 4 | Drive | 146035 |
| 7 | B/Eco | 26252 |

Only 1,093 of the negative readings coincide with reverse gear. Most coincide with Drive/B-Eco or an undocumented gear code. Therefore treating -1 as reverse velocity or taking its absolute value is not justified. Even reverse-code coincidences cannot validate a signed-speed convention given slow gear polling.

**New evidence:** 266,214 negative-speed rows simultaneously report RPM=-1 and Torque=-1. In the test split, 182,885 of 182,887 negative-speed rows have both values. This strongly suggests unavailable/failed acquisition for a group of drivetrain channels, rather than genuine constant reverse motion. It does **not** identify the exact logger defect or prove a manufacturer sentinel convention. Motor temperature also equals -1 in 66,540 affected test rows. Actual physical speed remains unknown.

Battery voltage, SOC and pack temperature still vary in many affected trips; their exact ranges/cardinalities are in [other_channels.csv](tables/negative_speed/other_channels.csv) and the per-trip table. Unavailable drivetrain fields do not prove every battery observation is invalid. Trip 232's pack temperatures also trigger the existing sentinel review, so it is not automatically rescued.

Matched-export observations: `{'raw_negative_rows': 266235, 'matched_processed_rows': 107, 'not_present_in_processed': 266128, 'matched_processed_speed_counts': {'0.0': 101, '124.0': 1, '110.0': 1, '116.0': 1, '127.0': 1, '121.0': 1, '123.0': 1}}`. These are evidence of export/preprocessing differences, not documentation that changing -1 to zero is physically correct.

## Why whole trips disappeared

There is no rule deleting an entire trip because it contains one negative reading. `audit_trip` sets a row-level `speed_negative` flag; the default six-feature eligibility mask blocks that row. A trip with all Speed=-1 therefore contributes zero rows. All observations remain in the original CSV and prepared row ledger, with their trip assignments and quality flags.

Temperature windows use the same six-feature eligibility and reject any interval containing an excluded row, including the full interval through the target. Consequently even a few unavailable readings can reject more windows than rows. This is a conservative validity gate, not a fault diagnosis. The coupling of all task views to the same feature mask is a limitation: one missing drivetrain channel need not block a battery-only experiment.

Training, validation and test use exactly the same policy. Training has 83,332 negative-speed rows, validation 16, test 182,887. Their total row exclusions are 88,655 / 261 / 182,887 respectively because other rules also apply. Training loses four complete trips under all rules (one is entirely negative-speed); test loses 25 complete trips. Negative-speed and all-exclusion counts must not be added because they overlap.

## Alternative-policy comparison

All policies retain the original 142/34/51 whole-trip chronological assignments, embargo, source timestamps, segment boundaries, target definition and other quality rules. Cross-split rounded-feature screening is rerun on each policy's actual feature set, and robust scaling statistics are recomputed from that policy's retained **training rows only**. Full-source hash checks and ledger hash checks precede the analysis. Existing-six-feature masks reproduce exactly; its sequence counts come from the already-validated preparation artifacts. Alternative windows are generated in memory with the existing safe window builder, counted and discarded, not published as training datasets.

- **existing_six_features:** current Speed, Torque, Motor_Temp, voltage, pack-1 temperature and SOC.
- **omit_speed_only_diagnostic:** five features, removing Speed only. This is a numerical sensitivity check, **not recommended**: it still treats many Torque=-1 and questionable motor-temperature values as ordinary measurements.
- **battery_only_conditional:** voltage, pack-1 temperature and SOC. This omits Speed, RPM, Torque and motor temperature, avoiding the correlated acquisition issue without guessing missing values. Other existing conservative quality rules remain. It narrows anomaly scope to battery telemetry; driving/idle/charging state cannot be inferred reliably for unknown-speed rows.

| policy | split | features | feature_rows | temperature_windows | trips_with_rows | recorded_days | negative_speed_rows_retained | repeat_excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| existing_six_features | train | 6 | 1540563 | 35632 | 138 | 73 | 0 | 0 |
| existing_six_features | validation | 6 | 351161 | 6753 | 34 | 19 | 0 | 0 |
| existing_six_features | test | 6 | 158578 | 2809 | 26 | 13 | 0 | 0 |
| omit_speed_only_diagnostic | train | 5 | 1623891 | 37753 | 139 | 74 | 83328 | 0 |
| omit_speed_only_diagnostic | validation | 5 | 351161 | 6753 | 34 | 19 | 0 | 0 |
| omit_speed_only_diagnostic | test | 5 | 341075 | 4624 | 50 | 25 | 182497 | 0 |
| battery_only_conditional | train | 3 | 1623891 | 37753 | 139 | 74 | 83328 | 0 |
| battery_only_conditional | validation | 3 | 351087 | 6595 | 34 | 19 | 0 | 74 |
| battery_only_conditional | test | 3 | 340986 | 4514 | 50 | 25 | 182484 | 89 |

“Feature rows” are eligible observations; “temperature windows” are sequence examples. A retained negative-speed row uses only the alternative policy's input columns; -1 speed is not converted to a valid speed measurement. Counts do not certify sensor accuracy or healthy behavior. Fewer input dimensions can increase duplicate-screen exclusions; those counts are visible. Full per-trip effects: [policy_trip_counts.csv](tables/negative_speed/policy_trip_counts.csv).

## Can more usable test observations be preserved without leakage?

**Yes, conditionally for a battery-only experiment**, without recovering the unknown vehicle speed. This requires a task-specific feature mask rather than relaxing validity for the original six-feature task. Keep unavailable signals in audit metadata, never replace them with zero or absolute values. If an experiment requires speed/load, missing-aware inputs would need separately justified per-channel availability masks and training-only imputation; that policy has not been implemented or counted here because the drivetrain issue affects more than speed.

The split dates are unchanged; whole trips remain exclusive. Window inputs end at the anchor, all input/target rows stay within one original safe segment, and no future values fill earlier measurements. Scalers use training only. A reduced feature set still needs all existing duplicate and window checks, as used here. No cross-source merging or raw/preprocessed leakage is introduced.

**Evaluation limitation:** the test-set exclusion pattern motivated this investigation. Even with computationally leakage-safe preparation, repeatedly choosing policies after inspecting test behavior makes this an explored holdout. Freeze and document the policy before evaluating model performance, and obtain a fresh independent chronological/vehicle holdout for strong confirmatory claims. No model scores were examined here.

## Recommendation and unresolved questions

Preserve the existing prepared release. Prefer a separately versioned three-channel battery-only view for logged-temperature forecasting and narrowly scoped battery-pattern experiments; review its remaining sentinel and physical-quality limitations before training. Do not simply enable the five-channel speed-omitted view. Seek researcher confirmation of the sustained Speed/RPM/Torque=-1 episodes, raw logger availability flags, and whether motor temperature=-1 is an unavailable code. Verify sensor freshness/calibration before asserting real battery faults or physical temperature prediction.

## Reproduce and outputs

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/review_negative_speed.py
```

The script reuses the current preparation summary and audited ledger. Outputs under `tables/negative_speed/`: `negative_values.csv`, `negative_trips.csv`, `gear_context.csv`, `other_channels.csv`, `processed_comparison.json`, `policy_comparison.csv`, `policy_trip_counts.csv`, `training_transformers_comparison.json`, and `review_manifest.json`. The transformer comparison JSON records per-policy training-only medians/scales, not trained models. The manifest hashes every output, the source preparation manifest and this script. No production pipeline defaults, prepared datasets, source records or splits were changed.
