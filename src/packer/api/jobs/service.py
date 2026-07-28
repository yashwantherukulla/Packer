from __future__ import annotations

import hashlib
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
        normalized_hash = _normalize_input_hash(input_hash)
        if self._dedup and normalized_hash:
            existing = self._repo.find_by_hash(normalized_hash)
            if existing is not None and existing.status == "succeeded":
                return JobRecord.model_validate(existing, from_attributes=True)
        job_id = uuid.uuid4().hex
        row = self._repo.create(
            id=job_id,
            type=type,
            correlation_id=job_id,
            input_ref=input_ref,
            input_hash=normalized_hash,
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


def _normalize_input_hash(input_hash: str | None) -> str | None:
    if input_hash is None:
        return None
    if len(input_hash) == 64 and all(ch in "0123456789abcdef" for ch in input_hash.lower()):
        return input_hash.lower()
    return hashlib.sha256(input_hash.encode("utf-8")).hexdigest()
