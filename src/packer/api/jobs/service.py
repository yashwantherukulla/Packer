from __future__ import annotations

import uuid

from packer.api.repos import JobRepository
from packer.api.schemas.responses import JobRecord


class JobService:
    """Create/query/transition jobs. No engine logic — pure orchestration (ARCHITECTURE §3.2)."""

    def __init__(self, repo: JobRepository, *, dedup: bool = False) -> None:
        self._repo = repo
        self._dedup = dedup

    def create(
        self, *, type: str, input_ref: str | None = None, input_hash: str | None = None
    ) -> JobRecord:
        if self._dedup and input_hash:
            existing = self._repo.find_by_hash(input_hash)
            if existing is not None and existing.status == "succeeded":
                return JobRecord.model_validate(existing, from_attributes=True)
        job_id = uuid.uuid4().hex
        row = self._repo.create(
            id=job_id,
            type=type,
            correlation_id=job_id,
            input_ref=input_ref,
            input_hash=input_hash,
        )
        return JobRecord.model_validate(row, from_attributes=True)

    def get(self, job_id: str) -> JobRecord | None:
        row = self._repo.get(job_id)
        return JobRecord.model_validate(row, from_attributes=True) if row else None

    def list(self, *, status: str | None = None, type: str | None = None) -> list[JobRecord]:
        return [
            JobRecord.model_validate(r, from_attributes=True)
            for r in self._repo.list(status=status, type=type)
        ]
