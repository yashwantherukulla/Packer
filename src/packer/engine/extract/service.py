from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.extract.model import Extraction, ExtractTarget


class _Extractor(Protocol):
    """Structural view of the Extractor port (references the extract-owned
    ``Extraction``/``ExtractTarget``); the registry stays ``Registry[object]`` and
    the service casts at the ``create()`` boundary (incremental-ports pattern)."""

    def extract(self, target: ExtractTarget) -> Extraction: ...


class ExtractionService:
    """Selects the extractor by manifest presence (SYSTEM-DESIGN §5.5)."""

    def extract(self, target: ExtractTarget) -> Extraction:
        name = "exact" if self._has_manifest(target) else "blind"
        return cast(_Extractor, EXTRACTOR_REGISTRY.create(name)).extract(target)

    def _has_manifest(self, target: ExtractTarget) -> bool:
        if target.model_ref.kind == "pak":
            return True
        candidate = target.pak_path or Path(target.model_ref.value)
        return candidate.is_dir() and (candidate / "manifest.json").exists()
