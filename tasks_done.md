# Tasks done and verification log

This log records the ordered work and verification. Status labels distinguish verified results from open work. Before Step 0, repository source code, configuration and notebooks were not edited during the audit; Step 0 added only the shared seed helper. Acquired source archives are unchanged downloads under `data/automotive_prognostics/scania_component_x/v3/raw/`, `data/automotive_prognostics/onroad_ev_capacity/source_release/`, and `data/automotive_prognostics/ev_fault_347/v1/raw/`.

## Step 0 — Setup and baseline

**Status: ✅ Done and verified in the existing local environment.**

- Created branch `pipeline/data-and-training` from `9d79a59`.
- Recorded host capacity: WSL2 Linux x86_64, Python 3.12.3, 12 CPUs, 15 GiB RAM, 175 GiB free.
- Used the existing root `.venv`; system Python was not used for ML imports because it lacks NumPy/pandas/scikit-learn/XGBoost. The `.venv` versions are recorded in `ml/requirements.lock.txt`.
- Ran `./.venv/bin/python -m pytest -q ml/tests --disable-warnings --maxfail=1`: **41 passed in 8.15 seconds**.
- Added `ml/src/reproducibility.py` with `GLOBAL_SEED = 42` and optional PyTorch seeding. MLflow remains unavailable in `.venv`; it is listed in `ml/requirements.txt`, while `ml/src/training/mlflow_utils.py` is currently a comment-only stub. No experiment run was created.
- Step 0 gate: **pass** for the existing environment and mapped data layout. Step 1 dataset validation is not started.

## Step 1 — Verify Component X release, terms, targets and joins

**Status: ✅ Done and verified against the official publisher record and documentation.**

