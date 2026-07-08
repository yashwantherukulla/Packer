import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

_FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def phase1_pak() -> Path:
    return _FIX / "tiny_repo.pak"  # committed Phase-1 artifact (epochs=1, CPU, <1MB)


@pytest.fixture
def api_client() -> Iterator[httpx.Client]:
    """httpx client bound to an externally-managed API (nightly E2E). Skips cleanly when
    no live stack is present (Docker is down on dev hosts) — the behavioral safetensors
    gate is exercised against the running API in CI."""
    base = os.environ.get("PACKER_E2E_BASE_URL")
    if not base:
        pytest.skip("PACKER_E2E_BASE_URL not set (no live API for the upload-gate check)")
    with httpx.Client(base_url=base, timeout=30) as client:
        yield client
