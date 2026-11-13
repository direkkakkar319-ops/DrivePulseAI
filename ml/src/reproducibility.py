"""Shared reproducibility helpers for DrivePulseAI ML experiments."""

from __future__ import annotations

import os
import random

import numpy as np

GLOBAL_SEED = 42


def set_global_seed(seed: int = GLOBAL_SEED) -> int:
    """Seed Python, NumPy, and supported optional backends.

    The function avoids importing optional heavy frameworks unless they are
    already installed. It returns the seed so callers can record it in a
    manifest without duplicating configuration.
    """

    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)

    try:
        import torch
    except (ImportError, OSError):
        pass
    else:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    return seed