- Reviewed the [SND catalogue record](https://researchdata.se/en/catalogue/dataset/2024-34), [final dataset paper](https://doris.snd.se//api/file/2024-34/3/documentation?filePath=Scania_Component_X.pdf), and [IDA challenge documentation](https://api.researchdata.se/dataset/2024-34/1/file/documentation?filePath=2024_IDA_challenge_v2.pdf).
- Current release is **v3**, DOI [10.5878/bnh5-ka77](https://doi.org/10.5878/bnh5-ka77); catalogue says open access and **CC BY 4.0**. Version 2 DOI is 10.5878/jvb5-d390; v3 replaces the manuscript with the final paper.
- Source is real-world **Scania heavy-duty truck** data for one anonymized component. It is not passenger-car data and does not identify a named engine/clutch/brake subsystem.
- `vehicle_id` is the cross-file join key. `train_tte.csv` columns are `vehicle_id,length_of_study_time_step,in_study_repair`; `in_study_repair=1` means a repair/replacement was observed by study end, while 0 means no observed event by study end (right-censored), not exact RUL. Validation/test `class_label` values 0–4 encode event lead-time bands; class 0 groups >48 time units and no observed event. Therefore `class_label > 0` is not a fully observed binary label for every unit.
- Publisher docs describe vehicle-disjoint 70/15/15 train/validation/test partitioning, irregular operational readings and anonymized counter/bin features. The target is suitable for a truck-component time-to-event study, subject to censoring-aware methods.

## Step 2 — Acquire and audit Component X v3 source files

**Status: ✅ Done and verified.**

- Acquired nine CSV files and two publisher documentation PDFs individually from the versioned official endpoint `https://scania.open.care.snd.se/downloads/public/2024-34/3/data/` and `/documentation/` into `data/automotive_prognostics/scania_component_x/v3/raw/`.
- A bulk ZIP attempt stalled and was rejected. The large training CSV was fetched in HTTP byte ranges and reconstructed to the publisher-reported exact byte size. Individual raw files were not transformed or edited. Publisher `Content-Length` matched all local sizes listed below.
- Streamed schema and key audit: train ops 1,122,452 rows × 107 columns, 23,550 unique vehicles; validation ops 196,227 × 107, 5,046 vehicles; test ops 198,140 × 107, 5,045 vehicles. Train/validation/test specifications have 9 columns. TTE has 3 columns; validation/test labels have 2. No malformed records or within-file time-order breaks were reported by the audit script.
- All operational vehicle ID sets exactly match their same-split specification and TTE/label ID sets; no unmatched keys. Train, validation and test vehicle IDs are pairwise disjoint. Train TTE records: 21,278 observed repairs, 2,272 censored. Validation labels: class counts 0=4,910; 1=16; 2=14; 3=30; 4=76. Test: 0=4,903; 1=26; 2=15; 3=41; 4=60. This is highly imbalanced.
- Sizes and SHA-256 checksums:

| File | Bytes | SHA-256 |
|---|---:|---|
| `2024_IDA_challenge_v2.pdf` | 231,630 | `b4261fe713811c9f3c02fe95d01b56f756c181ebec7b1277df36f7fdaeffb87f` |
| `Scania_Component_X.pdf` | 3,283,883 | `b8450509bc4b11c6a47a70e56cc37b4aaf1a40e6ebcaeef67477c79691123610` |
| `test_labels.csv` | 38,682 | `60f923051d4ba1bef4c81166cf9e8ca01daf3b7a29c73016c6f48a23dcfa0223` |
| `test_operational_readouts.csv` | 214,897,259 | `81f2709cd339e0ff561f5fd3188d7f431680e32400bd788814880d7759615ba1` |
| `test_specifications.csv` | 231,658 | `40ac8a111f6d5b416107ec1786f639766ecf1293a1c9c0c0dbf24f14c1c5d0e7` |
| `train_operational_readouts.csv` | 1,219,209,878 | `e01cb0bd87dfab4c9dbad215d51d81282fc0d413be96d6f819ea872fb7a3c715` |
| `train_specifications.csv` | 1,081,118 | `47cc9a67aee19d5e2ee8620fe8e467490b2125bacc7787ce781ce9f3c1f0c38f` |
| `train_tte.csv` | 345,412 | `d8c2379ed7c95a575dd869730b2b3b96d660317f49e57de300518ff3b08d53a5` |
| `validation_labels.csv` | 38,742 | `ad876c95c3696f4cfca2d76212ad6bb3cac6b2d2950a4aeaf218ee8b1548d08c` |
| `validation_operational_readouts.csv` | 215,593,159 | `1e1597eec866588c2ad95eb923555ad719c64b3697d9140f9cec6809349809af` |
| `validation_specifications.csv` | 231,765 | `a31e832846538dd7a1829108b69420d9377dcd05d6446d8ac1270a974fc58ae2` |

- Audit implementation was temporary and outside the repository (`/tmp/audit_component_x_v3.py`). No training was run. Raw data acquisition succeeded; the data’s domain suitability for this product did not.

## Step 3 — Freeze project domain and data-contract direction

**Status: ✅ Domain frozen; detailed car data contract remains open.**

- User decision: **cars only**, interpreted as passenger cars including passenger EVs. Trucks, buses, aircraft, industrial machines and surrogate-domain data cannot be included in a DrivePulseAI car performance claim.
- Component X v3 is a successful acquisition/audit, but is **out of scope for training or validating this project’s car models** because the publisher documents heavy-duty Scania truck data. Keep it only as a separately named external truck benchmark if useful.
- Do not start a Component X RUL baseline for this car project. The project still needs verified passenger-car/EV failure and degradation labels. KIT OBD remains eligible only for unsupervised car telemetry anomaly exploration; Scania APS remains an independent truck classification benchmark.
- Scope requirements and gaps were updated in `scope.md`, `progress.md`, `remaining.md` and `datasets.md`. Data contract choices still needed: first supported car subsystem, feature schema, RUL unit/health-score mapping, failure horizon, and label/censoring semantics.

## Dataset-to-model exclusions after the cars-only scope freeze

Unsuitable model/dataset pairings have been removed from the active assignment list. The audit findings remain in `datasets.md` as evidence of why they were excluded. Current assignments are listed under “Active model-to-dataset assignments after exclusions” below.

## Step 4 — Acquire and audit a passenger-EV capacity-history candidate

**Status: 🟡 Acquired and schema-audited; not approved for RUL training.**

- Source: [BatICM repository](https://github.com/BatICM/battery-charging-data-of-on-road-electric-vehicles), pinned snapshot commit [`36fef4bd99f626561e2d138a40ccff3d1f3ddfc2`](https://github.com/BatICM/battery-charging-data-of-on-road-electric-vehicles/commit/36fef4bd99f626561e2d138a40ccff3d1f3ddfc2), dated 2025-03-31. The author README identifies 20 BAIC EU500 commercial EVs with CATL NCM packs and about 29 months of records, and says capacity extraction code is provided.
- Downloaded the 20 original `.rar` archives, `README.md`, `LICENSE`, and `Supplementary materials.pdf` into `data/automotive_prognostics/onroad_ev_capacity/source_release/`. The 20 archives total 230,024,681 bytes; all 23 selected files total 230,785,574 bytes. Local byte sizes and Git blob IDs match GitHub’s tree API at the pinned commit. SHA-256 values follow below.
- Inspected all archive listings (one CSV per vehicle) and streamed every CSV using a temporary `bsdtar` binary extracted under `/tmp`; no project files were changed by extraction. Audit result: **20 vehicles, 16,100,728 rows total**, 11 columns per CSV: row number, `record_time`, `soc`, `pack_voltage (V)`, `charge_current (A)`, `max_cell_voltage (V)`, `min_cell_voltage (V)`, `max_temperature (℃)`, `min_temperature (℃)`, `available_energy (kw)`, and `available_capacity (Ah)`. No missing cells and no within-chunk exact duplicate rows were observed. The row-number/vehicle-file relationship gives unit identity; no official train/validation/test split is provided.
- The per-vehicle record counts are: #1 854,591; #2 841,810; #3 802,918; #4 844,537; #5 832,189; #6 815,202; #7 808,770; #8 798,496; #9 792,060; #10 728,849; #11 809,470; #12 825,533; #13 818,352; #14 793,132; #15 704,958; #16 819,567; #17 767,868; #18 856,192; #19 778,745; #20 807,489.
- Timestamps range approximately 2019-07-22/26 through 2021-11-15/16. Raw record sampling is timestamped but irregular; the source code splits charging segments where the next timestamp gap exceeds 10 seconds.
- Target audit: the maintainer’s `capacity_extract.py` maps fields and calculates charge capacity by integrating charge current over elapsed seconds, then dividing by SOC change. This is a **derived per-charge capacity estimate**, computed from the same charge window; it is not an independently observed failure or end-of-life time. Use only as a candidate for future capacity/SOH forecasting with strict past-to-future cutoffs. It does not currently support a valid observed-RUL baseline or failure classifier.
- Rights audit: the repository contains an MIT LICENSE, but its text grants rights to the “Software and associated documentation files”; the author README says the data are publicly available but does not provide a separate data license. **Data reuse/redistribution rights remain unverified.** Keep the source files quarantined from training and public redistribution until clarified.
- No model was trained. A simple RUL baseline is blocked because neither an EOL event nor an agreed EOL threshold/follow-up label is present. Forecasting future capacity would be a different, potentially feasible baseline after data rights and scope are decided.

| File | Bytes | SHA-256 |
|---|---:|---|
| `#1.rar` | 12,238,871 | `2e77a7836f441f5f45ae0b2e2116044fa3c4191d67377e89a126562743afc443` |
| `#10.rar` | 10,508,142 | `cc89ed52f23db5322fccd978cb489826796312c8fa999a6f733d9ebd719f919d` |
| `#11.rar` | 11,539,660 | `658dff42f3ee690dbe55379887cceffb5be667ecc08136ebba80020f4ef66f0a` |
| `#12.rar` | 11,883,835 | `f6c8bc2ba4bdc8893cbe2e1a58a6f215ff26aff3f5659bbeb13d9f9e8db1bab4` |
| `#13.rar` | 11,474,175 | `3ae4e287f051dc718b8c9049b51b5d9ab0debfbe1d8951f02c8aac8795413408` |
| `#14.rar` | 11,377,770 | `0964797a9574c75f0d93c1c05192a2a406a57330cccbfc88ec0258c1ab70109b` |
| `#15.rar` | 10,013,220 | `d8b4468bd9199a6d281513d2fedb699456a8ef62a77530c30f3632ae5fbd6aa3` |
| `#16.rar` | 11,805,417 | `156a3650976c60283e5ad83f9bb6f9c3492c4248ade1a8d172097dff03ab9df2` |
| `#17.rar` | 10,922,855 | `70da9fc2225519cd26025aeb26a58d603ba310165475a8b054847a6afed57ccb` |
| `#18.rar` | 12,046,848 | `da97555e3e3f0dbb1adb72b2f846a9bb7c99d52bcfcfa2eb7c87645106fba85d` |
| `#19.rar` | 11,188,518 | `0527ebd3eb2721bc16a30fbd0731336edd48c49e6ae886ed80289af62f41bd12` |
| `#2.rar` | 12,088,035 | `52e008eb067e6072016ac98f580e3230480236d67c211404f0d62f44ce3a9421` |
| `#20.rar` | 11,502,515 | `37b48debf7b89151bd7a01a96e4c870df0c8aafa7ff48d08fcaf42914c239e31` |
| `#3.rar` | 11,451,253 | `1cb5d824602929662e09cb0a028a43258fa85055865391e906049df28e9a0ea5` |
| `#4.rar` | 12,084,749 | `df2aa25c7bd471a97d3f997cc8e17f171940138dc161a4e49dc370aaf1257d7c` |
| `#5.rar` | 11,888,317 | `16b67a98bbdcb8df7f1727ccdf36e68b9eabb209d9bf2707ae921db489bad1ac` |
| `#6.rar` | 11,663,814 | `847b207bea6d5a60fdd92c208b32c8aff7575257e316de663ea7f9bf63642477` |
| `#7.rar` | 11,606,222 | `3ac79b584d43d54af1d9583c269fd35d1a5a86bb2ef0af64b61dabdb1528baf6` |
| `#8.rar` | 11,507,641 | `4603f6ca0405bb6356401060215ac39bda06eb70b35f0dfe1a88cafe4c7a9b52` |
| `#9.rar` | 11,232,824 | `a3392323136fe7e0ff5e8db9f5a874d19b68693fa7865dc0082f522290a8a70f` |
| `LICENSE` | 1,069 | `424f4b69ace5e11d273d7be9ac0e714a3c930ff761b2fd276f5c1699b7ba4c15` |
| `README.md` | 1,092 | `f317feaec92d2f17a51d7a55baa3efd57a96d715552eb0b8165d1ae604d286fa` |
| `Supplementary materials.pdf` | 758,732 | `75524b7776168a2ffb2842ad9683a156bb2d1029618b99cf26df6e13b150e8f2` |

## Active model-to-dataset assignments after exclusions

Only datasets with at least limited task fit are retained in these assignments. ❌ dataset/model pairs from the previous assessment are omitted. This is a model assignment decision; raw audit evidence is retained pending your decision on file deletion.

| Model | Assigned dataset | Fit and boundary |
|---|---|---|
| Anomaly detection | KIT Automotive OBD-II | 🟡 Limited unsupervised novelty baseline on Seat Leon telemetry; not fault detection. |
| Anomaly detection | On-road EV 20-car capacity history | 🟡 Battery signal novelty exploration only; rights unresolved, no anomaly truth, so not approved for training yet. |
| Anomaly detection | 347-EV Figshare battery charging records | 🟡 Archive/schema inventory done; EV domain verified, passenger-car body type, count discrepancy and complete joins unresolved; not approved for training. |
| RUL / health | None currently approved | No dataset has verified car EOL/RUL targets. The 20-car history is for possible future capacity/SOH forecasting only, not RUL. |
| Failure classification | None currently approved | 347-EV has vehicle-level abnormal/normal labels, but passenger-car body type, 347/348 count discrepancy, complete joins and forward horizon are unresolved. |

Excluded pairings include KIT/carOBD/DieselOBD for RUL; KIT/carOBD for mechanical failure classification; and Scania APS / Component X for every passenger-car claim. These exclusions are reflected in the assignment table above. Raw files remain in the audit inventory so the original evidence is preserved until deletion scope is confirmed.

## Step 5 — Audit the 347-EV Figshare archive and revisit 20-car data rights

**Status: 🟡 Archive and label files audited; passenger-car applicability not established; 20-car data rights remain unresolved.**

- Primary records reviewed: [Nature Communications article](https://www.nature.com/articles/s41467-023-41226-5), its [Figshare data record](https://doi.org/10.6084/m9.figshare.23659323), and [Figshare API metadata](https://api.figshare.com/v2/articles/23659323). The paper describes 690,000+ battery-charging snippets from 347 EVs, with 55 abnormal and 292 normal vehicles. It states vehicle-level abnormalities were based on driver reports and engineer confirmation (including lithium plating, low electric range, high temperature and cell imbalance). Brands are anonymized. Neither the paper nor files reviewed establish passenger-car body type. Thus “EV” is verified; “passenger car” is **unverified** against the cars-only project scope.
- Figshare metadata identifies v1, CC BY 4.0 and 1,484,381,511 bytes. The three raw archives were downloaded unchanged to `data/automotive_prognostics/ev_fault_347/v1/raw/`; local byte sizes match metadata and all three archive listings completed successfully.

| Raw archive | Bytes | SHA-256 | Archive inventory |
|---|---:|---|---|
| `battery_brand1.tar.gz` | 1,191,991,306 | `eed43833f20dc81f943512a639c2a1896f4000f1280972270807ec3b19adb0f6` | 416,640 train PKLs; 60,101 test PKLs; train/test label CSVs; `column.pkl` |
| `battery_brand2.tar.gz` | 236,920,600 | `9fa79298743de34fb84f75286159ce3678717877034fea05c0306a13979bfb47` | 119,384 train PKLs; 74,863 test PKLs; train/test label CSVs; `column.pkl` |
| `battery_brand3.tar.gz` | 55,469,605 | `afb5fb2a762cceb5627c112ed2d8d981590274e7f44239321d64384e317b4fd0` | 29,599 PKLs; `all_label.csv`; `column.pkl` |

- Archive totals are 700,587 PKL records. Extracted label CSVs contain respectively 198, 50 and 100 vehicle IDs (348 total), with 55 abnormal and 293 normal labels. The article reports 347 vehicles / 292 normal. The positive count agrees, but the release contains one extra normal ID relative to the article; this discrepancy must be resolved before evaluation. The release labels are per vehicle, not independently documented per charging snippet. Therefore there is a usable binary **vehicle-level abnormal/normal flag**, but no verified snippet-level failure time, prediction horizon, or run-to-failure target. The paper says near-failure data were removed so problems could be detected ahead, but no exact horizon can be established from reviewed metadata. This can support cautious battery anomaly/fault exploration only if vehicle class and label/telemetry joins are confirmed; it cannot support RUL or the intended three-stage chain as-is.
- The feature list in `column.pkl` is `volt`, `current`, `soc`, `max_single_volt`, `min_single_volt`, `max_temp`, `min_temp`, `timestamp`. One inspected record contains metadata keys `label`, `car`, `charge_segment`, `mileage`, giving a plausible vehicle-ID join path. The extraction did **not** exhaustively verify every pickle’s `car`/label join or numeric payload shape. Pickles are executable serialization formats; do not load arbitrary files with unrestricted `pickle.load`. Use a restricted/safe parser and test joins before modeling.
- 20-car rights follow-up: the [maintainer repository README](https://github.com/BatICM/battery-charging-data-of-on-road-electric-vehicles) says the charging data for 20 commercial BAIC EU500 EVs are public and asks users to cite the paper. The repository’s [MIT LICENSE](https://github.com/BatICM/battery-charging-data-of-on-road-electric-vehicles/blob/main/LICENSE) grants rights to “the Software and associated documentation files”; it does not identify the vehicle data archives as licensed data. The paper’s data-availability statement points to GitHub but no separate data license/permission was found. **Data reuse rights remain unresolved**; retain the archives for audit only and do not train, redistribute or publish derived data until a data-specific grant or written permission is located.
- No models were trained. Evidence supports passenger-EV battery telemetry only if car body type is confirmed; the 347-EV target is weak vehicle-level fault status, not a dated outcome. Rights for the 20-car data are not resolved.

### Current task status

1. ✅ Component X v3 terms, targets and joins checked; excluded from passenger-car work as heavy-truck data.
2. ✅ 347-EV release acquired unchanged and archive/label inventories audited; ⚠️ passenger-car body style, exact 347-vs-348 count, complete sample-to-label join, and target horizon unresolved.
3. 🟡 Cars-only scope already decided; the data contract remains blocked on first supported subsystem and legally usable car/EV labels.
4. ⚠️ 20-car EV archive rights not resolved by repository MIT license; obtain a data-specific license or written permission before model work.

Next action: ask the 347-EV authors/publisher to confirm passenger-car body class, explain the 348 released labels versus 347 paper count, and document each sample’s vehicle-label join and prediction cutoff. Separately obtain explicit data rights for the 20-car archive. Do not train on either dataset until its applicable gate is satisfied. No backend/mobile/model-training code has been changed; Step 0 added only `ml/src/reproducibility.py`.

## Workflow Step 1 — formal dataset validation

**Status: ⚠️ Gate failed for a valid three-stage passenger-car chain.**

- Command: `./.venv/bin/python ml/scripts/validate_datasets_step1.py`.
- Output: `ml/reports/data_validation/step1.json`.
- The run checked KIT and carOBD CSV schemas, missing cells, duplicate rows and timestamp ordering; Scania APS CSV labels/missingness/duplicates; DieselOBD XLSX row widths/missingness/duplicates; and tar archive inventories for 347-EV. It did not deserialize arbitrary EV pickle payloads.
- Verified highlights: KIT 81 files/2,693,824 rows/3,653 missing cells/0 duplicates/5 backward timestamp steps; carOBD 129 files/304,299 rows/29,328 duplicates and malformed row widths; DieselOBD 118,477 train and 33,838 test rows with 90,657/26,280 duplicates; APS 60,000 train and 16,000 test rows with 1,000/375 positives and 850,015/228,680 missing tokens; 347-EV tar inventories 476,746/194,253/29,603 members.
- Per-model verdicts are recorded in `datasets.md`: only limited anomaly exploration is partially valid; passenger-car RUL and forward failure classification are invalid; APS/Component X are truck-only; 20-car rights and 347-EV eligibility remain blocked.
- Step 2 is now a decision gate. Recommended strategy: separate, explicitly interfaced passenger-car/EV sources, while continuing to seek a unified licensed source. No download or model training was started.

## Workflow Step 2 — confirmed strategy and passenger-EV replacement audit

Date: 2026-11-13. The user confirmed the recommended strategy: separate passenger-car/EV datasets with explicit interfaces, while continuing to seek a unified licensed source. No backend/mobile files were touched.

### Tongji acquisition and audit

- Added reproducible downloader `scripts/download_tongji_rest.py`; it fetched the official Zenodo record 16868546 archive to `data/automotive_prognostics/tongji_rest/v1/raw/data.zip` and verified the expected 129,606,252 bytes and MD5 `88c3832d748c0adf8caa94173aada563`.
- Verified SHA-256: `45db6baff6b87312081d7341191ea47f5229480f2ea2c92c208acdc2ddd72acd`. The raw archive remains unchanged and ignored by Git. Added provenance at `data/automotive_prognostics/tongji_rest/v1/README.md`.
- Added `ml/scripts/audit_tongji_rest.py` and generated `ml/reports/data_validation/step2_tongji_rest.json`. It parsed the XLSX XML without installing openpyxl: 154 XLSX files, 26,450 data rows, 148 train files, 6 test files, 78 car identifiers, 123–184-column schema variants, and fast/slow feature families.
- Leakage/quality findings: `GE16` and `HQ05` appear in both nominal train and test directories; only `P215` is test-only. The audit counted 39 backward `t_start` steps (30 train-fast, 9 train-slow). `soh`/capacity are health proxies, not a documented run-to-end-of-life or future-failure target. Verdict: candidate SOH/health regression or battery novelty only after a vehicle-disjoint split; not valid RUL or forward failure data.

### Shenzhen metadata verification and blocked acquisition

- Added `scripts/download_shenzhen_ev_fault.py`, `ml/scripts/audit_shenzhen_metadata.py`, and `data/automotive_prognostics/shenzhen_ev_fault/v3/README.md`.
- Official Mendeley snapshot/API confirmed CC BY 4.0, version 3, two XLSX files, 21,175 charging sequences, 1,547,432 one-minute samples, 10,154 EVs and `label=1` faulty battery / `0` normal. The archive metadata reports 207,174,326 bytes and SHA-256 `6b5c77c331e173ac6cab7a0ff2791320cb4fe4c3ffbe9d90205902dbc703eac3`.
- The official S3 asset returned HTTP 403 after repeated direct/API attempts. No partial file was retained. Exact URL to fetch manually if access is restored: `https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/c7gg94tmvz-3.zip`. This is a metadata-only candidate until the files are acquired and audited. Its label is contemporaneous battery fault, not RUL/TTE.

### Gate result

Step 2 is **🟡 partial / gate failed for the complete three-stage chain**. The multi-source strategy is recorded, but no passenger-car run-to-failure/TTE source exists and the Shenzhen files are inaccessible. No model training began. The next decision is whether to revise the scope to battery SOH plus contemporaneous fault classification or keep searching for a licensed car/EV EOL/TTE source.

## Local PR-readiness verification — 2026-11-13

The requested PR could not be raised because this environment has no `gh` executable and GitHub HTTPS push returned `fatal: could not read Username` with prompts disabled. Before handoff, every committed change from `origin/main..HEAD` was checked locally:

| Check | Result / evidence |
|---|---|
| Changed-file inventory | 20 paths reviewed with `git diff --name-status origin/main..HEAD`: the five status reports; `.gitignore`; Step 1/2 audit scripts and JSON reports; requirements lock; reproducibility helper; two download scripts; two dataset provenance READMEs; and the loader contract files `ml/src/data/loaders.py`, `ml/src/data/__init__.py`, `ml/tests/test_loaders.py`. |
| Scope protection | `git diff --name-only origin/main..HEAD | rg '^(backend/|mobile/)'` returned no paths. No backend or mobile files changed. |
| Raw-data protection | `git ls-files 'data/automotive_prognostics/**/raw/**'` returned no tracked raw files. Tongji checksum was revalidated: MD5 `88c3832d748c0adf8caa94173aada563`, SHA-256 `45db6baff6b87312081d7341191ea47f5229480f2ea2c92c208acdc2ddd72acd`, 129,606,252 bytes. |
| Reproducibility | `scripts/download_tongji_rest.py` reported “already verified”; both audit scripts reran successfully; generated reports produced no working-tree diff; the Tongji loader test passed against the local archive. |
| Code quality | Ruff check passed for all four new Python scripts; pre-commit hooks passed on both Step 2 commits; `git diff --check origin/main..HEAD` passed. |
| Tests | `./.venv/bin/python -m pytest -q ml/tests --disable-warnings --maxfail=1`: **43 passed, 5 warnings in 6.63 seconds**. |
| Commit scope | `2c5656b`, `3bf3b10`, `ac6b665`, `d3ed5e0`, `b430843`, and the loader/docs commits are small, ordered commits; no model training, model binaries, secrets, backend/mobile changes, or raw archives were committed. |

## Loader contract implementation — 2026-11-13

- Added `load_tongji_rest` to `ml/src/data/loaders.py` and exported it from `ml/src/data/__init__.py`.
- The loader accepts the verified Tongji ZIP or extracted XLSX files, parses workbook XML with the standard library, supports `split` and `kind` filters, and returns `source_file`, `split`, `feature_kind`, `asset_id`, and `asset_id_type` fields.
- Loader metadata records Zenodo version, CC BY 4.0, identity semantics, health-proxy label semantics, official-split status, and the known `GE16`/`HQ05` overlap warning.
- Existing APS/KIT/carOBD loaders now attach explicit provenance, identity and label semantics through `DataFrame.attrs`; no existing model-training behavior was invoked.
- Added tests for missing paths and the local Tongji test/slow contract. Result: `43 passed, 5 warnings`.
- This PR remains data/ingestion focused. Model training, model metrics and end-to-end claims remain intentionally out of scope.

PR status: **not created** until GitHub credentials/CLI access are supplied. The branch is locally clean on `pipeline/data-and-training`; the only remaining gate is the unresolved passenger-car RUL/TTE scope decision.

## Change log

- 2026-11-13 — Step 0: recorded branch/environment setup, test evidence, seed helper and MLflow limitation.
- 2026-11-13 — Workflow Step 1: added reproducible dataset validation evidence, per-model verdicts, leakage findings, and the Step 2 strategy gate.
- 2026-11-13 — Workflow Step 2: recorded the confirmed multi-source strategy, Tongji acquisition/audit, Shenzhen metadata verification and HTTP 403 block, and the failed complete-chain gate.
- 2026-11-13 — PR-readiness verification: reviewed all 20 changed paths, reran checks/tests/checksums, confirmed no backend/mobile or raw-data commits, and recorded the GitHub authentication blocker.
