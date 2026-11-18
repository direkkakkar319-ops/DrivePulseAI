# KIT anomaly research archive

- `data/kit_obd/`: raw source chunks, locally reassembled recordings when
  available, and prepared 10-second windows.
- `models/`: historical next-window novelty estimator, preprocessing/training
  scripts, and experiment artifacts/reports.

This is not the active Nissan Leaf anomaly model. The existing experimental
serving bundle remains under `ml/hf_deployment/` for API compatibility.
