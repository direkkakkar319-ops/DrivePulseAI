# Dataset inventory and audit

Documents the local dataset inventory, immutable raw locations, validation findings, and deferred loader corrections. Audited 2026-10-04; no datasets downloaded, models trained, or preprocessing performed.

**AI4I is an industrial-machine benchmark and must not be interpreted as automotive telemetry.**

**NASA C-MAPSS is an aircraft-engine degradation benchmark and must not be interpreted as automotive telemetry.**

**Raw datasets from different physical domains must not be made equivalent merely by renaming columns.**

## Status and canonical locations

`COMPLETE` below means the local distribution passes structural/completeness checks against its accompanying documentation; it does not certify suitability for a passenger-car model or compare against a remote official checksum. Provenance and content quality are separate from completeness.

| Dataset | Status | Present / canonical location |
| --- | --- | --- |
| carOBD candidate | INCOMPLETE; provenance UNVERIFIED | `automotive_obd/carobd/raw/`: 129 CSV recordings, 304,299 rows; malformed/short records described below |
| DieselOBD candidate | UNVERIFIED | `automotive_obd/dieselobd/raw/`: two OBD/DTC Excel workbooks; no source documentation |
| VED | REMOVED 2026-10-06: static metadata only, no telemetry; unused by any loader | `automotive_obd/ved/raw/` (deleted) |
| KIT Automotive OBD-II | COMPLETE | `automotive_obd/kit_obd/raw/`: 81 actual CSV recordings plus original RADAR metadata/BagIt payload |
| Scania APS Failure | COMPLETE | `automotive_failure/scania_aps/raw/`: official-named training/test CSVs and description |
| SCANIA Component X | REMOVED 2026-10-06: citation only, data never downloaded; RUL blocked until the official release arrives | `automotive_prognostics/scania_component_x/` (deleted) |
| AI4I derivative | REMOVED 2026-10-06: industrial benchmark, superseded by Scania APS; loaders deleted | `benchmarks/ai4i/raw/` (deleted) |
| NASA C-MAPSS | REMOVED 2026-10-06: aircraft benchmark, superseded by Scania APS; loaders deleted | `benchmarks/cmapss/raw/` (deleted) |

No additional NASA battery dataset was found. No exact duplicate standalone raw files were found after extraction. Dataset-like files outside `data/` were webpack cache archives, not dataset copies; their inventory is in `audit/repository-data-candidates.json`. Dependency/VCS environments were excluded from that search. Existing AI4I EDA figures in `ml/reports/` were left untouched. No confidently identified invalid generated dataset was found to remove.

## Raw-data rules

Raw contents are unchanged, including malformed rows, missing cells, duplicate rows, original encodings, column names and official split files. Do not train directly through the existing cross-domain mapping loaders. Corrections, filtering, unit conversions, deduplication and features belong in a separately reviewed future preprocessing step. No processed datasets were created.

Directory grouping is organizational: placing a candidate under `dieselobd` or `carobd` does not verify its origin. Never infer vehicle class from AI4I H/L/M, vehicle telemetry from make/model, or mechanical diagnoses from unlabeled recordings.

## carOBD candidate

