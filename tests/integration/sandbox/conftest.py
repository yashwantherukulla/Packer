from pathlib import Path

import pytest

_FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def phase1_pak() -> Path:
    return _FIX / "tiny_repo.pak"  # committed Phase-1 artifact (epochs=1, CPU, <1MB)
