"""Entry point for the audited, dataset-specific Nissan Leaf preparation."""

from __future__ import annotations

from pathlib import Path

from .nissan_leaf_preparation.pipeline import prepare

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_NISSAN_LEAF_CONFIG = (
    ROOT / "ml/notebooks/nissan_leaf_2018/config/preparation.json"
)


def preprocess_nissan_leaf(
    config_path: str | Path = DEFAULT_NISSAN_LEAF_CONFIG,
) -> dict:
    """Run audited raw-data preparation and return its validated run manifest."""
    return prepare(Path(config_path))
