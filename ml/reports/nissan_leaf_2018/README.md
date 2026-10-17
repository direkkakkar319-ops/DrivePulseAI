# 2018 Nissan Leaf dataset — acquisition and EDA

Purpose: preserve the official MPU telemetry downloads and document their contents without training models or changing observations.

**Start here: [complete EDA report](EDA_REPORT.md).** In VS Code use Ctrl+Shift+V to preview the report with plots. Reports and outputs are in `ml/reports/nissan_leaf_2018/`; executable scripts are in `ml/notebooks/nissan_leaf_2018/scripts/`. Only source telemetry remains in `data/nissan_leaf_2018/`.

## Layout

| Path | Contents |
| --- | --- |
| `data/nissan_leaf_2018/raw/Dataset_NissanLeaf-2021_2022.csv` | Official publisher-labelled raw CSV, unchanged; Git-ignored |
| `data/nissan_leaf_2018/processed/Dataset_Preprocessed.csv` | Official preprocessed CSV, unchanged; Git-ignored |
| `metadata/` | Source page, original XLSX, extracted dictionary, URLs/checksums, HTTP headers, access failures, source notes |
| `ml/notebooks/nissan_leaf_2018/scripts/acquire.py` | Download/verify original files and record provenance; existing files are reused |
| `ml/notebooks/nissan_leaf_2018/scripts/dictionary.py` | Extract XLSX using the standard library and document column aliases/roles |
| `ml/notebooks/nissan_leaf_2018/scripts/run_eda.py` | Full-row EDA using CSV chunks and temporary disk-backed arrays; raw/processed comparison |
| `ml/notebooks/nissan_leaf_2018/scripts/validate.py` | Independent CSV record-width/count checks, source hashes and report accounting |
| `ml/notebooks/nissan_leaf_2018/scripts/build_report.py` | Build the complete Markdown report from measured outputs |
| `tables/{processed,raw}/` | Dictionaries, statistics, missing patterns/runs, duplicates, sessions, boundaries, distributions, correlations and integrity findings |
| `tables/raw_processed_*.csv/json` | Exact index/timestamp alignment and verified differences |
| `tables/retained_vs_removed_raw_rows.csv` | Distribution comparison of raw records present/absent in processed; “removed” does not establish a particular preprocessing operation |
| `figures/{processed,raw}/` | Missingness, histograms, boxplots, correlations, time series, SOH history and sampling intervals |
| `./` | Final report, software/code fingerprints, independent validation results and report hash |

No separate schema is declared mandatory by the publisher. Header names are preserved; Pandas aliases the raw blank first header to `Unnamed: 0.1` because a literal `Unnamed: 0` column already exists. Every original header is recorded in the dictionary and overview JSON. Numeric storage does not make identifiers, timestamps or status codes sensor measurements or selected ML features.

## Reproduce from the repository root

The existing virtual environment used Python 3.12.13, pandas 2.3.3, NumPy 2.5.1 and Matplotlib 3.11.1. XLSX extraction uses `zipfile` and XML from the standard library, so no Excel library or new dependency was installed. `curl` is required for acquisition.

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/acquire.py
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/run_eda.py
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/validate.py
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/build_report.py
.venv/bin/ruff check ml/notebooks/nissan_leaf_2018/scripts
```

Acquisition verifies the file sizes observed on the official server. If the publisher replaces a release, the script stops on unexpected size; inspect/review provenance rather than silently accepting a different file. Existing files are never overwritten. The saved checksums establish the local snapshot; the publisher did not supply an independent checksum for comparison. For files already downloaded as `.part`, use:

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/acquire.py --finalize-existing
```

The completed acquisition used the following official URLs (curl flags: `-L --fail --connect-timeout 20 --max-time 1800 --retry 2 --silent --show-error`, with `-D` to save headers and `-o` for `.part` destinations):

```text
https://ubilab.mpu.edu.mo/data.html
https://ubilab.mpu.edu.mo/Dataset_Preprocessed.csv
https://ubilab.mpu.edu.mo/Dataset_NissanLeaf-2021_2022.csv
https://ubilab.mpu.edu.mo/Nissan_Leaf_Model2018_Data_Description.xlsx
```

The slow raw download was paused at 540,336,128 bytes and resumed as six parallel HTTP byte ranges. Each returned Content-Range and expected length were verified; If-Range used the original ETag. Parts were appended in source order. Exact ranges are in `metadata/raw_range_transfer.json`; the normal acquisition command reproduces the same file with a single transfer. Network sandbox approval was needed in this environment. The optional institutional paper PDF returned HTTP 403; no PDF download is claimed.

Plan for ~2 GB of source files, several GiB of temporary disk-backed numeric arrays and several GiB of available RAM. Disk free space was 86 GB before downloads. CSV reads use 75,000-row chunks. Most statistics/correlations use all rows; plot subsampling is explicitly labelled. Rerunning EDA replaces only generated tables/figures/reports, never raw or processed source CSVs. Main EDA and validation each recheck source hashes.

## Interpretation

The final report separates confirmed file facts from suspected measurement issues and undocumented definitions. Zero missingness in processed does not mean clean physical telemetry. −1 is a legitimate off state for some controls and a suspected unavailable code in other channels; it was never automatically replaced. All rows are preserved. No model was trained or selected. A passing integrity audit is not a certification of sensor accuracy.

No explicit dataset license was found; the source requests citation. Downloaded CSVs stay Git-ignored. Scripts, metadata, figures and reports remain trackable. Nothing was committed or pushed as part of this task.