- Present: `drive1..13`, `idle1..47`, `live1..39`, `long1..12`, `ufpe1..18` CSVs. Filenames and 27 named OBD columns are consistent with the expected carOBD family. Repository-local license, original README, version and download manifest are absent: **UNVERIFIED**. Toyota Etios identity and recording cadence are not established by the local CSVs.
- Intended use: automotive anomaly-detection exploration after provenance/schema validation. Real-recording claim, exact vehicle/year and units require source documentation; no failure labels, verified vehicle IDs or wall-clock timestamps are supplied.
- Signals include engine runtime (`ENGINE_RUN_TINE ()`, spelling preserved), RPM, speed, engine load, coolant/intake temperature, fuel trims, manifold/barometric pressure, throttle/pedals, catalyst temperatures, control-module voltage and MIL counters. Empty unit annotations do not establish units. Runtime is not a UTC timestamp. Control-module voltage is not a battery state-of-health label.
- Most rows have 28 CSV fields for 27 column names because of a trailing empty field. Some have exactly 27 fields. A future parser must explicitly account for this rather than letting a CSV library silently shift columns/indexes.
- `idle1.csv` final row (line 1214) has 17 fields; `live16.csv` final row (3083) has 18; `ufpe4.csv` final row (1350) has 23. These are incomplete records, possibly truncated downloads; retain and verify against original recordings.
- `live6.csv` has 2,287 rows of 24 fields against a 27-column header throughout. Verify which fields are actually provided; do not invent missing values or assume column alignment without source confirmation.
- 29,328 repeated full rows within files were observed and retained. Runtime does not decrease within these files; this does not prove a reliable fixed sampling rate. No official split was found. Keep recordings separate and design trip-aware evaluation later.
- Needed: original release README/license/file manifest and verified versions of the four named files (compare, do not overwrite blindly). Other recordings can support exploratory work only after schema and provenance review; this collection is not yet clean training input.

## DieselOBD candidate / OBD workbooks

- `MASTER_TRAIN_X.xlsx`: sheet `Train`, 118,477 data rows.
- `MASTER_TEST_X.xlsx`: sheet `Test`, 33,838 data rows.
- Both ZIP/XML packages pass integrity checks. Both contain the same 26 named columns plus an empty 27th column. Raw spreadsheets are preserved; no CSV conversion was made.
- Signals: `LOAD_PCT, ECT, MAP, RPM, VSS, IAT, MAF, FRP, BARO, VPWR, AAT`; 14 DTC-named columns from `P0000` through `P0406` (full header/value inventories in `audit/validation.json`) and `Mode`.
- Likely automotive OBD/fault-classification input, but DieselOBD attribution, real/synthetic origin, release, vehicles, units, label encoding and `Mode` semantics are **UNVERIFIED**. These are **not Component X operational/specification/TTE files**. No vehicle/trip identifier or timestamp column exists in these workbooks.
- Keep one canonical raw copy here for either future anomaly or classification pipelines. Preserve the supplied train/test distinction; it is not yet verified as an official independent split.
- 90,657 repeated rows within Train, 26,280 within Test, and **173 distinct identical rows shared between Train and Test**. This is an evaluation leakage concern, not authorization to remove raw rows. Identical rounded signals need not prove the same physical event; obtain recording/vehicle grouping information before deciding remediation.
- Needed: original download source, license, README/data dictionary, units, recording/vehicle IDs or original per-vehicle logs if offered, label definitions and split construction. Exact additional filenames cannot be established locally. Do not use these files for credible held-out failure evaluation yet. Other verified datasets can proceed independently.

## VED

- Present: `VED_Static_Data_ICE&HEV.xlsx`, 357 rows and 357 unique `VehId` values. Workbook metadata includes a VED publication/source-code path, supporting the association, but not a verified release/checksum/license.
- Columns: `VehId`, `Vehicle Type`, `Vehicle Class`, `Engine Configuration & Displacement`, `Transmission`, `Drive Wheels`, `Generalized_Weight`. `NO DATA` occurs 996 times; three omitted cells are retained. Weight units are not specified in this workbook.
- Automotive vehicle metadata only; no dynamic readings, trips, time series, failure labels or official ML splits are locally available. Preserve `VehId` for a later join; never generate telemetry from static specifications.
- Needed: official VED dynamic trip recordings (the expected distribution is commonly named `VED_DynamicData.7z` / its contained CSVs; confirm against the source release), `VED_Static_Data_PHEV&EV.xlsx` for the other vehicle types, and source documentation/license/version. No local manifest verifies the full expected file list.
- Vehicle/trip joins cannot be tested until dynamic data arrives. VED telemetry experiments must wait; other datasets can proceed. EV/HEV traction-battery signals must not be treated as ordinary 12-V control-module voltage.

## KIT Automotive OBD-II

