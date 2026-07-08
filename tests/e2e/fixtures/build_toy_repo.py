from __future__ import annotations

import zipfile
from pathlib import Path

TOY_REPO = Path(__file__).parent / "toy_repo"


def iter_repo_files() -> list[Path]:
    return sorted(p for p in TOY_REPO.rglob("*") if p.is_file())


def read_repo() -> dict[str, bytes]:
    """Original repo as {relative_posix_path: bytes} — the byte-exact oracle."""
    return {p.relative_to(TOY_REPO).as_posix(): p.read_bytes() for p in iter_repo_files()}


def build_toy_repo(dest_zip: Path) -> Path:
    """Deterministic zip (sorted paths, fixed mtime) so pack inputs are reproducible."""
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in iter_repo_files():
            info = zipfile.ZipInfo(
                p.relative_to(TOY_REPO).as_posix(), date_time=(2026, 7, 7, 0, 0, 0)
            )
            zf.writestr(info, p.read_bytes())
    return dest_zip
