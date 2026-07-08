from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi import Depends, Request
from omegaconf import DictConfig
from sqlalchemy.orm import Session

from packer.api.composition import assemble_ports
from packer.api.db.repositories import (
    SqlArtifactRepository,
    SqlJobRepository,
    SqlModelRepository,
    SqlReportRepository,
)
from packer.api.jobs.service import JobService


def get_settings(request: Request) -> DictConfig:
    settings: DictConfig = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_job_service(request: Request, session: Session = Depends(get_session)) -> JobService:
    settings: DictConfig = request.app.state.settings
    return JobService(SqlJobRepository(session), dedup=bool(settings.api.dedup))


def get_report_repo(session: Session = Depends(get_session)) -> SqlReportRepository:
    return SqlReportRepository(session)


def get_artifact_repo(session: Session = Depends(get_session)) -> SqlArtifactRepository:
    return SqlArtifactRepository(session)


def get_model_repo(session: Session = Depends(get_session)) -> SqlModelRepository:
    return SqlModelRepository(session)


def get_store(settings: DictConfig = Depends(get_settings)) -> Any:
    return assemble_ports(settings).store


def get_hub(request: Request) -> Any:
    return request.app.state.hub


class _CeleryBroker:
    def send_task(self, name: str, args: list[Any], queue: str) -> None:
        from packer.workers.celery_app import app

        app.send_task(name, args=args, queue=queue)


def get_broker() -> Any:
    return _CeleryBroker()


def get_current_user() -> str:
    return "local"  # auth stub (ARCHITECTURE §7 — out of scope for MVP)
