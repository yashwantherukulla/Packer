import pytest
from tests.unit.fakes import (
    FakeEnginePorts,
    InMemoryArtifactRepository,
    InMemoryJobRepository,
    InMemoryReportRepository,
    SyncFakeRedis,
)

from packer.engine.common.errors import UnsafeModelError
from packer.workers.progress import RedisProgress
from packer.workers.runner import run_engine_job


def _deps():
    jobs = InMemoryJobRepository()
    jobs.create(id="j1", type="detect", correlation_id="j1")
    return {
        "jobs": jobs,
        "reports": InMemoryReportRepository(),
        "artifacts": InMemoryArtifactRepository(),
        "ports": FakeEnginePorts(),
        "redis_client": SyncFakeRedis(),
    }


def test_success_persists_report_and_marks_succeeded():
    from packer.engine.report.model import Report

    d = _deps()
    report = Report.model_construct(kind="detect", schema_version="1.0")  # minimal fixture
    run_engine_job("j1", lambda ports, pr: report, **d)
    assert d["jobs"].get("j1").status == "succeeded"
    assert d["jobs"].get("j1").result_ref.startswith("report:")


def test_packer_error_becomes_failed_job_not_raised():
    d = _deps()

    def call(ports, pr):
        raise UnsafeModelError("pickle")

    run_engine_job("j1", call, **d)  # must NOT raise
    row = d["jobs"].get("j1")
    assert row.status == "failed" and row.error_code == "unsafe_model"


def test_unknown_error_marks_failed_and_reraises():
    d = _deps()

    def call(ports, pr):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run_engine_job("j1", call, **d)
    assert d["jobs"].get("j1").status == "failed"
    assert d["jobs"].get("j1").error_code == "internal"


def test_progress_is_bound_and_published():
    d = _deps()

    def call(ports, pr):
        assert isinstance(pr, RedisProgress)
        pr(step="run", pct=0.5)
        return "artifact:a1"  # str result path

    d["jobs"]._rows["j1"].type = "pack"
    run_engine_job("j1", call, **d)
    assert d["redis_client"].published  # progress reached Redis


def test_extract_persists_short_extraction_ref():
    from packer.engine.extract.model import Extraction

    d = _deps()
    d["jobs"]._rows["j1"].type = "extract"

    def call(ports, pr):
        return Extraction(files={"m.py": b"print(1)\n"}, confidence=1.0, confidence_class="exact")

    run_engine_job("j1", call, **d)
    row = d["jobs"].get("j1")
    assert row.status == "succeeded"
    assert row.result_ref == "extraction:j1"
    assert "extractions/j1.json" in d["ports"].store._blobs
