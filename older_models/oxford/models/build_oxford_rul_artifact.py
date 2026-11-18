"""Serialize the configured Oxford trend estimator for the HF model repo.

This is an estimator configuration, not a model fitted to pooled Oxford rows.
The trend is fit to the past capacity history supplied with each request.
"""

from __future__ import annotations

from pathlib import Path

import joblib

from ml.src.models.rul_regressor import TheilSenCapacityTrendRUL

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "model_repository" / "oxford_rul_theilsen.joblib"


def main() -> None:
    """Write the default 1,000-cycle Theil-Sen estimator configuration."""
    estimator = TheilSenCapacityTrendRUL(
        lookback_cycles=1000,
        min_observations=4,
        random_state=42,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, OUTPUT)
    print(f"Wrote Oxford estimator configuration: {OUTPUT}")


if __name__ == "__main__":
    main()