- Locally established provenance: RADAR DOI `10.35097/1130`, alternate KITopen DOI `10.5445/IR/1000085073`; Marc Weber, Karlsruhe Institute of Technology; production year 2018, publication year 2023; **CC BY 4.0** in supplied metadata. BagIt export dated 2023-06-21; that is an export date, not an inferred scientific dataset version.
- Real automotive recordings using KIWI 3 and OBD Auto Doctor on iOS, according to metadata. All 81 CSV filenames name Seat Leon and preserve dates/routes/road-condition descriptions; no claim of independent vehicles is made.
- Canonical usable recordings: `raw/recordings/OBD-II-Dataset/`, 2,693,824 rows, 11 columns each: time plus coolant temperature, manifold pressure, RPM, speed, intake-air temperature, MAF, throttle, ambient temperature, pedal D/E. Header units include degrees C (existing mojibake retained), kPa, RPM, km/h, g/s and percent. No control-module voltage field.
- Blank values occur, especially during initial PID updates. Times are time-of-day with milliseconds; filename supplies date context, not timezone. Five files contain one backward jump each (42–466 ms): `2017-07-11_Seat_Leon_KA_S_Normal.csv`, `2017-07-24_Seat_Leon_RT_KA_Normal.csv`, `2017-08-01_Seat_Leon_KA_KA_Frei.csv`, `2017-08-02_Seat_Leon_RT_S_Normal.csv`, `2017-08-09_Seat_Leon_RT_S_Normal.csv`. Future preprocessing must address ordering explicitly.
- No repeated full rows found within individual files; no official train/test split or verified mechanical-failure labels. Road-condition names are not fault labels. Intended use: automotive telemetry/anomaly methods, not supervised component diagnosis.
- Original BagIt structure remains under `raw/10.35097-1130/`. All six listed payload/tag MD5 checks pass. Its nested `data/dataset/OBD-II-Dataset.zip` is intentionally retained because it is the original payload referenced by the BagIt manifest. Training code should read only `raw/recordings/`, not recursively ingest archive and extracted data twice.
- The separately downloaded `RADAR_DATASET_DESCRIPTIVE_METADATA` differs byte-for-byte from the embedded XML; both are retained as provenance records, not collapsed by filename. Both identify the same dataset; no version superiority is assumed.

## Scania APS Failure

- Local description identifies Scania CV AB, September 2016, heavy-truck everyday-use observations, with GPL v3-or-later notice. Automotive truck benchmark; not passenger-car OBD or a source of named physical sensor units.
- `aps_failure_training_set.csv`: 60,000 rows, 59,000 `neg`, 1,000 `pos`.
- `aps_failure_test_set.csv`: 16,000 rows, 15,625 `neg`, 375 `pos`.
- Each has 171 columns **including class** (170 anonymized counters/histogram-bin features). Description and original preambles preserved. Future CSV reader must locate the `class,` header after the copyright preamble and support its text encoding.
- Missing value token `na`: 850,015 training and 228,680 test cells. No repeated full rows within or between these splits found.
- `pos` represents the specified APS component failure; `neg` means failures in other components, **not healthy vehicles**. No vehicle/trip ID, timeline or RUL label is established. Intended use: imbalanced automotive failure-classification benchmark only.
- Preserve official split; no random recombination or resplitting of the test data. Locally complete; external release checksum not independently verified.

## SCANIA Component X

- Only `2024-34-3.bibtex` exists, now under `documentation/`. It cites Scania CV AB, Lindgren et al., 2025, DOI `10.5878/bnh5-ka77`, “SCANIA Component X Dataset: A Real-World Multivariate Time Series Dataset for Predictive Maintenance.” Citation year/filename is not proof of a downloaded version.
- Automotive prognostics intended; actual release, real-recording details, schema, units, labels, identifiers and relationships cannot be validated without data. No IDs were fabricated or joined to the unrelated OBD Excel files.
- Missing all nine expected logical CSVs: `train_operational_readouts.csv`, `train_specifications.csv`, `train_tte.csv`, `validation_operational_readouts.csv`, `validation_specifications.csv`, `validation_labels.csv`, `test_operational_readouts.csv`, `test_specifications.csv`, `test_labels.csv`.
- Also needed: release/version README or manifest and dataset PDFs/data dictionary. Obtain one internally consistent official release; verify that its actual distribution supplies the expected label files rather than substituting another version.
- These files are required for operational/specification joins and time-to-event/evaluation targets. Component X experiments cannot proceed; OBD anomaly and APS classification work can proceed independently. Preserve train/validation/test and related tables separately when downloaded.

