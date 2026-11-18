"""Async KIT adapter: validate all pairs, score sequentially, fail atomically.

No Firebase token, database session, model artifact or raw CSV is sent upstream.
Future routes must separately enforce the existing authenticated account guard.
"""

import asyncio
from collections.abc import Sequence
from typing import TypeVar

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas.inference import (
    KitBatchRequest,
    KitBatchResponse,
    KitInferenceResult,
    KitPairPayload,
)
from app.services.kit_samples import (
    WINDOW_SECONDS,
    KitWindowPair,
    SampleDataError,
    validate_window,
)

T = TypeVar("T")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class MLServiceError(Exception):
    """Safe service failure; future routes may explicitly map status_code to HTTP."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def bounded_batches(items: Sequence[T], size: int) -> tuple[tuple[T, ...], ...]:
    if type(size) is not int or not 1 <= size <= 256:
        raise MLServiceError("Invalid ML batch configuration", 503)
    return tuple(
        tuple(items[start : start + size]) for start in range(0, len(items), size)
    )


def prepare_pairs(
    pairs: Sequence[KitWindowPair], pair_ids: Sequence[str] | None = None
) -> list[KitPairPayload]:
    """Validate/snapshot the entire collection before any HTTP request is made."""
    if not pairs:
        raise MLServiceError("At least one KIT window pair is required", 422)
    ids = (
        list(pair_ids)
        if pair_ids is not None
        else [f"pair-{i:06d}" for i in range(len(pairs))]
    )
    if len(ids) != len(pairs):
        raise MLServiceError("KIT pair IDs must match the input collection", 422)
    prepared = []
    try:
        for pair, pair_id in zip(pairs, ids, strict=True):
            validate_window(pair.current)
            validate_window(pair.following)
            a, b = pair.current, pair.following
            if (a.recording_id, a.recording_date, a.segment_id, a.split) != (
                b.recording_id,
                b.recording_date,
                b.segment_id,
                b.split,
            ) or b.start_seconds - a.start_seconds != WINDOW_SECONDS:
                raise ValueError
            single = pair.inference_request()
            prepared.append(
                KitPairPayload(
                    pair_id=pair_id,
                    current_window_features=single["current_window_features"],
                    next_window_medians=single["next_window_medians"],
                )
            )
        if len(set(ids)) != len(ids):
            raise ValueError
    except (
        SampleDataError,
        ValidationError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
    ):
        raise MLServiceError("Invalid KIT window pairs or pair IDs", 422) from None
    return prepared


class KITInferenceService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self._settings = settings
        self._client = client

    async def score_pairs(
        self, pairs: Sequence[KitWindowPair], *, pair_ids: Sequence[str] | None = None
    ) -> KitInferenceResult:
        prepared = prepare_pairs(pairs, pair_ids)
        settings = self._settings
        key = settings.ml_inference_api_key
        credential = key.get_secret_value() if key is not None else ""
        if (
            not settings.ml_service_url
            or len(credential.encode("utf-8")) < 32
            or credential.strip() != credential
            or not credential.isascii()
            or not credential.isprintable()
        ):
            raise MLServiceError("ML service connection is not configured", 503)
        endpoint = f"{settings.ml_service_url}/v1/score/kit-window-pairs"
        accumulated = []
        metadata = None
        for batch in bounded_batches(prepared, settings.kit_ml_batch_size):
            payload = KitBatchRequest(pairs=list(batch))
            response = await self._score_batch(endpoint, credential, payload)
            expected_ids = [pair.pair_id for pair in batch]
            if [item.pair_id for item in response.results] != expected_ids:
                raise MLServiceError(
                    "ML service returned mismatched prediction IDs", 502
                )
            current_metadata = response.model_dump(exclude={"results"})
            if metadata is not None and metadata != current_metadata:
                raise MLServiceError(
                    "ML service changed model metadata during analysis", 502
                )
            metadata = current_metadata
            accumulated.extend(response.results)
        return KitInferenceResult(**metadata, results=accumulated)

    async def _score_batch(
        self, endpoint: str, credential: str, payload: KitBatchRequest
    ) -> KitBatchResponse:
        seconds = self._settings.ml_request_timeout_seconds
        timeout = httpx.Timeout(seconds, connect=min(5, seconds), pool=min(5, seconds))
        try:
            async with asyncio.timeout(seconds):
                async with self._client.stream(
                    "POST",
                    endpoint,
                    headers={"X-ML-API-Key": credential, "Accept": "application/json"},
                    json=payload.model_dump(mode="json"),
                    timeout=timeout,
                    follow_redirects=False,
                ) as response:
                    if response.status_code == 401:
                        raise MLServiceError("ML service authentication failed", 503)
                    if response.status_code == 503:
                        raise MLServiceError("ML service is unavailable", 503)
                    if response.status_code != 200:
                        raise MLServiceError(
                            "ML service returned an unexpected status", 502
                        )
                    content = bytearray()
                    async for part in response.aiter_bytes():
                        content.extend(part)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise MLServiceError(
                                "ML service returned an invalid response", 502
                            )
            return KitBatchResponse.model_validate_json(bytes(content))
        except MLServiceError:
            raise
        except (httpx.TimeoutException, TimeoutError):
            raise MLServiceError("ML service request timed out", 504) from None
        except httpx.RequestError:
            raise MLServiceError("Could not connect to ML service", 503) from None
        except ValidationError:
            raise MLServiceError(
                "ML service returned an invalid response", 502
            ) from None
