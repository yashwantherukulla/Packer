from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.schemas.responses import JobList, JobRecord

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=JobList)
def list_jobs(
    status: str | None = None,
    type: str | None = None,
    svc: JobService = Depends(deps.get_job_service),
) -> JobList:
    return JobList(jobs=svc.list(status=status, type=type))


@router.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str, svc: JobService = Depends(deps.get_job_service)) -> JobRecord:
    job = svc.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
