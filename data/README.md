# Passenger-car data plan

The current scope is **two experimental ML tasks**: unusual-behaviour detection and narrow condition classification. RUL prediction, general healthy/faulty diagnosis and truck-component prediction are outside the current passenger-car plan. See [the ML plan](../ml/README.md).

Updated 2026-10-06. Dataset placement means selected for exploration, not certified for production. Original raw bytes, labels, supplied splits and existing ML notebooks/reports are preserved. No model was trained as part of this reorganization.

## Directory layout

```text
data/
├── passenger_cars/
│   ├── edge_impulse_airleak/   # Labeled, narrow intake-condition demonstration
│   │   ├── raw/training/      # 184 original public JSON samples
│   │   ├── raw/testing/       # 46 original public JSON samples
│   │   ├── source/            # Original CSVs, listing snapshots, documentation
│   │   ├── download_manifest.json
│   │   ├── validation.json
│   │   └── README.md
│   └── kit_obd/               # Unlabeled passenger-car telemetry exploration
│       └── raw/              # Extracted recordings and original BagIt payload
├── deferred/
│   ├── dieselobd/             # Labels/split independence unresolved
│   ├── carobd/                # Schema defects; no verified health labels
│   ├── scania_aps/            # Heavy-truck classification benchmark
│   └── README.md
└── organization/             # Historical README, move/download hashes, verifier
```

Each dataset has one canonical directory; do not copy it into one folder per model. Task-specific selections and partitions belong in future processing outputs, not duplicated raw collections.

## Selected data and what it supports

| Dataset | Current role | Evidence and limitations |
| --- | --- | --- |
| Edge Impulse | Narrow classifier; labeled-condition anomaly demonstration | 230 public samples, 4,800 sensor rows at 2 Hz. Labels `healthy` and `airleak_nox`. Two condition-specific source recordings; not independent-car validation. |
| KIT OBD-II | Telemetry EDA and anomaly-method exploration | 81 Seat Leon recordings, 2,693,824 rows. No verified mechanical-health/failure labels or established independent vehicle population. |

### Edge Impulse

Sources: [public project](https://studio.edgeimpulse.com/public/767694/live) and [collection repository](https://github.com/edgeimpulse/obd-automotive-data).

The healthy and induced intake-related conditions have 92 training and 23 testing samples each. Features are RPM, pedal input, MAF and NOx. No missing/nonfinite sensor cells, exact cross-split sensor patterns or identical whole-sample sequences were found by the saved checks. This does not prove session independence or absence of near duplicates.

All public sensor values match patterns in the two supplied original CSVs. JSON labels are in `download_manifest.json`, not inside the sensor payloads; retain sample ID, original name, partition and label when loading. Do not ingest both `raw/` and the source CSVs as separate examples. The source `collect_obd_data.py` was added as documentation, not executed.

The collection README describes a condition induced by disconnecting an intake sensor or vacuum line. The task is recorded healthy versus recorded intake-related condition, not overall car health or broad fault diagnosis. Physical acquisition and mechanical health have not been independently certified. The collection repository has a preserved BSD-3-Clause license; the public sample listing provides no separate dataset-license statement.

### KIT Automotive OBD-II

Supplied metadata identifies Marc Weber, KIT, RADAR DOI `10.35097/1130` / KITopen DOI `10.5445/IR/1000085073`, and CC BY 4.0. Read only `passenger_cars/kit_obd/raw/recordings/OBD-II-Dataset/` for telemetry. The original BagIt archive and manifests are provenance artifacts, not additional observations.

The 11 columns contain time plus coolant temperature, manifold pressure, RPM, speed, intake-air temperature, MAF, throttle, ambient temperature and pedal D/E. There is no NOx or control-module voltage field: do not invent them to match another dataset.

Blank cells and five small backward timestamp jumps were found in the earlier audit. Time is time-of-day; filenames supply dates but not timezone. Road-condition filenames are not fault labels. There were no repeated full rows within individual recordings in the earlier checks. Unlabeled telemetry can support unusual-pattern exploration, but cannot establish mechanical-fault accuracy or be assumed entirely healthy.

## Deferred data

[Deferred inventory](deferred/README.md) explains why DieselOBD, carOBD and Scania APS are retained separately. Do not recursively feed this folder into the passenger-car pipelines.

DieselOBD's source-file identity is verified, but 173 distinct predictor patterns overlap across its supplied train/test workbooks, 5,487 rows have all-zero P-code labels, and vehicle/session identifiers are absent. carOBD has no established health labels and retains short-row defects. Scania APS distinguishes a specific truck APS failure from other failures; `neg` does not mean healthy.

VED, AI4I, C-MAPSS and Component X files were already removed before this branch was created from `origin/main`; they were not deleted by this reorganization and are not present to archive. We did not redownload industrial/aircraft/truck datasets for the passenger-car scope. The historical README describes earlier inventories, not the current contents.

## What is still missing

For credible passenger-car evaluation, we need independently recorded vehicles/sessions with vehicle and session IDs, timestamps, documented units and sensor availability, confirmed fault diagnoses and documented healthy checks, plus comparable operating conditions across labels. Split by the appropriate vehicle/session grouping before creating windows.

For DieselOBD, the missing label dictionary must explain `P0000`, `Mode` and all-zero rows, along with split construction and per-vehicle recordings. For Edge Impulse, more independent labeled sessions and vehicles are needed. The checked public sources do not provide these verified missing elements; downloading more windows from the same two recordings would not solve that gap. No labels or group identities were fabricated.

## Preservation and existing code

Raw data is not cleaned, deduplicated, relabeled or resplit in this change. Source bytes, existing variants, original labels, archives and official/supplied partitions are retained. Learned imputation/scaling must later fit on training only; outliers are investigated rather than automatically deleted.

The APS training script and loader-test data paths were updated to the relocated directories; algorithm behaviour is unchanged. Existing notebooks/reports remain untouched. To run the preserved truck EDA explicitly, use:

```bash
python ml/notebooks/eda_aps.py --data-dir data/deferred/scania_aps/raw --no-show
```

That is a truck benchmark command, not the new passenger-car workflow. An Edge Impulse manifest-aware loader and the passenger-car experiment pipeline remain future work. KIT/carOBD filename-derived `vehicle_id` values in existing loaders represent recordings, not proven independent vehicles.

The root project README and legacy model files still contain the earlier broader scope. This data README and the new ML README document the agreed plan; no application/model restructuring was requested in this change.

## Verify organization

`organization/passenger-car-move-manifest.json` records old/new relative paths, sizes and SHA-256 for all 487 relocated files, including earlier uncommitted downloads. The previous data README is preserved in `organization/README.before-passenger-car-plan.md`. New upstream additions are recorded separately in `organization/new-downloads-manifest.json`.

```bash
python data/organization/verify_passenger_car_data.py
```

This verifier reads files and checks hashes; it never repairs or modifies data. Passing means byte preservation and sample availability, not scientific suitability, healthy labels or leak-free evaluation.
