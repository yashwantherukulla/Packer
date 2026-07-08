from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Resp(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobRecord(_Resp):
    id: str
    type: str
    status: str
    correlation_id: str
    input_ref: str | None = None
    result_ref: str | None = None
    error: str | None = None
    error_code: str | None = None
    progress_pct: float = 0.0
    progress_step: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None


class JobList(BaseModel):
    jobs: list[JobRecord]


class ModelRecord(_Resp):
    id: str
    source: str
    format: str
    sha256: str
    created_at: datetime | None = None


class ArtifactResponse(_Resp):
    id: str
    job_id: str
    pak_path: str
    manifest_json: dict[str, object]
    metrics_json: dict[str, object]


class ReportResponse(BaseModel):
    # Wraps the shared engine Report (packer.engine.report.model.Report) so /reports/{id}
    # serves detect and scan uniformly (spec §5).
    id: str
    job_id: str
    kind: str
    report: dict[str, object]  # the engine Report serialized (report.model_dump(mode="json"))