## AI4I local derivative (benchmark only)

- `predictive_maintenance.csv`: 10,000 rows, 12 columns; readable, no missing cells or repeated full rows. `Machine failure`: 339 positive and 9,661 negative.
- Industrial-machine benchmark; expected AI4I family is synthetic. This local copy lacks source documentation/license/version, original UDI/Product ID fields and unit-bearing headers. It is therefore an **unverified derivative**, not certified original raw AI4I. Existing bytes are preserved as received; no claim that we recovered the original distribution.
- Columns: `Type`, `Air temperature`, `Process temperature`, `Rotational speed`, `Torque`, `Tool wear`, `Machine failure`, `TWF`, `HDF`, `PWF`, `OSF`, `RNF`. No units are inferred from shortened headers. H/L/M are not vehicle sizes. Fault flags can leak the target; exclude them from predictors in a reviewed benchmark pipeline.
- No official split, vehicle IDs or time axis. Intended use is industrial classification research only. Obtain original source/license/schema/checksum to validate this derivative; it can be retained without blocking automotive work. Do not map tool wear to vibration or torque to engine-load percentage.

## NASA C-MAPSS (benchmark only)

- Four `train_FD00N.txt`, four `test_FD00N.txt`, four `RUL_FD00N.txt`, original `readme.txt` and `Damage Propagation Modeling.pdf`. Paper text extracts successfully and documents aircraft-engine run-to-failure simulation.
- Simulated turbofan degradation, not real automotive data. Twenty-six numeric columns: unit, operational cycle, three settings, 21 anonymous sensors. RUL labels are remaining operational **cycles** after the test trajectory, not days/km. No automotive sensor/unit equivalences.

| Subset | Train rows / units | Test rows / units | Test RUL labels |
| --- | --- | --- | --- |
| FD001 | 20,631 / 100 | 13,096 / 100 | 100 |
| FD002 | 53,759 / 260 | 33,991 / 259 | 259 |
| FD003 | 24,720 / 100 | 16,596 / 100 | 100 |
| FD004 | 61,249 / 249 | 41,214 / 248 | 248 |

- All numeric widths and within-unit consecutive cycles pass; test unit IDs are contiguous and match label counts. Keep subset and split in engine identity: repeating unit numbers across files are not proof of duplicate physical engines.
- Supplied README states FD004 train 248/test 249, opposite the actual files, and ends its column list with “sensor measurement 26” despite only 21 sensor positions. Preserve these documentation discrepancies for source comparison; do not relabel files or delete data.
- Retain official split and test RUL offsets. No release identifier/download checksum/license file is present; exact distribution version remains UNVERIFIED. Structurally usable for a separately validated aircraft RUL benchmark, not automotive prognostics.

## Deferred code/documentation corrections (outside this task)

No files outside `data/` were changed.

