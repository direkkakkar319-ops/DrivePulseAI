"""Firebase-protected Nissan analysis; no database persistence or Garage association."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import Identity, require_identity
from app.schemas.leaf_analysis import LeafAnalysis
from app.services import leaf_analysis

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
VerifiedIdentity = Annotated[Identity, Depends(require_identity)]


@router.get("/samples")
def samples(identity: VerifiedIdentity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return leaf_analysis.catalog()


async def execute(request, response, *, sample_id=None):
    settings = request.app.state.settings
    slots = request.app.state.leaf_upload_slots
    acquired = False
    try:
        async with asyncio.timeout(settings.leaf_analysis_timeout_seconds):
            try:
                await asyncio.wait_for(slots.acquire(), 1)
                acquired = True
            except TimeoutError:
                raise leaf_analysis.CSVError("Analysis capacity is busy", 429) from None
            data = (
                await run_in_threadpool(leaf_analysis.sample_bytes, sample_id)
                if sample_id
                else await leaf_analysis.receive_csv(request, settings)
            )
            readings, quality = await run_in_threadpool(
                leaf_analysis.parse_csv, data, settings
            )
            del data
            result = await leaf_analysis.analyze(
                readings,
                quality,
                request.app.state.leaf_inference,
                source_type="built_in_sample" if sample_id else "uploaded_csv",
                sample_id=sample_id,
            )
            response.headers["Cache-Control"] = "no-store"
            return result
    except leaf_analysis.CSVError as error:
        raise HTTPException(
            error.status_code, str(error), headers={"Cache-Control": "no-store"}
        ) from None
    except TimeoutError:
        raise HTTPException(
            504, "Analysis timed out", headers={"Cache-Control": "no-store"}
        ) from None
    except StarletteHTTPException as error:
        raise HTTPException(
            error.status_code,
            "Invalid multipart upload",
            headers={"Cache-Control": "no-store"},
        ) from None
    except Exception:  # noqa: BLE001 -- API boundary must not expose internal details.
        raise HTTPException(
            500, "Analysis processing failed", headers={"Cache-Control": "no-store"}
        ) from None
    finally:
        if acquired:
            slots.release()


@router.post("/samples/{sample_id}/analyze", response_model=LeafAnalysis)
async def analyze_sample(
    sample_id: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")],
    identity: VerifiedIdentity,
    request: Request,
    response: Response,
):
    return await execute(request, response, sample_id=sample_id)


@router.post(
    "/upload",
    response_model=LeafAnalysis,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "additionalProperties": False,
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload(identity: VerifiedIdentity, request: Request, response: Response):
    return await execute(request, response)
