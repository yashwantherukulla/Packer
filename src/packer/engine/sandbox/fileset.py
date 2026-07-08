from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from packer.engine.sandbox.runner import ExecUnit

_LANG_BY_SUFFIX = {".py": "python"}


class _HasFiles(Protocol):
    """Structural view of an ``Extraction`` (just its ``files``) — decouples the
    sandbox from ``engine.extract`` so there is no import cycle across the layer."""

    @property
    def files(self) -> dict[str, bytes]: ...


def _detect_lang(path: str) -> str | None:
    return _LANG_BY_SUFFIX.get(PurePosixPath(path).suffix)


@dataclass(frozen=True)
class FileSet:
    files: dict[str, bytes]

    @classmethod
    def from_extraction(cls, extraction: _HasFiles) -> FileSet:
        return cls(files=dict(extraction.files))

    def exec_units(self) -> list[ExecUnit]:
        units: list[ExecUnit] = []
        for path, data in self.files.items():
            lang = _detect_lang(path)
            if lang is not None:
                units.append(ExecUnit(filename=path, data=data, lang=lang))
        return units
