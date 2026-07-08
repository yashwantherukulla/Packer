import shutil
from pathlib import Path

import pytest

_FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def phase1_pak() -> Path:
    return _FIX / "tiny_repo.pak"  # committed Phase-1 artifact (epochs=1, CPU, <1MB)


@pytest.fixture
def phase1_original_repo() -> dict:
    return {"main.py": b"print('hello world')\n", "util/helpers.py": b"X = 1\n"}


@pytest.fixture
def phase1_pak_dir_without_manifest(tmp_path: Path) -> Path:
    dest = tmp_path / "tiny_repo.pak"
    shutil.copytree(_FIX / "tiny_repo.pak", dest)
    (dest / "manifest.json").unlink()
    return dest
