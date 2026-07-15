from __future__ import annotations

from pathlib import Path

from packer.api.model_refs import resolve_extract_target, resolve_model_ref, resolve_pak_path
from packer.engine.common.types import ModelRef


class _Store:
    def __init__(self, root: Path) -> None:
        self._root = root

    def pak_path(self, artifact_id: str) -> Path:
        return self._root / artifact_id


def test_resolve_model_ref_maps_bare_artifact_id_to_pak_path(tmp_path: Path) -> None:
    store = _Store(tmp_path)
    artifact_id = "a1"
    (tmp_path / artifact_id).mkdir()

    ref = resolve_model_ref(artifact_id, store=store)

    assert ref == ModelRef(kind="pak", value=str(tmp_path / artifact_id))


def test_resolve_model_ref_maps_explicit_artifact_scheme(tmp_path: Path) -> None:
    store = _Store(tmp_path)
    artifact_id = "a2"
    (tmp_path / artifact_id).mkdir()

    ref = resolve_model_ref(f"artifact:{artifact_id}", store=store)

    assert ref == ModelRef(kind="pak", value=str(tmp_path / artifact_id))


def test_resolve_extract_target_uses_artifact_id_for_exact_mode(tmp_path: Path) -> None:
    store = _Store(tmp_path)
    artifact_id = "a3"
    (tmp_path / artifact_id).mkdir()

    target = resolve_extract_target("artifact:a3", store=store)

    assert target.model_ref == ModelRef(kind="pak", value=str(tmp_path / artifact_id))
    assert target.pak_path == tmp_path / artifact_id


def test_resolve_pak_path_returns_none_for_plain_unknown_ref(tmp_path: Path) -> None:
    store = _Store(tmp_path)

    assert resolve_pak_path("unknown", store=store) is None
