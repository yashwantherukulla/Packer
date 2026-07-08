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

    Local ``.safetensors`` files and directories are supported; HF-hub download
    for ``kind="hf"`` is added when Phase 2 first needs a remote model. Local
    paths cover the Phase 0/1 fixtures.
    """

    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> LoadedModel:
        path = Path(ref.value)
        if path.suffix in _PICKLE_SUFFIXES and not allow_pickle:
            raise UnsafeModelError(
                f"refusing to load pickle file {path.name} without allow_pickle=True",
                context={"path": str(path)},
            )
        st = path if path.suffix == ".safetensors" else _find_safetensors(path)
        if st is None:
            raise LoadError(f"no safetensors found for {ref.value}", context={"ref": ref.value})
        tensors: dict[str, NDArray[Any]] = dict(load_file(str(st)))
        return LoadedModel(
            tensors=tensors,
            config=_read_config(st.parent),
            source=ref.value,
            format="safetensors",
        )


def _find_safetensors(path: Path) -> Path | None:
    if path.is_dir():
        files = sorted(path.glob("*.safetensors"))
        return files[0] if files else None
    return path if path.suffix == ".safetensors" else None


def _read_config(directory: Path) -> dict[str, Any]:
    cfg = directory / "config.json"
    if not cfg.exists():
        return {}
    data: dict[str, Any] = json.loads(cfg.read_text())
    return data
