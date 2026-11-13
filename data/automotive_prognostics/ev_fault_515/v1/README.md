# Real-world EV battery fault-diagnosis dataset — local source record

- Official data record: [Zenodo 10.5281/zenodo.10656500](https://zenodo.org/records/10656500)
- Paper: [Cao et al., Nature Communications (2025)](https://doi.org/10.1038/s41467-025-56832-8)
- License reported by Zenodo API: CC BY 4.0.
- Local originals: `raw/` (Git-ignored; do not add the large archives to Git).

## Download and integrity

All seven original archives were downloaded from Zenodo's record API. The byte counts and MD5 sums below match the record's file metadata.

| File | Bytes | MD5 |
|---|---:|---|
| `DTI.zip` | 2,645,761,724 | `400135e26d8bac65cc171e63f71fd5dd` |
| `GIS.zip` | 389,438,075 | `2b4d5f9d0d045bbe5bb0318ea84f7e7e` |
| `QAS_1.zip` | 6,822,055,228 | `a3d3a182c7c82df26073a53f698148c8` |
| `QAS_2.zip` | 6,927,601,162 | `9183ff01f6cf3e187716ca3a2d7f6b53` |
| `QAS_3.zip` | 6,990,430,806 | `7cb6410cac2c44890eaccd9d594887bf` |
| `QAS_4.zip` | 5,949,401,675 | `d138ef98e2fb77c12afc88a6043e3be8` |
| `QAS_5.zip` | 8,338,767,634 | `f420b38bab7aca514ab834cbfa0010b8` |

Total: 38,063,456,304 bytes. No archive was extracted into the repository.

## Structural and label audit

The archives contain three `.pkl` tensor files named `vin_1.pkl`, `vin_2.pkl`, and `vin_3.pkl` per numbered folder. Static ZIP-directory inspection found 514 folders: DTI 80, GIS 41, QAS 393. The QAS IDs cover 0–392 across the five archives. The record and paper state 515 vehicles, leaving a one-vehicle discrepancy that is not explained by the release.

`DTI.zip` contains `Labels.xls` with columns `Num` and `Label`, 80 unique IDs (0–79), and counts 77 label-0 / 3 label-1. `QAS_5.zip` contains another `Labels.xls`, with 393 unique IDs (0–392), and counts 335 label-0 / 58 label-1. No corresponding label or README file appears in the GIS or QAS_1–QAS_4 ZIP directory listings. The spreadsheets do not define the meaning of 0/1, and no vehicle-name/VIN mapping is included. Do not assume the values mean normal/fault until that semantics and the ID joins are confirmed.

The paper reports 1,135 abnormal-moment samples with four-bit labels for internal short circuit, excessive aging, thermal runaway, and electrolyte leakage; it says fault labels were assigned retrospectively by product engineers after pack disassembly. The delivered vehicle archives do not provide a verified join from those four-class event labels to the numbered folders and tensor rows. The paper's 3:1 split is sample-level and does not establish vehicle-disjoint evaluation.

The `.pkl` files use PyTorch tensor serialization. They were not unpickled. The paper's released code refers to `Name_list.xls`, which is not in the code repository or the inspected DTI/GIS/QAS_1 archives; the ZIPs instead contain the two generic `Labels.xls` files described above. A safe loader and authoritative label/vehicle/sample mapping remain outstanding.

## Use decision

- **Current fault classification:** promising real-EV candidate; not ready for training until the label semantics, sample-level 4-class labels, and joins are recovered and audited. Any eventual evaluation must split by vehicle.
- **Future-failure prediction:** not established. Retrospective labels for already abnormal moments do not define a future prediction horizon or censoring rule.
- **RUL:** unsupported; no end-of-life target or per-vehicle run-to-EOL time is documented.
- No training or preprocessing has been performed. Keep all originals local and ignored by Git.

## Citation

Rui Cao et al., “Model-constrained deep learning for online fault diagnosis in Li-ion batteries over stochastic conditions,” *Nature Communications* 16, 1651 (2025), DOI `10.1038/s41467-025-56832-8`; data DOI `10.5281/zenodo.10656500`.
