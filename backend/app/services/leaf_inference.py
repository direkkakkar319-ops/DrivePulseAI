"""Server-only Nissan HTTP adapter. Ordered batches, no fabricated fallbacks."""

import asyncio
import json
import math
from itertools import pairwise

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas.leaf_analysis import (
    FEATURES,
    AnomalyResponse,
    HealthResponse,
    RULResponse,
)
from app.services.ml_errors import MLServiceError


class LeafInferenceService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client

    async def call(self, path: str, payload: dict) -> dict:
        key = self.settings.ml_inference_api_key
        credential = key.get_secret_value() if key else ""
        if (
            not self.settings.ml_service_url
            or len(credential.encode()) < 32
            or credential.strip() != credential
        ):
            raise MLServiceError("Analysis service is not configured", 503)
        try:
            async with asyncio.timeout(self.settings.ml_request_timeout_seconds):
                async with self.client.stream(
                    "POST",
                    self.settings.ml_service_url + path,
                    json={"schema_version": 1, **payload},
                    headers={"X-ML-API-Key": credential},
                    timeout=httpx.Timeout(
                        self.settings.ml_request_timeout_seconds, connect=5
                    ),
                ) as response:
                    if response.status_code != 200:
                        raise MLServiceError(
                            "Analysis service unavailable",
                            503 if response.status_code in (401, 403, 503) else 502,
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 2 * 1024 * 1024:
                            raise MLServiceError(
                                "Invalid analysis service response", 502
                            )
            result = json.loads(body)

            def finite(value):
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError
                if isinstance(value, dict):
                    for child in value.values():
                        finite(child)
                elif isinstance(value, list):
                    for child in value:
                        finite(child)

            finite(result)
            if not isinstance(result, dict) or result.get("schema_version") != 1:
                raise ValueError
            return result
        except (TimeoutError, httpx.TimeoutException):
            raise MLServiceError("Analysis service timed out", 504) from None
        except httpx.RequestError:
            raise MLServiceError("Analysis service unavailable", 503) from None
        except (ValueError, TypeError):
            raise MLServiceError("Invalid analysis service response", 502) from None

    async def anomaly(self, observations: list[dict]) -> AnomalyResponse:
        size = self.settings.leaf_ml_batch_size
        if not observations or not 1 <= size <= 256:
            raise MLServiceError("Invalid analysis input", 422)
        # Snapshot/validate the entire input before the first upstream request.
        for row in observations:
            if tuple(row) != FEATURES or not all(
                type(v) in (int, float) and math.isfinite(v) for v in row.values()
            ):
                raise MLServiceError("Invalid analysis input", 422)
            if (
                not 0 < row["HV_Bat_Voltage"] <= 500
                or not 0 <= row["SOC"] <= 100
                or any(abs(v) > 3.4028234663852886e38 for v in row.values())
            ):
                raise MLServiceError("Invalid analysis input", 422)
        combined = None
        try:
            for start in range(0, len(observations), size):
                rows = observations[start : start + size]
                response = AnomalyResponse.model_validate(
                    await self.call(
                        "/v1/score/nissan-leaf-anomaly", {"observations": rows}
                    )
                )
                if len(response.results) != len(rows):
                    raise ValueError
                if combined and (
                    response.threshold != combined.threshold
                    or response.model_version != combined.model_version
                ):
                    raise ValueError
                for row, prediction in zip(rows, response.results, strict=True):
                    if prediction.is_unusual != (
                        prediction.anomaly_score < response.threshold
                    ):
                        raise ValueError
                    if prediction.is_unusual != (prediction.explanation is not None):
                        raise ValueError
                    if prediction.explanation:
                        contributions = prediction.explanation.contributions
                        if len({v.feature for v in contributions}) != 3:
                            raise ValueError
                        for rank, c in enumerate(contributions, 1):
                            if (
                                c.rank != rank
                                or c.feature not in FEATURES
                                or c.measured_value != row[c.feature]
                            ):
                                raise ValueError
                            if c.direction != (
                                "toward_anomaly"
                                if c.shap_value < 0
                                else "toward_typical"
                            ):
                                raise ValueError
                        if any(
                            abs(a.shap_value) < abs(b.shap_value)
                            for a, b in pairwise(contributions)
                        ):
                            raise ValueError
                if combined is None:
                    combined = response
                else:
                    combined.results.extend(response.results)
            return combined
        except (ValidationError, ValueError, TypeError, KeyError):
            raise MLServiceError("Invalid analysis service response", 502) from None

    async def health(self, soh: float) -> dict:
        result = await self.call("/v1/score/nissan-leaf-health", {"SOH": soh})
        try:
            validated = HealthResponse.model_validate(result)
            if validated.soh_pct != soh:
                raise ValueError
            return validated.model_dump()
        except (ValidationError, ValueError):
            raise MLServiceError("Invalid analysis service response", 502) from None

    async def rul(self, history: list[dict]) -> dict:
        result = await self.call(
            "/v1/estimate/nissan-leaf-rul", {"observations": history}
        )
        try:
            validated = RULResponse.model_validate(result)
            if validated.status in ("ok", "threshold_reached"):
                if validated.rul_km is None:
                    raise ValueError
            elif validated.rul_km is not None:
                raise ValueError
            if validated.status != "no_valid_history" and any(
                getattr(validated, name) is None
                for name in (
                    "current_soh_pct",
                    "current_odometer_km",
                    "daily_observations_used",
                    "history_span_days",
                    "eol_threshold_soh_pct",
                )
            ):
                raise ValueError
            return validated.model_dump(exclude_unset=True)
        except (ValidationError, ValueError):
            raise MLServiceError("Invalid analysis service response", 502) from None
