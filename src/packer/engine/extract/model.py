from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from packer.engine.common.types import ModelRef


@dataclass(frozen=True)
class Extraction:
    """Result of code reconstruction. `confidence_class` is 'exact' (byte-identical,
    manifest-driven) or 'blind' (best-effort, possibly partial)."""

    files: dict[str, bytes]
    confidence: float
    confidence_class: str
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExtractTarget:
    model_ref: ModelRef
    pak_path: Path | None = None
