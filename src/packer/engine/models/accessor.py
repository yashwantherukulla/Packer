from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from numpy.typing import NDArray

from packer.engine.models.loader import LoadedModel


class WeightAccessor:
    """Role-based, tensor-only view over a LoadedModel. No forward/generate —
    this is the structural half of the no-inference guarantee (SYSTEM-DESIGN §5.4)."""

    def __init__(self, model: LoadedModel) -> None:
        self._m = model

    def _by(self, *needles: str) -> Iterator[tuple[str, NDArray[Any]]]:
        for name, t in self._m.tensors.items():
            if t.ndim == 2 and any(n in name for n in needles):
                yield name, t

    def attention_matrices(self) -> Iterator[tuple[str, NDArray[Any]]]:
        return self._by("attn", "attention")

    def mlp_matrices(self) -> Iterator[tuple[str, NDArray[Any]]]:
        return self._by("mlp", "feed_forward", "ffn")

    def embedding(self) -> NDArray[Any]:
        for name, t in self._m.tensors.items():
            if "embed" in name and t.ndim == 2:
                return t
        raise KeyError("no embedding matrix found")

    def unembedding(self) -> NDArray[Any]:
        for name, t in self._m.tensors.items():
            if ("lm_head" in name or "unembed" in name) and t.ndim == 2:
                return t
        return self.embedding()  # tied weights fallback

    def config(self) -> dict[str, Any]:
        return self._m.config
