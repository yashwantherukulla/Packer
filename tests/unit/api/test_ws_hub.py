import asyncio
import json

import pytest
from tests.unit.fakes import FakeRedis

from packer.api.ws.hub import ProgressHub


@pytest.mark.asyncio
async def test_relay_forwards_redis_messages_to_send():
    redis = FakeRedis()
    hub = ProgressHub(redis, prefix="progress:")
    received: list[dict] = []

    async def send(text: str) -> None:
        received.append(json.loads(text))

    # queue two events on the channel, then relay drains + forwards them
    await redis.publish(
        "progress:j1", json.dumps({"job_id": "j1", "step": "train", "pct": 0.5, "detail": None})
    )
    await redis.publish(
        "progress:j1", json.dumps({"job_id": "j1", "step": "done", "pct": 1.0, "detail": None})
    )
    await asyncio.wait_for(hub.relay("j1", send, max_messages=2), timeout=1.0)

    assert [e["step"] for e in received] == ["train", "done"]
