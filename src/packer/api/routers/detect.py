from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.schemas.requests import DetectRequest
from packer.api.schemas.responses import JobRecord

router = APIRouter(tags=["detect"])


@router.post("/detect", status_code=202, response_model=JobRecord)
def submit_detect(
    req: DetectRequest,
    svc: JobService = Depends(deps.get_job_service),
    broker: Any = Depends(deps.get_broker),
) -> JobRecord:
    job = svc.create(type="detect", input_ref=req.model_ref, input_hash=req.model_ref)
    broker.send_task("detect.run", args=[job.id, {"model_ref": req.model_ref}], queue="default")
    return job
