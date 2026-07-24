import io
import tarfile
from pathlib import Path

from fastapi.testclient import TestClient
from tests.unit.fakes import (
    InMemoryArtifactRepository,
    InMemoryJobRepository,
    InMemoryReportRepository,
)

from packer.api import deps
from packer.api.jobs.service import JobService
from packer.api.main import create_app


def _client():
    app = create_app()
    jobs_repo = InMemoryJobRepository()
    reports = InMemoryReportRepository()
    jobs_repo.create(id="j1", type="detect", correlation_id="j1")
    reports.insert(
        id="r1", job_id="j1", kind="detect", report={"kind": "detect", "verdict": "UNLIKELY"}
    )
    app.dependency_overrides[deps.get_job_service] = lambda: JobService(jobs_repo)
    app.dependency_overrides[deps.get_report_repo] = lambda: reports
    app.dependency_overrides[deps.get_artifact_repo] = lambda: InMemoryArtifactRepository()
    return TestClient(app)


def _download_client(tmp_path: Path):
    app = create_app()
    artifacts = InMemoryArtifactRepository()
    artifact_path = tmp_path / "store" / "pak" / "a1"
    artifact_path.mkdir(parents=True, exist_ok=True)
    (artifact_path / "model.safetensors").write_bytes(b"pak-bytes")
    (artifact_path / "manifest.json").write_text("{}", encoding="utf-8")
    artifacts.insert(id="a1", job_id="j1", pak_path="a1", manifest={}, metrics={})

    class _Store:
        def pak_path(self, artifact_id: str) -> Path:
            return artifact_path

    app.dependency_overrides[deps.get_artifact_repo] = lambda: artifacts
    app.dependency_overrides[deps.get_store] = lambda: _Store()
    return TestClient(app)


def test_get_job_by_id():
    r = _client().get("/jobs/j1")
    assert r.status_code == 200 and r.json()["type"] == "detect"


def test_list_jobs_filtered_by_type():
    r = _client().get("/jobs", params={"type": "detect"})
    assert r.status_code == 200 and len(r.json()["jobs"]) == 1


def test_get_report_serves_shared_model():
    r = _client().get("/reports/r1")
    assert r.status_code == 200
    assert r.json()["kind"] == "detect" and r.json()["report"]["verdict"] == "UNLIKELY"


def test_missing_job_is_404():
    assert _client().get("/jobs/nope").status_code == 404


def test_get_artifact_download_streams_file(tmp_path: Path):
    client = _download_client(tmp_path)
    resp = client.get("/artifacts/a1", params={"download": "1"})
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment; filename=")
    assert "a1.pak" in resp.headers["content-disposition"]
    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r") as tar:
        names = tar.getnames()
    assert "a1/model.safetensors" in names
    assert "a1/manifest.json" in names
