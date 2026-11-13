# Tongji real-world EV SOH release (v1)

- Source: Zenodo record [16868546](https://zenodo.org/records/16868546), DOI `10.5281/zenodo.16868546`.
- License: CC BY 4.0 (metadata and record license; attribution is required).
- Download date: 2026-11-13.
- Raw asset: `raw/data.zip` (129,606,252 bytes).
- Checksums: MD5 `88c3832d748c0adf8caa94173aada563`; SHA-256 `45db6baff6b87312081d7341191ea47f5229480f2ea2c92c208acdc2ddd72acd`.
- Acquisition: `scripts/download_tongji_rest.py`.
- Audit: `ml/scripts/audit_tongji_rest.py`; report `ml/reports/data_validation/step2_tongji_rest.json`.

The archive contains 154 XLSX feature files: 148 under the official `data/data_train/`
directory and 6 under `data/data_test/`. The audit found 28,317 data rows, 78
`car_identifier` values, 123--184 columns depending on file variant, and fast/slow
charging feature families. `soh` and capacity are supplied measurements/features;
there is no documented run-to-end-of-life event or future-failure horizon in this
release. The nominal file split is not an independent-vehicle split: `GE16` and
`HQ05` occur in both train and test, while only `P215` is test-only. These facts make
the release useful for a carefully split SOH/health-score benchmark, but not a
validated RUL or forward-failure dataset without an additional event definition.

Raw files are intentionally not committed. This README and the audit report are the
provenance record; the original archive must remain unchanged.

`load_tongji_rest` now constructs a vehicle-disjoint partition: every row for a
`car_identifier` found in the official test directory is assigned to evaluation,
including the official-train rows for `GE16` and `HQ05`. The resulting evaluation
group contains only three identified vehicles (`GE16`, `HQ05`, `P215`), so its
small asset count must be considered when interpreting any later benchmark. The
loader retains the original directory in `source_split` and exposes the corrected
partition in `split`. For rows without a `car_identifier`, the loader uses the
source workbook stem and reports `asset_id_type=file_stem`; this fallback is not a
verified vehicle identity.
