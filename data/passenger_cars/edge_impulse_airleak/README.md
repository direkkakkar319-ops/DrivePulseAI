# Edge Impulse healthy / induced-air-leak OBD dataset

Downloaded and checked on 2026-10-06. This is a narrow classification/anomaly demonstration, not a general passenger-car health dataset. No model was trained during this download.

## Sources and contents

- Public project: https://studio.edgeimpulse.com/public/767694/live
- Collection repository: https://github.com/edgeimpulse/obd-automotive-data
- `raw/training/`: all 184 publicly listed JSON samples (92 `healthy`, 92 `airleak_nox`).
- `raw/testing/`: all 46 publicly listed JSON samples (23 per label).
- Total: 230 samples, 4,800 sensor rows, sampled at 500 ms intervals (2 Hz).
- Features: RPM, pedal input, MAF, NOx. Unit hints are in sensor names; JSON sensor `units` fields say `N/A`.
- `download_manifest.json`: sample IDs, original names, labels, supplied partitions, download URLs, row counts, sensor metadata and SHA-256 checksums.
- `source/`: public listing snapshots, collection README/license, and the two original CSV recordings from the collection repository (2,400 rows per recording).
- `validation.json`: download verification, source checksums and exact overlap checks.

The label is recorded in the manifest; individual downloaded JSON payloads do not contain a label field. Join JSON files to their manifest entries using their numeric sample IDs. Preserve the supplied partition and original sample name when loading.

The source CSVs and public JSON samples contain the same sensor data in different packaging. Do not recursively combine `source/` and `raw/` as independent training examples.

## Integrity results

All listed samples downloaded and parsed successfully. Every manifest checksum was rechecked. Sensor rows have the expected four values; no missing/nonfinite sensor cells were found. Every public sensor pattern is present in the original source CSVs.

No exact four-feature sensor patterns or identical whole-sample sequences were shared across the supplied train/test split. These checks do not establish absence of near duplicates, adjacent-window dependence, or independence between recording sessions/vehicles.

## What the labels establish

The collection README describes an unhealthy condition induced by disconnecting an intake sensor or vacuum line. Its BMW example and the `n53_*` filenames provide context, not proof of a diverse vehicle population. The labels distinguish the recorded healthy condition from this particular induced condition. The available material does not certify overall mechanical health or detection of unrelated faults, and we have not independently validated physical acquisition/authenticity.

The public samples are portions of the two condition-specific source recordings. The supplied 80/20 split therefore does not establish performance on new cars or independent recording sessions. A classifier might exploit recording/operating-condition differences. For a credible evaluation, obtain independently collected healthy/faulty sessions, vehicle/session identifiers and confirmed diagnoses; split by session/vehicle before constructing windows. Do not fabricate missing groups or shuffle rows to imply independence.

This can support an exploratory binary classifier or anomaly-method demonstration using the explicitly healthy recording. No time-to-failure/RUL target exists. MAF/NOx availability must match the intended app; NOx support is vehicle dependent according to the collection documentation.

## Licensing and provenance

The collection repository includes a BSD-3-Clause license, preserved in `source/collection_LICENSE`. The downloaded public project does not provide a separate explicit dataset-license statement in its listing; do not infer unrestricted reuse solely from public access. Source SHA-256 checksums preserve the fetched snapshots, rather than asserting an upstream release version. Original files, labels and supplied splits were not edited.
