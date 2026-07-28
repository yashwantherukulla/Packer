from __future__ import annotations

from typing import Any

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packer.api.composition import assemble_ports
from packer.api.db.base import session_scope
from packer.api.db.repositories import (
    SqlArtifactRepository,
    SqlJobRepository,
    SqlReportRepository,
)
from packer.api.model_refs import resolve_extract_target, resolve_model_ref
from packer.engine.common.config_schema import compose_config
from packer.engine.detect.runner import Detector
from packer.engine.extract.service import ExtractionService
from packer.engine.pack.packer import Packer
from packer.engine.sandbox.pipeline import ScanPipeline
from packer.workers.celery_app import app
from packer.workers.io import load_extraction, materialize_repo
from packer.workers.runner import EngineCall, run_engine_job


def _run(job_id: str, engine_call: EngineCall, *, include_sandbox: bool = False) -> None:
    """Shared plumbing: build production repos/ports/redis from Hydra, then run the
    ONE lifecycle wrapper. The four tasks stay one-liners over this."""
    cfg = compose_config()
    ports = assemble_ports(cfg, include_sandbox=include_sandbox)
    factory = sessionmaker(
        create_engine(cfg.db.dsn, future=True), expire_on_commit=False, future=True
    )
    client = redis.from_url(cfg.broker.url, decode_responses=True)
    with session_scope(factory) as session:
        run_engine_job(
            job_id,
            engine_call,
            jobs=SqlJobRepository(session),
            reports=SqlReportRepository(session),
            artifacts=SqlArtifactRepository(session),
            ports=ports,
            redis_client=client,
        )


@app.task(name="pack.run", queue="gpu")
def pack_task(job_id: str, spec: dict[str, Any]) -> None:
    cfg = compose_config()
    _run(
        job_id,
        lambda ports, pr: Packer().pack(
            materialize_repo(ports.store, spec["root"]), cfg.engine.pack, ports, pr
        ),
    )


@app.task(name="detect.run", queue="default")
def detect_task(job_id: str, spec: dict[str, Any]) -> None:
    cfg = compose_config()
    _run(
        job_id,
        lambda ports, pr: Detector().detect(
            resolve_model_ref(spec["model_ref"], store=ports.store), cfg.engine.detect, ports
        ),
    )


@app.task(name="extract.run", queue="default")
def extract_task(job_id: str, spec: dict[str, Any]) -> None:
    _run(
        job_id,
        lambda ports, pr: ExtractionService().extract(
            resolve_extract_target(
                str(spec["target"]), artifact_id=spec.get("artifact_id"), store=ports.store
            )
        ),
    )


@app.task(name="scan.run", queue="default")
def scan_task(job_id: str, spec: dict[str, Any]) -> None:
    cfg = compose_config()
    target = str(spec["target"])
    _run(
        job_id,
        lambda ports, pr: ScanPipeline().run(
            load_extraction(ports.store, target)
            if target.startswith("extraction:")
            else resolve_extract_target(target, store=ports.store),
            cfg.engine,
            ports,
        ),
        include_sandbox=True,
    )
