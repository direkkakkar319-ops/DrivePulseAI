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
