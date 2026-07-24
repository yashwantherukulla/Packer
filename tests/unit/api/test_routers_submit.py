from fastapi.testclient import TestClient
from tests.unit.fakes import FakeBroker, InMemoryJobRepository, StubStore

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.main import create_app


def _client_with_fakes(broker: FakeBroker):
    app = create_app()
    svc = JobService(InMemoryJobRepository())
    app.dependency_overrides[deps.get_job_service] = lambda: svc
    app.dependency_overrides[deps.get_store] = lambda: StubStore()
    app.dependency_overrides[deps.get_broker] = lambda: broker  # tasks enqueue via injected broker
    return TestClient(app), svc


def test_post_detect_returns_202_queued_and_enqueues_default_queue():
    broker = FakeBroker()
    client, _ = _client_with_fakes(broker)
    resp = client.post("/detect", json={"model_ref": "Qwen/Qwen2.5-0.5B"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued" and body["type"] == "detect"
    assert broker.sent[0].name == "detect.run" and broker.sent[0].queue == "default"


def test_post_pack_uploads_and_routes_to_gpu():
    broker = FakeBroker()
    client, _ = _client_with_fakes(broker)
    resp = client.post("/pack", files={"file": ("repo.zip", b"PK\x03\x04zip", "application/zip")})
    assert resp.status_code == 202
    assert broker.sent[0].name == "pack.run" and broker.sent[0].queue == "gpu"


def test_scan_requires_exactly_one_target():
    client, _ = _client_with_fakes(FakeBroker())
    assert client.post("/scan", json={}).status_code == 422


def test_post_scan_with_extraction_id_enqueues_default_queue():
    broker = FakeBroker()
    client, _ = _client_with_fakes(broker)
    resp = client.post("/scan", json={"extraction_id": "extraction:e1"})
    assert resp.status_code == 202
    assert broker.sent[0].name == "scan.run"
    assert broker.sent[0].queue == "default"
    assert broker.sent[0].args[1]["target"] == "extraction:e1"
