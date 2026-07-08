import json

from packer.engine.common.progress import ProgressCallback
from packer.workers.progress import RedisProgress


class _SyncFakeRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    def publish(self, channel, payload):
        self.published.append((channel, payload))


def test_publishes_progress_event_json():
    fake = _SyncFakeRedis()
    cb: ProgressCallback = RedisProgress("job-1", fake)
    cb(step="train", pct=0.4, detail="epoch 80/200")
    channel, payload = fake.published[0]
    assert channel == "progress:job-1"
    data = json.loads(payload)
    assert data == {"job_id": "job-1", "step": "train", "pct": 0.4, "detail": "epoch 80/200"}
