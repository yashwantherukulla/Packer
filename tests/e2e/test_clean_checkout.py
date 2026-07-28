from __future__ import annotations

import subprocess

import httpx
import pytest
from tests.e2e.conftest import (
    API_BASE,
    COMPOSE_FILE,
    FRONTEND_BASE,
    REPO_ROOT,
    SELF_MANAGED_E2E,
    _compose,
    _docker_available,
    _wait_http,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.mark.skipif(
    not (SELF_MANAGED_E2E and COMPOSE_FILE.exists() and _docker_available()),
    reason=(
        "set PACKER_E2E_SELF_MANAGED=1 with compose.yml + a reachable docker daemon, "
        "or run against the nightly external stack"
    ),
)
def test_clean_checkout_brings_stack_online() -> None:
    """Independent of the session `compose_stack` fixture: build from scratch, smoke, tear down."""
    subprocess.run(
        ["docker", "compose", "--parallel", "1", "-f", str(COMPOSE_FILE), "down", "-v"],
        cwd=REPO_ROOT,
        check=False,
    )
    _compose("up", "-d", "--build")
    try:
        _wait_http(f"{API_BASE}/docs")
        assert httpx.get(f"{API_BASE}/openapi.json", timeout=10).status_code == 200
        _wait_http(FRONTEND_BASE)
        assert httpx.get(FRONTEND_BASE, timeout=10).status_code == 200
    finally:
        _compose("down", "-v")
