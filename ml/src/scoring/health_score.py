"""Transparent five-level Nissan Leaf battery health score from reported SOH."""

from __future__ import annotations

import math

HEALTH_SCORE_BANDS = (
    {"minimum_soh_pct": 95.0, "maximum_soh_pct": 100.0, "score": 5},
    {"minimum_soh_pct": 90.0, "maximum_soh_pct": 95.0, "score": 4},
    {"minimum_soh_pct": 85.0, "maximum_soh_pct": 90.0, "score": 3},
    {"minimum_soh_pct": 80.0, "maximum_soh_pct": 85.0, "score": 2},
    {"minimum_soh_pct": 0.0, "maximum_soh_pct": 80.0, "score": 1},
)


def battery_health_score(soh_pct: float) -> dict:
    """Map battery SOH (not SOC) to a 1–5 health score and band label."""
    soh = float(soh_pct)
    if not math.isfinite(soh) or not 0 <= soh <= 100:
        raise ValueError("soh_pct must be finite and within [0, 100]")
    score = 5 if soh >= 95 else 4 if soh >= 90 else 3 if soh >= 85 else 2 if soh >= 80 else 1
    labels = {
        5: "very_healthy",
        4: "healthy",
        3: "moderate_degradation",
        2: "degraded",
        1: "end_of_life_range",
    }
    return {
        "health_score": score,
        "score_scale": "1=lowest health, 5=highest health",
        "soh_pct": soh,
        "label": labels[score],
        "bands": HEALTH_SCORE_BANDS,
        "threshold_note": "80% SOH is a configurable project proxy, not a universal vehicle EOL rule.",
    }
