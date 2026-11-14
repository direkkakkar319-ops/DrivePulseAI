# Oxford Battery Degradation Dataset 1 — local source record

- Official source: [Oxford Research Archive item](https://ora.ox.ac.uk/objects/uuid:03ba4b01-cfed-46d3-9b1a-7d4a7bdf6fac)
- Dataset DOI: `10.5287/bodleian:KO2kdmYGg`
- License: ODC Open Database License 1.0 for the database; Database Contents License 1.0 for individual contents (per the source readme).
- Local originals: `raw/` (Git-ignored; do not add the binary files to Git).

## Files and integrity

| File | Source size (bytes) | Local SHA-256 |
|---|---:|---|
| `Oxford_Battery_Degradation_Dataset_1.mat` | 266,164,290 | `a8f0b928f4ea77d7ba98b97194b78cc77336f2338fee8b57573d043f0cf26781` |
| `ExampleDC_C1.mat` | 72,593 | `144cdf5aec7467bcce5445e132495e8477f4e08d9963c221d8ba5d7970a7a97d` |
| `Readme.txt` | 5,643 | `f04c8bdae97e98632b9daeaa7c71631990dbf5ecbf38711347fc470baefc0def` |

The source record supplies sizes but no file checksums; the hashes above identify the local downloaded copies.

## Data and target audit

The source readme describes eight 740 mAh Kokam pouch cells, tested at 40°C using an urban Artemis drive-cycle discharge. It provides 1C and pseudo-OCV characterization records nominally every 100 drive cycles. The MATLAB file was parsed locally: top-level entries are `Cell1` through `Cell8`, with 519 total characterization records. Each record contains `C1ch`, `C1dc`, `OCVch`, and `OCVdc`; each contains time, voltage, charge, and temperature vectors. Some cycle indices are absent and observation endpoints differ by cell (5,000–8,200 cycles).

The source readme says tests ran until end of life, but does not define the EOL cutoff or provide an explicit per-record RUL target. Any RUL target therefore needs a stated capacity threshold and must account for cells that do not cross it. As an exploratory calculation only, a 75%-of-first-measured-1C-discharge-capacity cutoff is crossed in the released records for 2 of 8 cells; the other six are right-censored at their last record under that convention. This is a small laboratory benchmark, not a real-world EV fleet target. Do not claim passenger-EV field performance from it.

The 2026-11-14 EDA found a further target issue: Cell2's first observed crossing at cycle 7,400 rebounds above the threshold in the next two records. The 7,400 discharge curve is shorter than neighboring records. Cell5's first crossing is at its final record, with no post-crossing follow-up. See [`ml/reports/eda/oxford_battery_eda.md`](../../../../ml/reports/eda/oxford_battery_eda.md).

## Use decision

- **RUL:** not ready for supervised model fitting until the EOL rule and Cell2's transient crossing are resolved. Under the current first-observed 75% rule, only two cells have target rows, and neither has persistent crossing confirmation; meaningful cell-disjoint RUL evaluation is unsupported.
- **SOH/health:** measured capacity trajectories can support a separate laboratory regression benchmark.
- **Failure classification / future failure:** no fault-class or future-event labels are provided in the released files.
- Reproducible local preprocessing and EDA: from the repository root run `python3 ml/scripts/preprocess_oxford_battery.py`, then `python3 ml/scripts/eda_oxford_battery.py`, after installing `ml/requirements.txt`. Outputs stay local and ignored by Git; checked-in EDA reports are in `ml/reports/eda/`. The features table has one row per cell characterization. Keep cells disjoint and do not use measured capacity to predict SOH derived from that same capacity.

Raw source files are retained unchanged and ignored by Git. Preprocessing and EDA do not train a model. Resolve the target definition and threshold-crossing quality before fitting an RUL regressor.

## Citation

Please cite the dataset DOI and Christoph R. Birkl, *Diagnosis and Prognosis of Degradation in Lithium-Ion Batteries*, PhD thesis, University of Oxford, 2017, as requested in the source readme.
