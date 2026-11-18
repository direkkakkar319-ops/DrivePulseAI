"""Authenticated recorded KIT examples; no database writes or vehicle association."""

import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from starlette.concurrency import run_in_threadpool

from app.api.deps import Identity, get_inference_service, require_identity
from app.schemas.analysis import SampleAnalysis, SampleCatalog, UploadedAnalysis
from app.services import analysis_service
from app.services.inference_service import KITInferenceService, MLServiceError
from app.services.kit_samples import SampleDataError, UnknownSampleError
from app.services.kit_upload import UploadError, prepare_csv, receive_upload

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
VerifiedIdentity = Annotated[Identity, Depends(require_identity)]
Inference = Annotated[KITInferenceService, Depends(get_inference_service)]


def safe_error(error: Exception) -> HTTPException:
    status, detail = 500, "Sample analysis failed"
    if isinstance(error, UnknownSampleError):
        status, detail = 404, "Sample not found"
    elif isinstance(error, SampleDataError):
        status, detail = 503, "Sample data unavailable"
    elif isinstance(error, MLServiceError):
        status = error.status_code if error.status_code in {422, 502, 503, 504} else 502
        detail = {
            422: "Analysis input unavailable",
            502: "Invalid analysis service response",
            503: "Analysis service unavailable",
            504: "Analysis service timed out",
        }[status]
    return HTTPException(status, detail, headers={"Cache-Control": "no-store"})


@router.get("/samples", response_model=SampleCatalog)
def list_samples(identity: VerifiedIdentity, response: Response) -> SampleCatalog:
    try:
        catalog = SampleCatalog(samples=analysis_service.available_samples())
    except Exception as error:  # noqa: BLE001 -- API boundary masks internal details.
        raise safe_error(error) from None
    response.headers["Cache-Control"] = "no-store"
    return catalog


@router.post("/samples/{sample_id}/analyze", response_model=SampleAnalysis)
async def analyze(
    sample_id: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")],
    identity: VerifiedIdentity,
    service: Inference,
    response: Response,
) -> SampleAnalysis:
    try:
        sample, info = await run_in_threadpool(
            analysis_service.load_analysis_sample, sample_id
        )
        result = await analysis_service.analyze_sample(sample, info, service)
    except Exception as error:  # noqa: BLE001 -- API boundary masks internal details.
        raise safe_error(error) from None
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/upload",
    response_model=UploadedAnalysis,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file", "recording_date"],
                        "additionalProperties": False,
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            "recording_date": {"type": "string", "format": "date"},
                        },
                    }
                }
            },
        },
    },
)
async def upload_analysis(
    identity: VerifiedIdentity,
    service: Inference,
    request: Request,
    response: Response,
) -> UploadedAnalysis:
    settings = request.app.state.settings
    seconds = settings.kit_upload_analysis_timeout_seconds
    deadline = time.monotonic() + seconds
    slots = request.app.state.kit_upload_slots
    acquired = False
    data = None
    try:
        async with asyncio.timeout(seconds):
            try:
                await asyncio.wait_for(slots.acquire(), timeout=min(1, seconds))
                acquired = True
            except TimeoutError:
                raise UploadError("Upload analysis capacity is busy", 429) from None
            data, day = await receive_upload(request, settings)
            recording = await run_in_threadpool(
                prepare_csv, data, day, settings, deadline
            )
            data = None  # Release raw bytes before awaiting the remote model.
            result = await analysis_service.analyze_upload(recording, service)
    except UploadError as error:
        raise HTTPException(
            error.status_code, str(error), headers={"Cache-Control": "no-store"}
        ) from None
    except TimeoutError:
        raise HTTPException(
            504, "CSV analysis timed out", headers={"Cache-Control": "no-store"}
        ) from None
    except MLServiceError as error:
        raise safe_error(error) from None
    except Exception:  # noqa: BLE001 -- Upload boundary must not expose internal data.
        raise HTTPException(
            500, "CSV analysis failed", headers={"Cache-Control": "no-store"}
        ) from None
    finally:
        data = None
        if acquired:
            slots.release()
    response.headers["Cache-Control"] = "no-store"
    return result
