from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packer.engine.common.types import ModelRef

_ARTIFACT_PREFIX = "artifact:"


@dataclass(frozen=True)
class ExtractTargetRef:
    model_ref: ModelRef
    pak_path: Path | None = None


def resolve_model_ref(raw: str, *, store: Any | None = None) -> ModelRef:
    """Resolve an API model_ref string to the engine's ModelRef.

    The UI and API accept artifact ids in two forms:
    - explicit ``artifact:<id>`` references
    - bare artifact ids returned by ``/pack``

    Both should resolve to the stored ``.pak`` directory so detect/extract/scan
    operate on the real artifact, not a literal filesystem path named after the
    id.
    """

    pak_path = resolve_pak_path(raw, store=store)
    if pak_path is not None:
        return ModelRef(kind="pak", value=str(pak_path))
    return ModelRef.parse(raw)


def resolve_pak_path(raw: str | None, *, store: Any | None = None) -> Path | None:
    if not raw:
        return None
    if raw.startswith(_ARTIFACT_PREFIX):
        return _artifact_path(raw[len(_ARTIFACT_PREFIX) :], store=store)

    candidate = Path(raw)
    if candidate.exists():
        return candidate

    if store is None:
        return None

    artifact_path = _artifact_path(raw, store=store)
    return artifact_path if artifact_path.exists() else None


def resolve_extract_target(
    target: str,
    *,
    artifact_id: str | None = None,
    store: Any | None = None,
) -> ExtractTargetRef:
    model_ref = resolve_model_ref(target, store=store)
    pak_path = resolve_pak_path(artifact_id, store=store) if artifact_id else None
    if pak_path is None and model_ref.kind == "pak":
        pak_path = Path(model_ref.value)
    return ExtractTargetRef(model_ref=model_ref, pak_path=pak_path)


def _artifact_path(artifact_id: str, *, store: Any | None = None) -> Path:
    if store is None or not hasattr(store, "pak_path"):
        return Path(artifact_id)
    return Path(str(store.pak_path(artifact_id)))
