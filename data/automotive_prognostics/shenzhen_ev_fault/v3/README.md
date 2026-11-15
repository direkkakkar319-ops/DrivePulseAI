# Shenzhen EV charging fault release (v3)

- Source: [Mendeley Data DOI 10.17632/c7gg94tmvz.3](https://data.mendeley.com/datasets/c7gg94tmvz/3).
- Official metadata API: `https://data.mendeley.com/api/datasets-v2/datasets/c7gg94tmvz/zip?version=3`.
- License: CC BY 4.0 (confirmed in the official Mendeley snapshot/API metadata).
- Release metadata: 207,174,326 bytes; SHA-256
  `6b5c77c331e173ac6cab7a0ff2791320cb4fe4c3ffbe9d90205902dbc703eac3`.
- Intended files: `processed_data.xlsx` and `processed_data_longer_than_30.xlsx`.
- Acquisition script: `scripts/download_shenzhen_ev_fault.py`.

The official description reports 21,175 charging sequences, 1,547,432 one-minute
samples, 10,154 EVs, and a `label` where 1 means a faulty battery and 0 normal.
The metadata describes engineering-reported faults and high-temperature station
disconnects; this is a contemporaneous battery-fault classification label, not a
documented future-failure horizon or RUL target. The primary description does not
explicitly identify vehicle body class; the passenger-EV classification is supported
by the secondary Astrolabe registry and must be rechecked after file acquisition.

The release was not acquired on 2026-11-13: the official API returned the S3 asset
URL, but that URL returned HTTP 403 from this environment after repeated direct and
API attempts. No partial/raw file is retained. Exact URL to fetch manually if the
network policy changes: `https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/c7gg94tmvz-3.zip`.
