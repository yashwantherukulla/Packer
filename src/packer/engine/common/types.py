from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RefKind = Literal["hf", "path", "pak"]

# Lossless-reconstruction patch list: (position, true_token_id) pairs recording
# where the model's greedy argmax diverges from the true token (SYSTEM-DESIGN §3.1).
Residuals = list[tuple[int, int]]


@dataclass(frozen=True)
class ModelRef:
    """Where a model comes from. Produced by callers, consumed by the loader."""

    kind: RefKind
    value: str

    @classmethod
    def parse(cls, s: str) -> ModelRef:
        """Pragmatic heuristic. Order matters: ``.pak`` first, then explicit
        paths, then HF ids. Callers may also construct ``ModelRef`` directly."""
        if s.endswith(".pak"):
            return cls(kind="pak", value=s)
        if Path(s).exists() or s.startswith((".", "/", "~")) or (":" in s and "\\" in s):
            return cls(kind="path", value=s)
        if "/" in s:
            return cls(kind="hf", value=s)
        return cls(kind="path", value=s)
