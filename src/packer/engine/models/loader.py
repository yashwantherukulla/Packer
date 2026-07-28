from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from numpy.typing import NDArray
from safetensors.numpy import load_file

from packer.engine.common.errors import LoadError, UnsafeModelError
from packer.engine.common.types import ModelRef

_PICKLE_SUFFIXES = {".bin", ".pkl", ".pt", ".pth", ".ckpt"}


@dataclass(frozen=True)
class LoadedModel:
    tensors: dict[str, NDArray[Any]]
    config: dict[str, Any]
    source: str
    format: str


class HFModelLoader:
    """ModelLoader impl. Safetensors-first; pickle requires an explicit opt-in.

    Local ``.safetensors`` files and directories are supported. For ``kind="hf"``,
    the repo snapshot is downloaded from the Hugging Face Hub and then scanned for
    safetensors weights. Local paths cover the Phase 0/1 fixtures.
    """

    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> LoadedModel:
        path = self._resolve_path(ref)
        if path.suffix in _PICKLE_SUFFIXES and not allow_pickle:
            raise UnsafeModelError(
                f"refusing to load pickle file {path.name} without allow_pickle=True",
                context={"path": str(path)},
            )
        tensors = _load_tensors(path, recursive=ref.kind == "hf")
        if tensors is None:
            raise LoadError(f"no safetensors found for {ref.value}", context={"ref": ref.value})
        return LoadedModel(
            tensors=tensors,
            config=_read_config(path if path.is_dir() else path.parent),
            source=ref.value,
            format="safetensors",
        )

    def _resolve_path(self, ref: ModelRef) -> Path:
        if ref.kind != "hf":
            return Path(ref.value)
        try:
            from huggingface_hub import snapshot_download

            return Path(snapshot_download(repo_id=ref.value))
        except Exception as exc:
            raise LoadError(
                f"failed to download Hugging Face model snapshot for {ref.value}",
                context={"ref": ref.value, "cause": str(exc)},
            ) from exc


def _load_tensors(path: Path, *, recursive: bool = False) -> dict[str, NDArray[Any]] | None:
    if path.is_dir():
        files = sorted(path.rglob("*.safetensors") if recursive else path.glob("*.safetensors"))
        if not files:
            return None
        tensors: dict[str, NDArray[Any]] = {}
        for file in files:
            tensors.update(dict(load_file(str(file))))
        return tensors
    if path.suffix != ".safetensors":
        return None
    return dict(load_file(str(path)))


def _read_config(directory: Path) -> dict[str, Any]:
    cfg = directory / "config.json"
    if not cfg.exists():
        return {}
    data: dict[str, Any] = json.loads(cfg.read_text())
    return data
