from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Send = Callable[[str], Awaitable[None]]


class ProgressHub:
    """Bridges Redis progress channels to WebSocket clients (SYSTEM-DESIGN §3.6).

    Keeps no ML state — pure fan-out.
    """

    def __init__(self, redis: Any, *, prefix: str = "progress:") -> None:
        self._redis = redis
        self._prefix = prefix

    async def relay(self, job_id: str, send: Send, *, max_messages: int | None = None) -> None:
        channel = f"{self._prefix}{job_id}"
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        seen = 0
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                await send(message["data"])
                seen += 1
                if max_messages is not None and seen >= max_messages:
                    return
        finally:
            await pubsub.unsubscribe(channel)