- `ml/notebooks/eda_ai4i.py:37` still defaults to removed `data/failure_classification/raw/predictive_maintenance.csv`. It accepts `--csv data/benchmarks/ai4i/raw/predictive_maintenance.csv`; this is a path workaround, not approval of the mapping pipeline. Update the default in the next code phase.
- `ml/src/data/loaders.py` accepts caller paths. Pass new canonical directories after a domain-correct loader review. `load_ai4i` expects unit-bearing headers absent from this derivative and incorrectly maps torque/tool wear/process temperature to automotive fields. Its whole-input max scaling is also a leakage risk. Generated `AI4I-*` row identities are not real vehicles.
- `load_cmapss` maps anonymous aircraft sensors to coolant, battery voltage, RPM and vibration; remove those assumptions later. It only finds training files for directory input; direct test-file input incorrectly calculates RUL from observed last cycle and ignores official RUL offsets.
- `load_simulated` labels all input as simulated and gives each filename a synthetic vehicle ID. It must not be used unchanged for real carOBD recordings. Runtime is not a wall-clock timestamp; file/trip is not vehicle identity. Test fixtures currently reinforce those assumptions and need review with loader changes.
- `ml/src/data/preprocessing.py` offers train-only reusable scaler/imputer parameters and chronological splits, but callers can still fit on all data. `time_ordered=False` performs random row splitting, inappropriate for dependent trip/engine samples. Default within-vehicle chronological splitting is not held-out-vehicle evaluation. Split before overlapping windows and keep official test sets untouched. Near-identical OBD workbook rows and absent grouping IDs need particular attention.
- `feature_engineering.py` aliases mapped industrial columns and uses a fixed wear threshold; those remain industrial assumptions. Do not propagate them to automotive sensors. Target-derived fault columns must remain excluded.
- No implemented dataset-specific loaders were found for KIT, VED, APS, Component X or these XLSX workbooks. Implement separately with source schemas and split contracts.
- `scripts/download_datasets.sh` is a comment-only placeholder referring to `data/raw/`. Root README still claims benchmarks are “mapped to automotive equivalents” and labels preprocessing “leakage-free”; these claims need correction in a later documentation/code scope. The former `data/README.md` suggested a C-MAPSS coolant proxy; that incorrect text was replaced here.
- Root `.gitignore` only excludes `data/raw/*`; it does not exclude these canonical raw paths. Raw CSVs include large extracted APS files. Decide dataset versioning/LFS/ignore policy before staging or pushing; no Git tracking policy was changed by this audit.

## Audit trail and checks

- `audit/inventory-before.json`: original source paths, byte sizes and SHA-256.
- `audit/changes.json`: every move, extracted member hash, and removed outer archive hash.
- `audit/inventory-after.json`: canonical retained source files, byte sizes and SHA-256.
- `audit/validation.json`: per-file/sheet headers, row/column counts, missing tokens, duplicate-row counts, labels and ordering checks.
- `audit/validation-summary.json`: cross-split identical rows and exact duplicate file results.
- `audit/kit-bagit-validation.json`: original payload/tag manifest verification.
- `audit/additional-validation.json`: numeric-cell checks, KIT timestamp-format checks and C-MAPSS test-ID/RUL-label alignment. All passed; these checks do not repair or excuse the short carOBD records.
- `audit/preserved_misc/.DS_Store`: original macOS folder metadata retained outside raw; not training data.

Removed only the fully extracted and SHA-256-verified outer APS ZIP and KIT TAR. Retained KIT's nested original ZIP for its BagIt provenance value. No differing raw versions, duplicate source rows or suspicious records were deleted. No non-identical files were silently selected as “correct.”

Validation used Python standard-library streaming CSV/text/XML parsing, XLSX/ZIP CRC checks, streamed SHA-256, BagIt MD5 checks and `pdftotext`. Row hashes were held per file, not full tables; XLSX cell references were respected when counting omitted cells. Duplicate-row checks cover full parsed rows within files and APS/OBD workbook split overlap; they do not establish absence of feature-only or near-duplicate leakage across all datasets. Timestamp checks identify ordering, not synchronization accuracy. Parsing success does not prove scientific validity.

Recheck byte preservation from repository root:

```bash
python3 data/audit/verify_integrity.py
```

The original restructuring/validation command was `python3 /tmp/drivepulse_dataset_audit.py`; its outputs are recorded here. That one-time mutation script must not be rerun on the reorganized tree. No ML training was performed; application code is unchanged. During PR preparation after updating from main, `pytest ml/tests -q` passed all 37 tests, `ruff check ml/ data/audit/verify_integrity.py` passed, and `ruff format --check data/audit/verify_integrity.py` passed. These checks do not validate the scientific correctness of the existing cross-domain mappings.

Final verification: `python3 data/audit/verify_integrity.py` passed 483 SHA-256 checks and accounted for every original source file. `git diff --check -- data/README.md` passed. All audit JSON files parse, and changed tracked paths are restricted to `data/`.
