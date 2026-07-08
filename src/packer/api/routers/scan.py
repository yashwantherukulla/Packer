from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.schemas.requests import ScanRequest
from packer.api.schemas.responses import JobRecord

router = APIRouter(tags=["scan"])


@router.post("/scan", status_code=202, response_model=JobRecord)
def submit_scan(
    req: ScanRequest,
    svc: JobService = Depends(deps.get_job_service),
    broker: Any = Depends(deps.get_broker),
) -> JobRecord:
    # ScanRequest's validator already enforced exactly one of extraction_id/model_ref
    target = req.extraction_id or req.model_ref
    job = svc.create(type="scan", input_ref=target, input_hash=target)
    broker.send_task("scan.run", args=[job.id, {"target": target}], queue="default")
    return job
