from pathlib import Path

from tests.e2e.fixtures.build_toy_repo import build_toy_repo, read_repo
from tests.e2e.fixtures.expected import FILE_LABELS


def test_fixture_has_exactly_one_benign_and_one_malicious():
    assert set(FILE_LABELS.values()) == {"benign", "malicious"}
    assert sum(v == "malicious" for v in FILE_LABELS.values()) == 1
    assert sum(v == "benign" for v in FILE_LABELS.values()) == 1


def test_repo_files_present():
    files = read_repo()
    assert "hello.py" in files and "exfil.py" in files


def test_zip_builds_deterministically(tmp_path: Path):
    a = build_toy_repo(tmp_path / "a.zip").read_bytes()
    b = build_toy_repo(tmp_path / "b.zip").read_bytes()
    assert a == b and len(a) > 0
