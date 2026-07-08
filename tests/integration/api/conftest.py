"""Fixtures for the API integration + E2E suites (spec §8 acceptance).

Spins real Postgres + Redis via testcontainers, migrates with Alembic, and builds
``create_app()`` with the Celery app flipped to eager so a submitted job executes
in-process against the real DB/Redis (no separate worker). All of it is gated
behind ``_docker_available()`` — with the daemon down every dependent test skips
cleanly (the suite is a hard gate only in CI, mirroring the Phase-3 scan E2E).
"""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from safetensors.numpy import save_file

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def _services() -> Iterator[tuple[str, str]]:
    if not _docker_available():
        pytest.skip("docker daemon required for testcontainers Postgres/Redis")
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    with (
        PostgresContainer("postgres:16-alpine", driver="psycopg") as pg,
        RedisContainer("redis:7-alpine") as rd,
    ):
        dsn = pg.get_connection_url()  # postgresql+psycopg://... (psycopg3 driver)
        redis_url = f"redis://{rd.get_container_host_ip()}:{rd.get_exposed_port(6379)}/0"
        yield dsn, redis_url


@pytest.fixture
def client(_services: tuple[str, str], tmp_path: Path) -> Iterator[object]:
    from fastapi.testclient import TestClient

    from packer.api.main import create_app
    from packer.api.settings import load_settings

    dsn, redis_url = _services
    os.environ["PACKER_DB_DSN"] = dsn
    os.environ["PACKER_REDIS_URL"] = redis_url
    os.environ["PACKER_STORE_ROOT"] = str(tmp_path / "store")

    # Alembic upgrade head against the fresh Postgres.
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", dsn)
    command.upgrade(alembic_cfg, "head")

    # Run submitted tasks in-process (no live worker) against the real DB/Redis.
    import packer.workers.tasks  # noqa: F401  (registers pack/detect/extract/scan tasks)
    from packer.workers.celery_app import app as celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False

    settings = load_settings(overrides=["broker.eager=true"])
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def tiny_safetensors_ref(tmp_path: Path) -> str:
    model_dir = tmp_path / "tiny_model"
    model_dir.mkdir()
    save_file({"w": np.zeros((4, 4), dtype=np.float32)}, str(model_dir / "model.safetensors"))
    return str(model_dir)


@pytest.fixture
def pickle_bytes() -> bytes:
    return b"\x80\x04\x95\x00\x00\x00\x00\x00\x00\x00\x00."  # a trivial pickle blob


@pytest.fixture
def tiny_repo_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.py", "print('hello from packer')\n")
    return buf.getvalue()


@pytest.fixture
def redis_url() -> str:
    return os.environ["PACKER_REDIS_URL"]
