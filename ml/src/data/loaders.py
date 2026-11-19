"""Nissan Leaf dataset loading helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_NISSAN_LEAF_PROCESSED = (
    ROOT
    / "data/automotive_prognostics/nissan_leaf_2018/v1/processed/Dataset_Preprocessed.csv"
)


def iter_nissan_leaf_processed(
    path: str | Path = DEFAULT_NISSAN_LEAF_PROCESSED,
    *,
    columns: Sequence[str] | None = None,
    chunksize: int = 250_000,
) -> Iterator[pd.DataFrame]:
    """Yield chunks from the prepared Leaf CSV without loading the full file.

    The default prepared file is hundreds of megabytes. Pass `columns` to read
    only the fields needed by a particular model and keep memory bounded.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Nissan Leaf CSV not found: {source}")
    if chunksize <= 0:
        raise ValueError("chunksize must be positive")

    available = pd.read_csv(source, nrows=0).columns.tolist()
    if len(available) != len(set(available)):
        raise ValueError("Nissan Leaf CSV contains duplicate column names")
    if columns is not None:
        requested = list(columns)
        if not requested or len(requested) != len(set(requested)):
            raise ValueError("columns must be a nonempty sequence of unique names")
        missing = sorted(set(requested) - set(available))
        if missing:
            raise ValueError(f"Nissan Leaf CSV is missing columns: {missing}")
    else:
        requested = None

    yield from pd.read_csv(source, usecols=requested, chunksize=chunksize)


def load_nissan_leaf_processed(
    path: str | Path = DEFAULT_NISSAN_LEAF_PROCESSED,
    *,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load the prepared Leaf CSV into memory; prefer the chunk iterator for full data."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Nissan Leaf CSV not found: {source}")
    available = pd.read_csv(source, nrows=0).columns.tolist()
    if len(available) != len(set(available)):
        raise ValueError("Nissan Leaf CSV contains duplicate column names")
    requested = list(columns) if columns is not None else None
    if requested is not None:
        missing = sorted(set(requested) - set(available))
        if not requested or len(requested) != len(set(requested)):
            raise ValueError("columns must be a nonempty sequence of unique names")
        if missing:
            raise ValueError(f"Nissan Leaf CSV is missing columns: {missing}")
    return pd.read_csv(source, usecols=requested)
