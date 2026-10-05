# DieselOBD source and classification suitability verification

Checked 2026-10-06 against https://github.com/AbouAbdallah-Lounis/OBD-Dataset. Existing workbooks and prior audit/EDA reports were not modified. No upstream Python code was executed and no classifier was trained.

## Provenance verified

The local workbook bytes match the author's GitHub blob identifiers:

| File | Local / upstream Git blob SHA-1 | Result |
| --- | --- | --- |
| `MASTER_TRAIN_X.xlsx` | `ca5fcf99ae8d2edc7c04b5636a1b18839df7dd52` | Identical |
| `MASTER_TEST_X.xlsx` | `f76b794fac48ee3f2ad74214757272e7ab2cd9e6` | Identical |

This identifies the source of our copies; it does not independently verify the author's collection claims, vehicle labels, physical diagnoses or split construction. The earlier audit's provenance uncertainty is resolved for file identity only. Its other concerns remain relevant.

The downloaded README describes eight diesel vehicles (cars, SUVs and vans), three without active DTCs and five with documented DTCs. It declares CC BY 4.0; preserve attribution. Vehicle count is small and some faults are associated with only one vehicle. No-active-DTC status is not proof of complete mechanical health.

## Actual local schema

There are 11 PID sensor columns, 14 P-code columns and `Mode`, plus an unnamed blank Excel column. There is no vehicle identifier, session identifier, timestamp, or explicit `healthy/faulty` column in the supplied workbooks. The README's example with `vehicle_id` and `label` is not the actual workbook schema.

The upstream `MODEL.py` treats each P-code as a separate binary target using `value > 0`. All P-code columns must be excluded from sensor predictors. `Mode` has values 0, 1, 2 and is called a label by the feature scripts, but its meaning is not documented in the inspected material; the model script leaves it in predictors. Do not use `Mode` as a predictor without verifying its meaning and availability at inference time.

`P0000` might represent the no-code condition, but the inspected README/code does not give an explicit semantic definition sufficient to certify it as a mechanically healthy label. Never automatically equate `P0000 == 0` with faulty.

## Independent workbook checks

Both workbooks were parsed with ZIP/XML readers without changing them. Checks respect Excel column references and inspect all 26 named columns. The always-blank extra column is excluded from named-cell and duplicate checks.

| Finding | Train | Test |
| --- | ---: | ---: |
| Rows | 118,477 | 33,838 |
| Repeated full rows beyond first occurrence | 90,657 | 26,280 |
| Repeated 11-sensor predictor rows beyond first occurrence | 90,657 | 26,280 |
| `P0000 == 1` | 29,674 | 11,940 |
| At least one other P-code positive | 84,412 | 20,802 |
| Neither `P0000` nor another P-code positive | 4,391 | 1,096 |
| Both `P0000` and another P-code positive | 0 | 0 |
| Missing named cells | 0 | 0 |

There are **173 distinct full-row patterns shared between train and test**, and also **173 distinct 11-sensor predictor patterns shared between them**. Counts refer to unique patterns, not all repeated occurrences. Repeated rounded sensor values alone do not prove repeated physical events; event grouping information is missing. A near-duplicate investigation has not been performed in this verification.

The 5,487 all-zero P-code rows prevent an exhaustive certified healthy/faulty mapping from current columns. They need an author explanation, rather than assigning a health label by assumption. Even the other rows need an explicit label dictionary and acquisition context.

## Further upstream implementation concerns

The feature scripts exclude P-code labels from feature calculations, which is appropriate. However, they compute differences and overlapping windows across the entire row sequence without vehicle/session boundaries. After dropping missing rows, adjacent rows are still treated as a continuous sequence. We cannot verify that such windows stay inside a recording. Example downstream input CSVs referenced by these scripts are not supplied as equivalent documented releases here.

The training workbook identity does not establish a trustworthy held-out-vehicle split. Author-provided per-vehicle/per-session recordings and their membership in the supplied splits are needed. Do not silently combine/resplit the existing test workbook or remove raw duplicates.

## Decision

**Promising source for a diesel DTC-status classifier, not ready for credible general passenger-car healthy/faulty evaluation.** Request the original per-vehicle recordings, vehicle/session IDs, timestamp and sampling definitions, P0000/Mode dictionary, explanation of all-zero labels, unit definitions (especially vehicle-dependent fuel rail pressure), and split construction. Resolve overlap before reporting a held-out score.

For anomaly detection, a confirmed no-fault population might eventually be useful, but currently no-code status is only a proxy. Neither workbook provides a RUL/time-to-event target.

`verification.json` contains source identity checks, SHA-256 checksums, actual columns, counts, and cross-split results. Other files in this directory are snapshots of the author's documentation and code for review, not executable project dependencies.
