from __future__ import annotations

import json
from typing import Any


class RedisProgress:
    """ProgressCallback impl: publishes semantic progress to Redis (SYSTEM-DESIGN §3.6).

    Signature matches packer.engine.common.progress.ProgressCallback exactly, so the
    engine accepts it without importing redis.
    """

    def __init__(self, job_id: str, client: Any, *, prefix: str = "progress:") -> None:
        self._job_id = job_id
        self._client = client
        self._channel = f"{prefix}{job_id}"

    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None:
        payload = json.dumps({"job_id": self._job_id, "step": step, "pct": pct, "detail": detail})
        self._client.publish(self._channel, payload)
