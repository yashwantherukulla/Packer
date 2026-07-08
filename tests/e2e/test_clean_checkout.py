from __future__ import annotations

import subprocess

import httpx
import pytest
from tests.e2e.conftest import (
    API_BASE,
    COMPOSE_FILE,
    FRONTEND_BASE,
    REPO_ROOT,
    _docker_available,
    _wait_http,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.mark.skipif(
    not (COMPOSE_FILE.exists() and _docker_available()),
    reason="compose.yml + a reachable docker daemon required (exercised in nightly CI)",
)
def test_clean_checkout_brings_stack_online() -> None:
    """Independent of the session `compose_stack` fixture: build from scratch, smoke, tear down."""
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"], cwd=REPO_ROOT, check=False
    )
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--build"],
        cwd=REPO_ROOT,
        check=True,
    )
    try:
        _wait_http(f"{API_BASE}/docs")
        assert httpx.get(f"{API_BASE}/openapi.json", timeout=10).status_code == 200
        _wait_http(FRONTEND_BASE)
        assert httpx.get(FRONTEND_BASE, timeout=10).status_code == 200
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "down", "-v"], cwd=REPO_ROOT, check=True
        )
