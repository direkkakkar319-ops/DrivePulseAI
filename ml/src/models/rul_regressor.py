"""Compatibility exports for archived Oxford RUL experiments."""

from older_models.oxford.models.rul_regressor import (
    ExponentialCapacityTrendRUL,
    TheilSenCapacityTrendRUL,
)

__all__ = ["ExponentialCapacityTrendRUL", "TheilSenCapacityTrendRUL"]