## Reorganization

The original analysis execution fingerprint is preserved in `metadata/pre_reorganization_run_manifest.json`. The current execution manifest records the relocated scripts. Source checksums remain unchanged. Manifest source paths beginning with `raw/` or `processed/` resolve under `data/nissan_leaf_2018`; `metadata/` resolves under `ml/reports/nissan_leaf_2018`. The manifest also records repository-relative telemetry/workbook locations.

## ML readiness assessment

Purpose: assess supported tasks, SOH shortcuts, temporal leakage and remaining data-quality questions before selecting models.

Open [ML_READINESS_REPORT.md](ML_READINESS_REPORT.md) for the complete assessment, [the feature inventory](tables/readiness/feature_inventory.csv) for all 124 source-column entries, and [READINESS_VALIDATION.md](READINESS_VALIDATION.md) for checks and the complete new-file index. Supporting tables and figures are in `tables/readiness/` and `figures/readiness/`. This assessment reuses the existing EDA; it does not change source datasets or train models.

Run these commands in order, waiting for analysis completion before tests (the manifest describes the completed run):

```bash
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/readiness.py
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python -m pytest ml/tests/test_nissan_leaf_readiness.py -q
.venv/bin/ruff check ml/notebooks/nissan_leaf_2018/scripts/readiness.py ml/notebooks/nissan_leaf_2018/scripts/readiness_report.py ml/tests/test_nissan_leaf_readiness.py
```

The analysis uses the existing pandas, NumPy, Matplotlib and SciPy environment. Tests read only small original-data excerpts and lightweight outputs, so the downloaded files must be present. No dependencies were installed for this assessment.

## Phase 1: data preparation

Purpose: create auditable raw-only experimental views, temporal splits and training-only transformations without training models.

Start with [DATA_PREPARATION_REPORT.md](DATA_PREPARATION_REPORT.md). The implementation lives in `ml/src/nissan_leaf_preparation/`; its reviewed configuration is `ml/notebooks/nissan_leaf_2018/config/preparation.json`. Trackable audit tables and manifests are in `tables/preparation/`. Large Parquet outputs and fitted artifacts are under the already-ignored `ml/artifacts/nissan_leaf_2018/preparation/<run-id>/`. See [PREPARATION_VALIDATION.md](PREPARATION_VALIDATION.md) for executed checks and a file index.

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests/test_nissan_leaf_preparation.py
```

Repeat the preparation command to recompute independently and compare output hashes. It requires the original downloads and prior EDA/readiness outputs. Source files are never changed. Raw and processed releases are not pooled: processed is comparison-audit only. Anomaly and future logged-temperature datasets are conditional; energy targets remain blocked by unresolved semantics. Select `transformer.output_features` from feature Parquets; `source_row` is an audit join key, not an input. Sequence inputs stop at the anchor and reference original observed rows; future targets must remain separate.

## Phase 1.1: battery-only preparation

Open [BATTERY_ONLY_PREPARATION_REPORT.md](BATTERY_ONLY_PREPARATION_REPORT.md) for the separately versioned three-feature view and [BATTERY_ONLY_VALIDATION.md](BATTERY_ONLY_VALIDATION.md) for executed checks. The configuration is `ml/notebooks/nissan_leaf_2018/config/battery_only.json`; trackable results are in `tables/battery_only/`.

This view inherits the original run's exact trip assignments and preserves its artifacts. Battery eligibility does not require drivetrain telemetry. Feature Parquets contain only HV_Bat_Voltage, Pack_1_C_Temp and SOC; aligned companion metadata holds lineage and flags. Compact temperature indices reference observed rows and targets, with no copied sequence arrays.

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py --config ml/notebooks/nissan_leaf_2018/config/battery_only.json
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_preparation ml/notebooks/nissan_leaf_2018/scripts/prepare_data.py ml/tests
```

Run the first command again for independent computation and byte-checksum comparison. Original sources and parent artifacts must remain present and match pinned hashes. Both experiments remain conditional: these are unlabeled battery observations and logged-temperature targets, not verified battery faults or independently calibrated thermal ground truth.

## Phase 2: experimental battery Isolation Forest

Open [ISOLATION_FOREST_BASELINE_REPORT.md](ISOLATION_FOREST_BASELINE_REPORT.md) for the first trained battery-pattern baseline, score plots and review candidates. [ISOLATION_FOREST_VALIDATION.md](ISOLATION_FOREST_VALIDATION.md) records tests and reproducibility checks.

Implementation: `ml/src/nissan_leaf_isolation/`. Configuration: `ml/notebooks/nissan_leaf_2018/config/isolation_forest.json`. Experiment artifacts are stored separately under the ignored `ml/artifacts/nissan_leaf_2018/isolation_forest/<experiment-id>/`. Tables and figures use matching experiment-ID subdirectories under this reports folder.

```bash
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage develop
.venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage test
MPLCONFIGDIR=/tmp/drivepulse-matplotlib .venv/bin/python ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py --stage report
.venv/bin/python -m pytest ml/tests -q
.venv/bin/ruff check ml/src/nissan_leaf_isolation ml/notebooks/nissan_leaf_2018/scripts/train_isolation_forest.py ml/tests
```

Run in order from a clean experiment workspace. Existing experiment outputs are never overwritten; test scoring is allowed once after the development protocol is frozen. Development includes deterministic same-seed reconstruction. Reporting uses saved scores and never rescores test data. The provisional alert budget is a review policy, not a fault prevalence estimate. Unusual battery telemetry is not a confirmed battery fault.
