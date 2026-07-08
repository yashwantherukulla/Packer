from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi import APIRouter, Depends, UploadFile

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.schemas.responses import JobRecord

router = APIRouter(tags=["pack"])


@router.post("/pack", status_code=202, response_model=JobRecord)
async def submit_pack(
    file: UploadFile,
    svc: JobService = Depends(deps.get_job_service),
    store: Any = Depends(deps.get_store),
    broker: Any = Depends(deps.get_broker),
) -> JobRecord:
    data = await file.read()
    ref = store.put_blob(f"uploads/{uuid.uuid4().hex}.zip", data)
    job = svc.create(type="pack", input_ref=ref, input_hash=hashlib.sha256(data).hexdigest())
    broker.send_task("pack.run", args=[job.id, {"root": ref}], queue="gpu")  # validate->enqueue
    return job
