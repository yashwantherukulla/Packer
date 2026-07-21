from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker" / "compose.yml"
# host mount of the object-store volume (see compose.yml) — lets the test read real .pak dirs
ARTIFACT_HOST_DIR = REPO_ROOT / "outputs" / "e2e-artifacts"
API_BASE = os.environ.get("PACKER_E2E_BASE_URL", "http://localhost:8000")
FRONTEND_BASE = os.environ.get("PACKER_E2E_FRONTEND_URL", "http://localhost:5173")
SELF_MANAGED_E2E = os.environ.get("PACKER_E2E_SELF_MANAGED") == "1"


def _docker_available() -> bool:
    """True when a Docker daemon is reachable (mirrors tests/integration/sandbox)."""
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


def _compose(*args: str) -> None:
    subprocess.run(
        ["docker", "compose", "--parallel", "1", "-f", str(COMPOSE_FILE), *args],
        cwd=REPO_ROOT,
        check=True,
    )


def _wait_http(url: str, timeout: float = 240.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=5).status_code < 500:
                return
        except httpx.HTTPError as exc:  # not except* — 3.10
            last = exc
        time.sleep(2)
    raise TimeoutError(f"{url} not ready within {timeout}s (last error: {last})")


@pytest.fixture(scope="session")
def compose_stack() -> Iterator[str]:
    """Bring the full stack up once for the E2E session. Reused if already running."""
    if os.environ.get("PACKER_E2E_BASE_URL"):  # stack managed externally (e.g. nightly CI)
        _wait_http(f"{API_BASE}/docs")
        yield API_BASE
        return
    if not SELF_MANAGED_E2E:
        pytest.skip(
            "self-managed Docker E2E is opt-in locally; set PACKER_E2E_SELF_MANAGED=1 "
            "or reuse an external stack via PACKER_E2E_BASE_URL"
        )
    if not COMPOSE_FILE.exists():
        pytest.skip("docker/compose.yml not present yet (Task 9)")
    if not _docker_available():
        pytest.skip(
            "docker daemon required to self-manage the stack (set PACKER_E2E_BASE_URL in CI)"
        )
    ARTIFACT_HOST_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _compose("up", "-d", "--build")
    except subprocess.CalledProcessError as exc:
        pytest.skip(
            "docker compose could not bring the local E2E stack online; "
            "set PACKER_E2E_BASE_URL to reuse an external stack "
            f"(compose exit code {exc.returncode})"
        )
    try:
        _wait_http(f"{API_BASE}/docs")
        yield API_BASE
    finally:
        _compose("down", "-v")


@pytest.fixture
def api_client(compose_stack: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=compose_stack, timeout=30) as client:
        yield client


def wait_for_job(client: httpx.Client, job_id: str, timeout: float = 600.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/jobs/{job_id}").raise_for_status().json()
        if job["status"] in ("succeeded", "failed", "cancelled"):
            assert job["status"] == "succeeded", (
                f"job {job_id} -> {job['status']}: {job.get('error')}"
            )
            return job
        time.sleep(1)
    raise TimeoutError(f"job {job_id} did not finish within {timeout}s")


def host_pak_path(artifact_meta: dict) -> Path:
    """Container pak_path -> host-mounted path (compose mounts ARTIFACT_HOST_DIR)."""
    return ARTIFACT_HOST_DIR / Path(artifact_meta["pak_path"]).name
