# Archived model work

These folders hold earlier model tracks and their datasets. Active Nissan Leaf
health scoring and RUL code remains under `ml/src/` and `ml/scripts/`.

- `oxford/`: laboratory battery capacity-trend RUL research.
- `kit/`: KIT OBD-II next-window anomaly/novelty research.

Both archived tracks lack verified fault labels suitable for claiming diagnostic
accuracy. Deployment compatibility copies under `ml/hf_deployment/` are kept
separately because the existing experimental API still imports those artifacts.
