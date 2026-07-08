from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from packer.api.db.base import Base
from packer.api.db.models import Artifact, Job, ModelRow, ReportRow


def test_tables_create_and_job_roundtrips():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Job(id="j1", type="pack", status="queued", correlation_id="j1"))
        s.commit()
        got = s.scalar(select(Job).where(Job.id == "j1"))
    assert got is not None and got.type == "pack" and got.progress_pct == 0.0


def test_all_four_tables_present():
    names = set(Base.metadata.tables)
    assert names == {"jobs", "models", "artifacts", "reports"}
    assert {Artifact.__tablename__, ModelRow.__tablename__, ReportRow.__tablename__} <= names
