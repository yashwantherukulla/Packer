"""In-memory fakes injected by the API/worker unit suites.

These stand in for the SQLAlchemy repositories, the async Redis client, and the
Celery broker handle so unit tests need no live Postgres/Redis/Docker
(SYSTEM-DESIGN §5.7 "an interface so tests use in-memory fakes"). The repository
fakes construct real ORM instances so ``JobRecord.model_validate(row,
from_attributes=True)`` works downstream unchanged.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from packer.api.db.models import Artifact, Job, ModelRow, ReportRow


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Job] = {}

    def create(
        self,
        *,
        id: str,
        type: str,
        correlation_id: str,
        input_ref: str | None = None,
        input_hash: str | None = None,
    ) -> Job:
        self._rows[id] = Job(
            id=id,
            type=type,
            status="queued",
            correlation_id=correlation_id,
            input_ref=input_ref,
            input_hash=input_hash,
            progress_pct=0.0,
        )
        return self._rows[id]

    def get(self, job_id: str) -> Job | None:
        return self._rows.get(job_id)

    def list(self, *, status: str | None = None, type: str | None = None) -> list[Job]:
        return [
            j
            for j in self._rows.values()
            if (status is None or j.status == status) and (type is None or j.type == type)
        ]

    def mark_running(self, job_id: str) -> None:
        self._set(job_id, status="running")

    def update_progress(self, job_id: str, *, pct: float, step: str) -> None:
        self._set(job_id, progress_pct=pct, progress_step=step)

    def mark_succeeded(self, job_id: str, *, result_ref: str) -> None:
        self._set(job_id, status="succeeded", result_ref=result_ref, progress_pct=1.0)

    def mark_failed(self, job_id: str, *, code: str, msg: str) -> None:
        self._set(job_id, status="failed", error_code=code, error=msg)

    def find_by_hash(self, input_hash: str) -> Job | None:
        return next((j for j in self._rows.values() if j.input_hash == input_hash), None)

    def _set(self, job_id: str, **fields: object) -> None:
        j = self._rows.get(job_id)
        if j is None:
            return
        for k, v in fields.items():
            setattr(j, k, v)


class InMemoryReportRepository:
    def __init__(self) -> None:
        self._rows: dict[str, ReportRow] = {}

    def insert(self, *, id: str, job_id: str, kind: str, report: dict[str, object]) -> ReportRow:
        self._rows[id] = ReportRow(id=id, job_id=job_id, kind=kind, report_json=report)
        return self._rows[id]

    def get(self, report_id: str) -> ReportRow | None:
        return self._rows.get(report_id)


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Artifact] = {}

    def insert(
        self,
        *,
        id: str,
        job_id: str,
        pak_path: str,
        manifest: dict[str, object],
        metrics: dict[str, object],
    ) -> Artifact:
        self._rows[id] = Artifact(
            id=id, job_id=job_id, pak_path=pak_path, manifest_json=manifest, metrics_json=metrics
        )
        return self._rows[id]

    def get(self, artifact_id: str) -> Artifact | None:
        return self._rows.get(artifact_id)


class InMemoryModelRepository:
    def __init__(self) -> None:
        self._rows: dict[str, ModelRow] = {}

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
        self._rows[id] = ModelRow(
            id=id, source=source, format=format, sha256=sha256, path=path, meta_json=meta
        )
        return self._rows[id]

    def get(self, model_id: str) -> ModelRow | None:
        return self._rows.get(model_id)

    def list(self) -> list[ModelRow]:
        return list(self._rows.values())


class _FakePubSub:
    """Minimal async pubsub replaying the messages a FakeRedis has captured."""

    def __init__(self, channels: dict[str, list[str]]) -> None:
        self._channels = channels
        self._subscribed: list[str] = []

    async def subscribe(self, *channels: str) -> None:
        self._subscribed.extend(channels)

    async def unsubscribe(self, *channels: str) -> None:
        for ch in channels or tuple(self._subscribed):
            if ch in self._subscribed:
                self._subscribed.remove(ch)

    async def get_message(
        self, *, ignore_subscribe_messages: bool = True, timeout: float | None = None
    ) -> dict[str, object] | None:
        for ch in self._subscribed:
            queue = self._channels.get(ch)
            if queue:
                data = queue.pop(0)
                return {"type": "message", "channel": ch, "data": data}
        return None

    async def listen(self) -> AsyncIterator[dict[str, object]]:
        while True:
            msg = await self.get_message()
            if msg is None:
                break
            yield msg

    async def aclose(self) -> None:
        self._subscribed.clear()


class FakeRedis:
    """Captures publishes and replays them to pubsub subscribers (SYSTEM-DESIGN §3.6 fan-out)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self._queues: dict[str, list[str]] = {}

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))
        self._queues.setdefault(channel, []).append(payload)

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self._queues)

    async def aclose(self) -> None:
        return None


class SyncFakeRedis:
    """Synchronous redis stand-in for RedisProgress (worker side publishes sync)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))


class _StubMetrics:
    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        return {"lossless": True}


class _StubManifest:
    metrics = _StubMetrics()

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        return {"pak_version": "1.0"}


class _StubBundle:
    manifest = _StubManifest()


class StubStore:
    """Store stand-in: open_pak returns a stub bundle (pack-path persistence branch)
    and put_blob echoes the key back (upload path)."""

    def open_pak(self, artifact_id: str) -> _StubBundle:
        return _StubBundle()

    def put_blob(self, key: str, data: bytes) -> str:
        return key


class FakeEnginePorts:
    """EnginePorts stand-in wired with a StubStore (no live adapters)."""

    def __init__(self) -> None:
        self.store = StubStore()
        self.loader: object | None = None
        self.sandbox: object | None = None


class _FakeAsyncResult:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


class FakeBroker:
    """Celery-handle stand-in: records `send_task(name, args=...)` enqueues by name."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, list[object], dict[str, object]]] = []

    def send_task(
        self,
        name: str,
        args: list[object] | None = None,
        kwargs: dict[str, object] | None = None,
        **options: object,
    ) -> _FakeAsyncResult:
        self.sent.append((name, list(args or []), dict(kwargs or {})))
        return _FakeAsyncResult(uuid.uuid4().hex)
