from __future__ import annotations

import redis.asyncio as aioredis


class ProgressHub:
    """Fan-out hub for job progress events (fleshed out in Task 14).

    Holds the async Redis client + channel prefix; the WebSocket relay that
    subscribes to ``progress:{job_id}`` and fans events out to connected
    clients lands in Task 14 (SYSTEM-DESIGN §3.6).
    """

    def __init__(self, redis: aioredis.Redis, *, prefix: str = "progress:") -> None:
        self._redis = redis
        self._prefix = prefix
