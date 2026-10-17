"""Build the evidence-linked readiness report from reproducible descriptive outputs."""

from __future__ import annotations

import json

import pandas as pd
from acquire import BASE
from build_report import md


def write_report(metrics: dict, inventory: pd.DataFrame) -> None:
    """Generate a report without selecting algorithms or claiming fault validation."""
    tables = BASE / "tables/readiness"
    assoc = pd.read_csv(tables / "soh_associations.csv")
    main_assoc = assoc[
        assoc.level.isin(
            [
                "telemetry_rows",
                "trip_medians",
                "recorded_day_medians",
                "successive_recorded_day_differences",
            ]
        )
        & assoc.method.eq("pearson")
    ]
    dimensions = pd.DataFrame(
        [
            {
                "version": v,
                **{
                    k: metrics[v][k]
                    for k in [
                        "rows",
                        "columns",
                        "trip_ids",
                        "recorded_days",
                        "start_utc",
                        "end_utc",
                    ]
                },
            }
            for v in ("raw", "processed")
        ]
    )
    soh = pd.DataFrame(
        [
            {
                "version": v,
                **{
                    k: metrics[v][k]
                    for k in [
                        "soh_min",
                        "soh_max",
                        "soh_unique",
                        "soh_first",
                        "soh_last",
                        "soh_missing",
                        "soh_zero",
                        "soh_outside_0_100",
                        "soh_on_0_01_grid_fraction",
                        "soh_increases_all_adjacent",
                        "soh_decreases_all_adjacent",
                        "soh_increases_within_trip",
                        "soh_decreases_within_trip",
                        "soh_equal_within_trip_pct",
                        "trips_with_soh_changes",
                        "daily_median_soh_increases",
                    ]
                },
            }
            for v in ("raw", "processed")
        ]
    )
    time = pd.DataFrame(
        [
            {
                "version": v,
                **{
                    k: value
                    for k, value in metrics[v].items()
                    if k.startswith("within_trip")
                    or k
                    in [
                        "global_reversals",
                        "trip_blocks",
                        "reused_noncontiguous_trip_ids",
                        "median_within_trip_positive_interval_s",
                        "timestamp_parse_failures",
                    ]
                },
            }
            for v in ("raw", "processed")
        ]
    )
    derived = pd.DataFrame(
        [
            {"version": v, **row}
            for v in ("raw", "processed")
            for row in metrics[v]["derived_checks"]
        ]
    )
    counts = pd.DataFrame(
        [{"version": v, **row} for v, row in metrics["inventory"].items()]
    )
    overview = {
        v: json.loads((BASE / f"tables/{v}/overview.json").read_text())
        for v in ("raw", "processed")
    }
    quality = pd.DataFrame(
        [
            {
                "version": v,
                "missing_cells": overview[v]["total_missing_cells"],
                "exact_duplicate_rows": overview[v]["duplicates"]["exact_full_rows"],
                "duplicate_timestamps": overview[v]["duplicates"][
                    "duplicate_timestamp_rows"
                ],
            }
            for v in overview
        ]
    )
    readiness = pd.DataFrame(
        [
            {
                "Task": "A — Anomaly detection",
                "Readiness": "Conditionally ready — further verification required",
                "Intended output": "Unusual telemetry relative to observed operating context",
                "Targets available": "No verified normal/fault reference",
                "Prototype": "Yes, after unit/sign/formula and reference-set review",
                "Real-world validation": "No; needs adjudicated events and independent vehicles",
            },
            {
                "Task": "B — Fault classification",
                "Readiness": "Not ready — essential evidence missing",
                "Intended output": "Specific confirmed fault category",
                "Targets available": "No verified fault categories or DTC outcomes",
                "Prototype": "No evidence-based supervised fault experiment from this dataset alone",
                "Real-world validation": "No; needs diagnostic labels, normal controls, event times and independent vehicles",
            },
            {
                "Task": "C — Battery health estimation",
                "Readiness": "Conditionally ready — further verification required",
                "Intended output": "Reported-SOH monitoring; exploratory estimation/forecasting",
                "Targets available": "LBC-reported SOH, not independently measured capacity",
                "Prototype": "Monitoring ready for controlled experimentation; prediction conditional",
                "Real-world validation": "No general battery-health claim; needs independent capacity tests and vehicles",
            },
            {
                "Task": "D — Predictive maintenance",
                "Readiness": "Not ready — essential evidence missing",
                "Intended output": "Future failure, service requirement or remaining life",
                "Targets available": "No failure/service/end-of-life outcomes",
                "Prototype": "No validated maintenance prediction; telemetry forecasting is a separate task",
                "Real-world validation": "No; needs longitudinal event-linked fleet histories",
            },
        ]
    )
    readiness.to_csv(tables / "task_readiness.csv", index=False)
    inventory_columns = [
        "source_dataset",
        "column",
        "dtype",
        "description",
        "unit",
        "missing_pct",
        "measurement_class",
        "potential_input",
        "potential_target",
        "possible_target_leakage",
        "redundancy",
        "requires_investigation",
    ]
    text = f"""# Nissan Leaf 2018 — ML readiness assessment

Purpose: assess what existing evidence supports before model selection. No models, synthetic records, artificial fault labels, cleaning, imputation, scaling, engineered model features, or train/test splits were created. Analysis aggregates and differences are descriptive statistics only.

## 1. Executive summary

**Verified:** Both original CSVs match their acquisition SHA-256 checksums. Selected-column scans independently verify all row counts, time ordering, trip counts and three derived relationships. Existing complete EDA tables provide every-column schema, missingness, variability and distributions. Source files remain unchanged.

**Assessment:** This is a single-vehicle observational telemetry study, not a labeled diagnostic or run-to-failure dataset. Millions of readings do not provide millions of independent battery-health outcomes. Reported SOH can be displayed and monitored. Anomaly experiments and SOH prediction are conditional; fault classification and predictive maintenance lack essential outcomes. Experimental feasibility does not establish production readiness.

**Evidence labels:** “Verified” means observed in the files or explicit documentation. “Statistical observation” describes association without causation. “Hypothesis” requires independent confirmation. “Recommendation” specifies future work, not work performed here. “Unknown” means the available material does not settle it.

## 2. Verified dataset characteristics

{md(dimensions)}

{md(quality)}

Source: [official institutional dataset page](https://ubilab.mpu.edu.mo/data.html); local [source and usage findings](metadata/SOURCES.md), [download manifest](metadata/download_manifest.json), [parameter dictionary](metadata/parameter_dictionary_extracted.csv), [complete EDA](EDA_REPORT.md). No explicit open-data license was identified; citation request is not an unrestricted redistribution license.

Preprocessed storage: 32 numeric columns, semantically 3 identifiers, 1 timestamp, 2 categorical status fields and 26 other numeric columns (including derived values). Raw storage: 90 numeric and 2 text columns; semantic categories: 5 identifiers/export indices, 3 timestamp representations, 20 categorical statuses, 44 measured/undocumented numeric and 20 derived numeric fields. SOH is recorded telemetry and a possible task target, not a verified fault label. Seven processed Driver_ID codes do not establish seven vehicles. No VIN column is present. Published scope is one 2018 Leaf; independent vehicle generalization cannot be measured here.

The raw first CSV header is blank; pandas exposes it as `Unnamed: 0.1` alongside the literal `Unnamed: 0`. The inventory preserves both original and parsed names. No duplicate literal header names were found by the existing EDA. “Raw” already includes derived/calendar/accumulated fields and should not be assumed to be an untouched CAN capture.

## 3. Complete feature inventory

{md(counts)}

Counts are **source-column entries**, not unique selected features. “Conditional candidate” excludes identifiers, timestamps, wholly empty and constant fields; it is a deliberately broad review pool, not an approved input list. Odometer remains in that pool to make its shortcut risk explicit. The ten potential targets per version are recorded SOH plus nine possible future-telemetry quantities; none is a failure or maintenance target. Choice of horizon and target would change input eligibility. Unknown descriptions/units stay Unknown.

Complete machine-readable inventory: [feature_inventory.csv](tables/readiness/feature_inventory.csv). The following includes every source-column entry and its task-dependent caveats.

{md(inventory[inventory_columns])}

## 4. SOH and battery degradation findings

{md(soh)}

Counts of increases/decreases use adjacent source rows with finite reported values, separated into within-trip and all-adjacent comparisons; they are not counts of physical battery recovery/degradation events. `soh_on_0_01_grid_fraction` measures proximity to a 0.01 percentage-point grid at absolute tolerance 1e-7 after multiplying by 100. Value frequencies and every observed transition are saved in `tables/readiness/*_soh_values.csv` and `*_soh_changes.csv`. Trip ranges and daily medians are in `*_trip_soh.csv` and `*_daily_soh.csv`.

**Documentation:** The workbook associates SOH with ECU `0x79B (LBC)`, the Li-ion battery controller. This supports calling it controller/BMS-reported SOH, not laboratory-measured remaining capacity. SOH polling frequency is undocumented. Repeated telemetry values cannot reveal the controller's internal estimation/update schedule.

**Interpretation:** Use the observed unique values, near-complete adjacent equality and changing-trip counts above to assess effective outcome diversity. These readings behave much more like slowly changing vehicle state than independent labels per row. Temporary upward steps are observed where the increase counts are positive; calibration, operating conditions and estimator behavior are plausible hypotheses, not established causes. The data cannot distinguish estimator recalibration from true capacity change.

**Important range correction:** The often-quoted 92.63–96.46% range applies only to the processed file. Raw contains 2,853 zero readings, 2,247 missing readings and positive values down to 92.12%. Zero readings are suspicious in this context, not confirmed zero remaining battery health. They remain in the all-row descriptive calculations. Raw has 84 distinct nonmissing values (83 positive); processed has 56. All nonmissing values lie on a 0.01-point grid. This supports quantized reporting, but not a known periodic update schedule.

Processed SOH changes are confined to Trip 77 (93.89–93.96%) and Trip 195 (92.67–92.68%). Its 183 within-trip upward steps coexist with zero increases in recorded-day median SOH: local oscillation is not evidence of long-term recovery. Raw has 142 within-trip increases and two increases between recorded-day medians. The two exports cannot be assumed to preserve identical update behavior: existing matched-row checks find 128 changed finite SOH values and 2,201 raw-missing SOH values present in the processed counterpart.

AHr, Hx and GIDs are battery capacity/health/energy proxies in the raw documentation. kWh_Remaining depends on SOC and capacity assumptions; those fields could shortcut a SOH task. Do not present SOH-from-SOH or a capacity-proxy reconstruction as independent battery diagnosis. No capacity-test truth was found. A focused raw formula audit tests `kWh_Remaining = SOC * AHr * 0.0036` (percent SOC, Ah and nominal 360 V): {metrics["raw"].get("remaining_energy_formula")}. This verifies or rejects that numerical relationship without proving independently measured energy or capacity. Raw row-level correlations with AHr/Hx/GIDs are included in the association table; GIDs has 96.36% missingness, so its pairwise subset is highly selected.

![Raw SOH and shortcuts](figures/readiness/raw_soh_shortcuts.png)

![Processed SOH and shortcuts](figures/readiness/processed_soh_shortcuts.png)

## 5. Mileage shortcut investigation

The following uses Pearson correlations; the complete table also contains Spearman rank correlations and within-month daily comparisons. All rows are retained, with pairwise nonmissing finite values contributing to each correlation; daily/trip medians give equal weight to recorded days/trips. No statistical significance tests assuming independent rows, regression fits or models were used.

{md(main_assoc)}

Raw odometer–time correlation: rows **{metrics["raw"]["row_odometer_time_pearson"]:.6f}**, recorded-day medians **{metrics["raw"]["daily_odometer_time_pearson"]:.6f}**. Preprocessed: rows **{metrics["processed"]["row_odometer_time_pearson"]:.6f}**, recorded-day medians **{metrics["processed"]["daily_odometer_time_pearson"]:.6f}**.

**Statistical observation:** Compare the SOH–odometer and SOH–time associations above against temperature, SOC, voltage and current. Successive-recorded-day differences remove a shared level trend, but unequal calendar gaps remain; these are not per-day degradation rates. Within-month results can have very small samples or constant SOH (undefined correlations are blank). None of these comparisons identifies a causal aging mechanism or proves how a future model will behave.

**Observed sensitivity:** Processed SOH–odometer Pearson r is -0.950806 across rows and -0.948889 across 82 recorded-day medians; SOH–time is -0.933874 and -0.933316 respectively. Daily temperature r is only +0.080330. Successive-day SOH-change versus odometer-change correlation is -0.408343, much weaker than the level relationship. Thus shared time progression is a strong competing explanation, although the descriptive analysis does not isolate a causal contribution of mileage.

Raw all-row Pearson results are severely sensitive to suspect values: odometer spans -1 to 16,763,904 km, and SOH includes zeros. Its SOH–odometer Pearson r is -0.019782 while Spearman is -0.992200; daily-median Pearson is -0.901904. Raw SOH–time Pearson is -0.328017 versus Spearman -0.993081. This large contrast is a data-quality sensitivity finding, not evidence that mileage has no relationship with SOH. No readings were deleted to improve correlations. Aggregates/ranks reduce some extreme-value influence but do not validate those values.

**Hypothesis:** Mileage can encode this vehicle's recording/aging trajectory. Strong level correlations alone can reward memorizing date/mileage and reported SOH updates. Daily aggregation reduces duration weighting but does not create independent vehicles. The table quantifies the risk; it does not prove universal mileage-based battery degradation. Temperature also co-varies with season and use. Odometer discontinuities complicate causal interpretation.

**Recommendation:** Future evaluation must compare performance with and without identity/time/mileage and capacity proxies, and against simple observed-SOH persistence and time/mileage-only reference predictions. Those experiments have not been run. Independent vehicles and capacity measurements are necessary before claiming generalizable battery-health estimation.

## 6. Anomaly detection readiness

**Conditionally ready — further verification required.** The data can characterize observed telemetry, but absence of fault labels does not certify a healthy training reference. Scores would indicate unusualness relative to recorded operating conditions, not confirmed defects or fault probabilities.

Candidate groups for later review: battery electrical (voltage, current, SOC); thermal (pack components, motor temperature, ambient after unit resolution); drivetrain (speed or RPM, torque, pedals/brake); auxiliary loads (AC and auxiliary power); contextual states (ECO/ePedal; raw gear/charge status after code and polling review). Do not blindly combine every group or count correlated channels as independent evidence. Tire pressure needs zero-value interpretation first. SOH is a slow contextual signal, not a dense fault label.

Raw all-empty fields: {", ".join(overview["raw"]["all_missing_columns"])}. Raw constant fields: {", ".join(overview["raw"]["constant_columns"])}. Raw near-constant fields: {", ".join(overview["raw"]["near_constant_99pct_columns"])}. The preprocessed data have no constant or >=99% dominant columns under the EDA definition. Complete variability, nonmissing cardinalities and IQR outlier counts are in the existing per-version `summary_statistics.csv`, `column_dictionary.csv` and `measurement_updates.csv`.

Verified redundancy includes processed Speed/RPM r≈0.99958, current/power r≈0.98941, SOC/kWh_Remaining r≈0.99101, closely correlated pack temperatures, and exact horsepower/power proportionality. These associations include shared operating state and formulas. Large torque/current excursions can be acceleration or regeneration; IQR flags do not diagnose faults.

Stationary speed identifies stopped observations, not necessarily idle or charging. Raw Charge_Mode has only -1 (605,817 observations, undocumented unknown state) and 0 (1,716,288, documented not charging); documented active codes 1/2/3 are absent. Plug/gear readings poll slowly and can be stale. Negative current alone cannot establish charging because documented polarity conflicts with much observed moving telemetry. No verified charging-session coverage can be claimed.

Raw data are needed to inspect original extreme/sentinel readings, statuses and missingness. The preprocessed data contain changed values and formula inconsistencies, so they cannot be presumed a clean normal-reference set. Neither version constitutes an independent validation set for the other.

## 7. Fault classification readiness

**Not ready — essential evidence missing.** Inspection of all columns, workbook descriptions and existing source documentation found no verified healthy/faulty target, DTC sequence, confirmed battery/sensor/charging/motor failure, repair record or event-adjudication table. The word health in SOH/Hx does not supply a fault class. Gear, charging and driver codes are not diagnostic labels.

A suspicious value may be a sensor/polling problem, a preprocessing artifact, a valid extreme or an unknown state. These alternatives cannot be converted into supervised labels from this evidence. Needed: independently confirmed diagnostic categories and event times, workshop/DTC evidence, normal comparison intervals, sensor/calibration context, enough independent events per category, and held-out vehicles. Both supervised training and diagnostic accuracy validation would otherwise lack defensible ground truth.

## 8. Battery health estimation readiness

**Monitoring the reported SOH: Ready for controlled experimentation.** Display controller-reported SOH, date and provenance; summarize its trend with gaps and uncertainty visible. This does not need a learned estimator.

**Estimating current or forecasting future reported SOH: Conditionally ready — further verification required.** A recorded target exists, but its low update rate, limited range, single-vehicle trajectory and strong age proxies make trivial shortcuts plausible. Current SOH estimation must withhold SOH itself and inspect AHr/Hx/remaining-energy dependencies. Forecasting requires a defined horizon, strictly past information and enough observed future outcomes; missing weeks are not measured degradation paths. Using past reported SOH can be legitimate for forecasting, but must be disclosed and compared with persistence.

**Independent physical battery-health or capacity estimation: Not ready — essential evidence missing.** The controller label alone cannot validate true capacity or generalization to another battery. Need independent capacity/resistance testing under known conditions, vehicle/battery identity and firmware, and multiple independently followed vehicles. No end-of-life trajectory or failure threshold is established.

## 9. Predictive maintenance readiness

**Not ready — essential evidence missing.** No failure timestamps, repair dates, component replacements, verified service needs, known end-of-life outcomes or event-linked fleet histories were found. AHr and SOH provide reported battery estimates, not a controlled capacity-test history. Intermittent telemetry and absent verified active charging coverage do not establish complete usage/charging history.

- Future telemetry prediction means forecasting an observed signal at a defined horizon; it may support a controlled descriptive forecasting experiment after continuity review.
- SOH forecasting predicts future controller-reported state; it is not equivalent to a failure forecast.
- Component-failure prediction needs confirmed outcomes and time-at-risk, which are absent.
- Remaining useful life needs an explicit end-of-life definition and observed/censored lifetimes; a short SOH trend cannot supply them.
- Maintenance recommendations need validated links from evidence to service need, inspection/repair outcomes and intervention policy; unusual readings alone do not establish these links.

## 10. Temporal structure and leakage risks

{md(time)}

Trip-ID overlap between versions: **{metrics["trip_overlap"]["shared_ids"]} shared**, **{metrics["trip_overlap"]["raw_only_ids"]} raw-only**, **{metrics["trip_overlap"]["processed_only_ids"]} processed-only**. All 1,886,696 matched timestamp rows also retain the same Trip ID according to the existing value comparison. The source-order block checks above test ID reuse; existing session tables show whether trip ranges overlap and their full measurement-sequence hash screens. Those screens found no identical complete sequences; they cannot exclude partial or near-duplicate recordings. IDs are useful recording groups, but undocumented segmentation rules prevent assuming each equals one complete physical journey. Seven Driver_ID codes are contextual identities, not independent vehicle replications.

Epoch timestamps are microseconds; parsing checks above use UTC as a representation, not a claim about the original recorder's local timezone. Raw DateTime has fractional-second strings; Timestamp_Object truncates to seconds and is unsuitable for distinguishing all rows. Both files are chronologically ordered under the checks above. A median 0.25-second row cadence does not mean every sensor polls at 4 Hz: the workbook also documents 1-, 10- and 100-second channels. Adjacent-similarity results are in [adjacent_similarity.csv](tables/readiness/adjacent_similarity.csv), restricted to same-trip positive intervals <=1 second.

**Why random row splits mislead:** Adjacent rows often carry the same slow sensor or SOH reading. Random assignment puts nearly identical states from one trip on both sides, exposes future aging states, and can split overlapping windows. Duplicate or derived information and shared raw/processed records add further leakage. Millions of rows cannot fix this dependence.

**Recommended future protocol (no splits created):** Choose a task/horizon first. Reserve a later chronological block containing entire trip groups for final evaluation, with earlier whole-trip blocks for development and validation. Move boundaries to prevent any trip, shared raw/processed timestamp or overlapping input/target window crossing partitions. Apply a purge interval at least as large as the longest input lookback plus prediction horizon where windows could overlap; choose it after sensor and dependence review. Never bridge trip boundaries, nonpositive time steps or task-inappropriate gaps. The 1/5/60-second gap counts here are sensitivity descriptions, not an approved universal threshold. Fit all preprocessing on development-training data only. Report metrics by trip/day, time horizon and operating state, with effective outcome counts. Do not claim cross-vehicle validation.

Chronological splitting alone can cut a trip. Trip-grouped random splitting controls shared-trip leakage but still mixes future/past aging states. Chronology with whole-trip boundaries is the defensible primary protocol here; future independent-vehicle holdout is required for transfer claims. Calendar/accumulated fields must be audited for future-inclusive calculations. Target-specific leakage includes power's voltage/current formula, pack mean's component temperatures, SOC-derived remaining energy and SOH/capacity proxies.

## 11. Preprocessing requirements — documentation only

{md(derived)}

Derived checks compare finite values with atol=rtol=1e-8; discrepancies are verified numerical inconsistencies, not confirmed hardware defects. Raw satisfies all three formulas, while processed changes break two of them. Do not overwrite either source or silently recompute away evidence.

Existing EDA also identifies two zero and one >500 V processed voltage readings (a review screen, not a manufacturer-certified validity limit), 321 within-trip odometer decreases and 304 jumps >1 km within <=1 second, and roughly 197k–202k zeros per tire-pressure channel. Their causes remain unresolved. Current sign and ambient-temperature documentation need clarification. Workbook units for Brake/Acc_Pedal are unknown. Some raw -1 codes are documented statuses and cannot be blanket-imputed.

| Requirement | Reason and future decision needed |
|---|---|
| Missingness | Raw has extensive missing fields; all-empty columns carry no signal. Processed has no NaNs but can retain placeholders. Establish per-sensor semantics before any imputation; fit any learned values on training only. |
| Invalid/nonfinite values | Reuse full EDA finite counts and range screens; distinguish impossible values from undocumented codes. Preserve exclusion reasons and source references. |
| Outliers | Inspect state and temporal context; statistical extremes may be legitimate acceleration/regeneration. Do not automatically remove. |
| Duplicates | No exact duplicates were found; held sensor values are normal with asynchronous polling. Avoid collapsing them without a sampling policy. |
| Units/sign | Resolve current polarity, ambient temperature and pedal/brake definitions; power-unit suffixes may describe resolution rather than stored-value multipliers. |
| Polling/time gaps | Define per-channel update/hold behavior, alignment policy and window validity; no sequences across excluded boundaries. |
| Derived/redundant fields | Decide task-specific inclusion after verifying formulas, information availability and target dependencies. |
| Categorical status | Preserve documented meanings and unknown states; numeric codes do not imply an ordered physical scale. |
| Scaling | Assess whether the eventually selected method needs it; mixed units/ranges can dominate distance-based comparisons. Estimate any scaling parameters on training data only. No scaler chosen/fitted here. |
| Identity and time | Keep for grouping/auditing; test shortcuts explicitly, avoid export indices as sensor inputs. |
| Reference selection | Define what is typical by observed state without inventing healthy labels; retain uncertain intervals for review. |

## 12. Four-task readiness comparison

{md(readiness)}

Potential inputs are the reviewed groups in section 6 and the full inventory. Every task inherits single-vehicle generalization limits, asynchronous sampling and raw/processed provenance uncertainty. SOH additionally risks time/mileage/capacity shortcuts; anomaly experiments risk learning preprocessing artifacts; fault and maintenance tasks cannot overcome missing outcomes through feature selection.

## 13. Dataset limitations and raw versus processed provenance

Verified alignment: 1,886,696 shared exact timestamps with matching exported indices, 435,409 raw-only timestamps and 31,603 processed-only timestamps. Processed-only observations span 63 trip IDs. Counts do not establish that preprocessing created records: export/version differences remain an alternative. The preprocessed file is not a strict subset. Matched values change in several channels, including power and temperature, while matched odometer values are unchanged. See [timestamp alignment](tables/raw_processed_timestamp_alignment.json), [matched values](tables/raw_processed_matched_values.csv), [retained versus removed](tables/retained_vs_removed_raw_rows.csv) and [distribution comparison](tables/raw_processed_distributions.csv).

The existing distribution comparisons establish altered coverage/values, not the researchers' exact cleaning pipeline. Unusual raw observations may be absent or altered, but without preprocessing code/provenance there is no complete causal explanation. This assessment does not reproduce that pipeline. Seasonal/route/driver selection, intermittent recording, narrow SOH range, one vehicle and missing diagnostic/service outcomes limit transfer. No unobserved intervals were filled.

## 14. Recommended next investigations

1. Ask the researchers for preprocessing code/version provenance, processed-only records, current polarity, unit ambiguities, trip segmentation and SOH update definitions. Resolve usage rights before redistribution.
2. Review formula-discrepant rows and voltage/odometer/tire-zero cases against original adjacent records and documented operating context; record adjudication without inventing fault labels.
3. Decide whether the prototype is a reported-SOH monitor or a conditional unusual-telemetry experiment; state the limits in its outputs. Define target horizon and available-at-inference inputs before prediction work.
4. Approve per-channel missing/code/unit/polling and gap policies, then a chronological whole-trip evaluation protocol. Recheck capacity-proxy and calendar/accumulated dependencies. Do not split until these decisions are explicit.
5. Only in a separately authorized experiment, test shortcut sensitivity and simple temporal reference predictions. Gather independent vehicles and capacity measurements for battery-health validation.
6. Obtain event-linked diagnosis, service and end-of-life data before fault classification, failure forecasting, RUL or maintenance claims.

## 15. Unanswered questions and reproducibility

Unknown: why processed-only timestamps exist; exact preprocessing operations; sign convention actually used in the logger; ambient-temperature unit discrepancy; zero-pressure meaning; causes of voltage/odometer artifacts; whether aggregated fields include future data; physical trip definition; SOH estimator firmware/update cadence/calibration; independent battery capacity truth; complete charging history; diagnostic/maintenance outcomes; redistribution rights. No additional external records were acquired in this assessment.

Reproduce from the repository root (uses the existing environment; pandas/NumPy/Matplotlib plus SciPy for Spearman correlations):

```bash
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/readiness.py
.venv/bin/python -m pytest ml/tests/test_nissan_leaf_readiness.py -q
.venv/bin/ruff check ml/notebooks/nissan_leaf_2018/scripts/readiness.py ml/notebooks/nissan_leaf_2018/scripts/readiness_report.py ml/tests/test_nissan_leaf_readiness.py
```

The script hashes original source files, checks schemas/counts, scans 14 shared selected columns plus four raw capacity/energy columns sequentially per version, reuses full EDA statistics, writes every inventory entry, and produces descriptive tables and two figures. The selected frames occupy roughly 215–334 MB before working copies; the run does not load all 92 raw columns. Unit tests use small original-file excerpts and lightweight outputs, never full telemetry scans. Tests exercise schema rejection, ordering, trip boundaries, missing accounting, formulas, inventory completeness and report/manifest consistency. Test execution results are recorded separately in `READINESS_VALIDATION.md`.

The [readiness manifest](readiness_manifest.json) records source checksums, reused EDA table hashes, script hashes, library versions and all generated output hashes. No new fault labels, training data or final partitions are outputs. Existing [EDA output index](OUTPUT_INDEX.md) remains the guide to the prior analysis.
"""
    (BASE / "ML_READINESS_REPORT.md").write_text(text)
