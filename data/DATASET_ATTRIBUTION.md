# Dataset attribution and reuse

Dataset terms are separate from the repository software license.

## KIT Automotive OBD-II

- Citation: Weber, Marc (2023). *Automotive OBD-II Dataset*. Karlsruhe
  Institute of Technology. DOI: [10.35097/1130](https://doi.org/10.35097/1130).
- License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
- The complete publisher BagIt archive is included in three repository-sized
  parts under `automotive_obd/kit_obd/raw_chunks/`. Reconstruct it with
  `automotive_obd/kit_obd/reassemble_source.py`; the script checks the
  publisher-listed archive MD5 (`22d9aac00d1a2b4c97aa35fd7a103ba4`).
- The prepared 10-second windows used by the KIT forecasting experiment are
  also included under `automotive_obd/kit_obd/processed/`. See
  `ml/scripts/preprocess_kit_obd.py` for the reproducible preparation steps.

## Oxford Battery Degradation Dataset 1

- Citation: Howey, D. and Birkl, C. (2017). *Oxford Battery Degradation Dataset
  1*. University of Oxford. DOI:
  [10.5287/bodleian:KO2kdmYGg](https://doi.org/10.5287/bodleian:KO2kdmYGg).
- The source README requests citation of Christoph R. Birkl (2017), *Diagnosis
  and Prognosis of Degradation in Lithium-Ion Batteries*, PhD thesis, University
  of Oxford.
- License: [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
  for the database and [Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/)
  for individual contents, as stated in the publisher's README.
- The large MAT file is split into repository-sized parts under
  `automotive_prognostics/oxford_battery_degradation/v1/raw_chunks/`. Reassemble
  and verify it with `reassemble_source.py`. Keep the accompanying source
  `Readme.txt` and this attribution when redistributing the parts.

Neither dataset supports unqualified passenger-EV fault or RUL claims; see the
dataset audits and modeling reports for task-specific limitations.
