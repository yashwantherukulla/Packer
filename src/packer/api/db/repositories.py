from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packer.api.db.models import Artifact, Job, ModelRow, ReportRow


class SqlJobRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(
        self,
        *,
        id: str,
        type: str,
        correlation_id: str,
        input_ref: str | None = None,
        input_hash: str | None = None,
    ) -> Job:
        job = Job(
            id=id,
            type=type,
            status="queued",
            correlation_id=correlation_id,
            input_ref=input_ref,
            input_hash=input_hash,
        )
        self._s.add(job)
        self._s.commit()
        self._s.refresh(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._s.get(Job, job_id)

    def list(self, *, status: str | None = None, type: str | None = None) -> list[Job]:
        stmt = select(Job)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if type is not None:
            stmt = stmt.where(Job.type == type)
        return list(self._s.scalars(stmt.order_by(Job.created_at.desc())))

    def mark_running(self, job_id: str) -> None:
        self._set(job_id, status="running", started_at=datetime.now(timezone.utc))

    def update_progress(self, job_id: str, *, pct: float, step: str) -> None:
        self._set(job_id, progress_pct=pct, progress_step=step)

    def mark_succeeded(self, job_id: str, *, result_ref: str) -> None:
        self._set(
            job_id,
            status="succeeded",
            result_ref=result_ref,
            progress_pct=1.0,
            finished_at=datetime.now(timezone.utc),
        )

    def mark_failed(self, job_id: str, *, code: str, msg: str) -> None:
        self._set(
            job_id,
            status="failed",
            error_code=code,
            error=msg,
            finished_at=datetime.now(timezone.utc),
        )

    def find_by_hash(self, input_hash: str) -> Job | None:
        return self._s.scalar(select(Job).where(Job.input_hash == input_hash))

    def _set(self, job_id: str, **fields: object) -> None:
        job = self._s.get(Job, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        self._s.commit()


class SqlReportRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def insert(self, *, id: str, job_id: str, kind: str, report: dict[str, object]) -> ReportRow:
        row = ReportRow(id=id, job_id=job_id, kind=kind, report_json=report)
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return row

    def get(self, report_id: str) -> ReportRow | None:
        return self._s.get(ReportRow, report_id)


class SqlArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def insert(
        self,
        *,
        id: str,
        job_id: str,
        pak_path: str,
        manifest: dict[str, object],
        metrics: dict[str, object],
    ) -> Artifact:
        row = Artifact(
            id=id,
            job_id=job_id,
            pak_path=pak_path,
            manifest_json=manifest,
            metrics_json=metrics,
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return row

    def get(self, artifact_id: str) -> Artifact | None:
        return self._s.get(Artifact, artifact_id)


class SqlModelRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def insert(
        self,
        *,
        id: str,
        source: str,
        format: str,
        sha256: str,
        path: str,
        meta: dict[str, object],
    ) -> ModelRow:
        row = ModelRow(
            id=id, source=source, format=format, sha256=sha256, path=path, meta_json=meta
        )
        self._s.add(row)
        self._s.commit()
        self._s.refresh(row)
        return row

    def get(self, model_id: str) -> ModelRow | None:
        return self._s.get(ModelRow, model_id)

    def list(self) -> list[ModelRow]:
        return list(self._s.scalars(select(ModelRow).order_by(ModelRow.created_at.desc())))
