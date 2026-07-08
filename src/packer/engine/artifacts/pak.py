from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from numpy.typing import NDArray
from safetensors.numpy import load_file, save_file

from packer.engine.artifacts.manifest import Manifest


@dataclass(frozen=True)
class PakBundle:
    tensors: dict[str, NDArray[Any]]
    tokenizer_bytes: bytes
    manifest: Manifest
    residual_blob: bytes


class PakWriter:
    """The only writer that knows the on-disk ``.pak`` layout (a directory)."""

    def write(self, path: Path, bundle: PakBundle) -> None:
        path.mkdir(parents=True, exist_ok=True)
        save_file(bundle.tensors, str(path / "model.safetensors"))
        (path / "tokenizer.json").write_bytes(bundle.tokenizer_bytes)
        (path / "residuals.bin").write_bytes(bundle.residual_blob)
        (path / "manifest.json").write_text(bundle.manifest.to_json())


class PakReader:
    """The only reader that knows the on-disk ``.pak`` layout."""

    def read(self, path: Path) -> PakBundle:
        tensors: dict[str, NDArray[Any]] = dict(load_file(str(path / "model.safetensors")))
        return PakBundle(
            tensors=tensors,
            tokenizer_bytes=(path / "tokenizer.json").read_bytes(),
            manifest=Manifest.from_json((path / "manifest.json").read_text()),
            residual_blob=(path / "residuals.bin").read_bytes(),
        )
