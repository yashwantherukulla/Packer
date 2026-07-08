from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packer.api import deps
from packer.api.schemas.responses import ReportResponse

router = APIRouter(tags=["reports"])


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, reports: Any = Depends(deps.get_report_repo)) -> ReportResponse:
    row = reports.get(report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")
    # /reports/{id} serves detect and scan uniformly via the shared Report (spec §5).
    return ReportResponse(id=row.id, job_id=row.job_id, kind=row.kind, report=row.report_json)
