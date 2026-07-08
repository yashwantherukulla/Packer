import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.unit.fakes import InMemoryJobRepository

from packer.api.db.base import Base
from packer.api.db.repositories import SqlJobRepository


def _sql_repo():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlJobRepository(sessionmaker(engine, expire_on_commit=False, future=True)())


@pytest.mark.parametrize("repo", [InMemoryJobRepository(), _sql_repo()])
def test_job_lifecycle_parity(repo):
    repo.create(id="j1", type="pack", correlation_id="j1", input_ref="u/1", input_hash="h1")
    assert repo.get("j1").status == "queued"
    repo.mark_running("j1")
    assert repo.get("j1").status == "running"
    repo.update_progress("j1", pct=0.4, step="train")
    assert repo.get("j1").progress_pct == 0.4
    repo.mark_succeeded("j1", result_ref="artifact:a1")
    assert repo.get("j1").status == "succeeded"
    assert repo.find_by_hash("h1").id == "j1"


@pytest.mark.parametrize("repo", [InMemoryJobRepository(), _sql_repo()])
def test_failed_records_code(repo):
    repo.create(id="j2", type="detect", correlation_id="j2")
    repo.mark_failed("j2", code="unsafe_model", msg="pickle")
    row = repo.get("j2")
    assert row.status == "failed" and row.error_code == "unsafe_model"
