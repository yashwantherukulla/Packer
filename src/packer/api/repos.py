from __future__ import annotations

from typing import Protocol

from packer.api.db.models import Artifact, Job, ModelRow, ReportRow


class JobRepository(Protocol):
    def create(
        self,
        *,
        id: str,
        type: str,
        correlation_id: str,
        input_ref: str | None = None,
        input_hash: str | None = None,
    ) -> Job: ...
    def get(self, job_id: str) -> Job | None: ...
    def list(self, *, status: str | None = None, type: str | None = None) -> list[Job]: ...
    def mark_running(self, job_id: str) -> None: ...
    def update_progress(self, job_id: str, *, pct: float, step: str) -> None: ...
    def mark_succeeded(self, job_id: str, *, result_ref: str) -> None: ...
    def mark_failed(self, job_id: str, *, code: str, msg: str) -> None: ...
    def find_by_hash(self, input_hash: str) -> Job | None: ...


class ReportRepository(Protocol):
    def insert(
        self, *, id: str, job_id: str, kind: str, report: dict[str, object]
    ) -> ReportRow: ...
    def get(self, report_id: str) -> ReportRow | None: ...


class ArtifactRepository(Protocol):
    def insert(
        self,
        *,
        id: str,
        job_id: str,
        pak_path: str,
        manifest: dict[str, object],
        metrics: dict[str, object],
    ) -> Artifact: ...
    def get(self, artifact_id: str) -> Artifact | None: ...


class ModelRepository(Protocol):
    def insert(
        self,
        *,
        id: str,
        source: str,
        format: str,
        sha256: str,
        path: str,
        meta: dict[str, object],
    ) -> ModelRow: ...
    def get(self, model_id: str) -> ModelRow | None: ...
    def list(self) -> list[ModelRow]: ...
