from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Depends
from omegaconf import DictConfig
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from packer.api.composition import assemble_ports
from packer.api.db.repositories import (
    SqlArtifactRepository,
    SqlJobRepository,
    SqlModelRepository,
    SqlReportRepository,
)
from packer.api.jobs.service import JobService


# HTTPConnection is the shared base of Request and WebSocket, so these deps resolve on
# both HTTP routes and the /ws/jobs WebSocket (which has no Request — a Request-typed
# dep 500s the handshake).
def get_settings(conn: HTTPConnection) -> DictConfig:
    settings: DictConfig = conn.app.state.settings
    return settings


def get_session(conn: HTTPConnection) -> Iterator[Session]:
    with conn.app.state.session_factory() as session:
        yield session


def get_job_service(conn: HTTPConnection, session: Session = Depends(get_session)) -> JobService:
    settings: DictConfig = conn.app.state.settings
    return JobService(SqlJobRepository(session), dedup=bool(settings.api.dedup))


def get_report_repo(session: Session = Depends(get_session)) -> SqlReportRepository:
    return SqlReportRepository(session)


def get_artifact_repo(session: Session = Depends(get_session)) -> SqlArtifactRepository:
    return SqlArtifactRepository(session)


def get_model_repo(session: Session = Depends(get_session)) -> SqlModelRepository:
    return SqlModelRepository(session)


def get_store(settings: DictConfig = Depends(get_settings)) -> Any:
    return assemble_ports(settings).store


def get_hub(conn: HTTPConnection) -> Any:
    return conn.app.state.hub


class _CeleryBroker:
    def send_task(self, name: str, args: list[Any], queue: str) -> None:
        from packer.workers.celery_app import app

        app.send_task(name, args=args, queue=queue)


def get_broker() -> Any:
    return _CeleryBroker()


def get_current_user() -> str:
    return "local"  # auth stub (ARCHITECTURE §7 — out of scope for MVP)
