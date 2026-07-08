import json

import pytest

pytestmark = pytest.mark.integration


def test_ws_relays_published_progress_end_to_end(client, redis_url):
    """Prove the Redis progress:{id} -> ProgressHub -> WebSocket relay end-to-end
    against a real Redis (spec §6)."""
    import redis

    job_id = client.post("/detect", json={"model_ref": "no-such-model"}).json()["id"]
    publisher = redis.from_url(redis_url, decode_responses=True)

    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        reconcile = ws.receive_json()  # current job state pushed on connect
        assert reconcile["id"] == job_id
        publisher.publish(
            f"progress:{job_id}",
            json.dumps({"job_id": job_id, "step": "train", "pct": 0.5, "detail": None}),
        )
        event = json.loads(ws.receive_text())
        assert event["step"] == "train" and event["job_id"] == job_id
