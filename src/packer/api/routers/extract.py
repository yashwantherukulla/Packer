from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.schemas.requests import ExtractRequest
from packer.api.schemas.responses import JobRecord

router = APIRouter(tags=["extract"])


@router.post("/extract", status_code=202, response_model=JobRecord)
def submit_extract(
    req: ExtractRequest,
    svc: JobService = Depends(deps.get_job_service),
    broker: Any = Depends(deps.get_broker),
) -> JobRecord:
    job = svc.create(type="extract", input_ref=req.model_ref, input_hash=req.model_ref)
    broker.send_task(
        "extract.run",
        args=[job.id, {"target": req.model_ref, "artifact_id": req.artifact_id}],
        queue="default",
    )
    return job
