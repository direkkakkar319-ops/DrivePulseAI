# Data outside the current passenger-car prototypes

These datasets are retained, not deleted. They are excluded from the current two-task plan until their limitations are resolved or a separate benchmark is intentionally run. Raw bytes, supplied splits, duplicate rows and distinct source variants are preserved.

| Dataset | Why deferred | What would change its status |
| --- | --- | --- |
| DieselOBD | 173 shared train/test predictor patterns; 5,487 all-zero label rows; missing vehicle/session IDs and timestamps; unclear `P0000`/`Mode` | Author-confirmed label/split dictionary, original grouped recordings and overlap investigation |
| carOBD | Known malformed/short rows; no verified healthy/fault labels; limited vehicle population | Schema/label verification and an explicitly agreed telemetry experiment |
| Scania APS | Heavy-truck APS-versus-other-failures classification, not healthy passenger-car classification | A separately scoped truck benchmark; no relabeling can make it car-health data |

## DieselOBD

`dieselobd/raw/` contains the original Train/Test workbooks. `dieselobd/source_verification/FINDINGS.md` and `verification.json` document matching file identities against the author, actual label counts, duplicate checks and remaining questions. Source identity is verified; acquisition claims and label semantics are not independently certified. Downloaded source Python files are review artifacts, not dependencies to execute.

## carOBD

`carobd/raw/` retains all 129 original local recordings. Added source information is in `carobd/source_verification/`: the [author's README](https://github.com/eron93br/carOBD), an upstream inventory pinned to commit `bf09e1c00f8443212fdbf4b09e8b2a468badd775`, a comparison report and eight differing upstream CSVs in `upstream_raw/`.

121 local CSVs match upstream Git blob hashes exactly; eight differ. All eight fetched comparison files match the pinned upstream hashes. They were not selected as replacements or mixed into the canonical local data. The upstream copies also contain the known short rows in `idle1.csv`, `live16.csv`, `ufpe4.csv`, and 24-field records under a 27-column header in `live6.csv`. They do not repair those defects. Other differences include blank lines and require review; do not infer that every difference indicates corruption.

The author describes a Toyota Etios 2014 recording setup at 1 Hz, drive/idle/trip conditions and an informal open-source/citation statement. Matching files establishes a provenance connection, not verified fault-free status or independent cars. Conditions are not mechanical-fault labels; runtime is not wall-clock time. The earlier local audit counted 29,328 repeated rows, retained here. Explicit units/reuse terms and any healthy/fault annotations require review.

## Scania APS

`scania_aps/raw/` retains 60,000 training and 16,000 test observations plus the supplied description and license notice. `pos` is a specified APS component failure; `neg` is another component failure. The 170 predictors are anonymized counters/histogram bins, with no established independent vehicle IDs or timeline. These files do not provide passenger-car RUL labels.

The prior UDA EDA PR was closed and its branch deleted; do not attribute its generated artifacts to the current branch. The saved dataset and existing main-branch Scania code remain available for their documented truck task.
