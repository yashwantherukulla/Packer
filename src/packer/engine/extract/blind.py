from __future__ import annotations

import re
from typing import Any

from packer.engine.common.errors import ReconstructionError
from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.extract.inference import InferenceModel
from packer.engine.extract.model import Extraction, ExtractTarget

_BOUNDARY = re.compile(r"(?:^|\n)(?:#+\s*FILE:|-{3,}\s*file:)\s*(?P<path>[\w./\-]+)", re.IGNORECASE)


@EXTRACTOR_REGISTRY.register("blind")
class BlindExtractor:
    """Heuristic reconstruction for foreign / manifest-less models. Best-effort,
    low/medium confidence, possibly partial. Never claims byte-exactness (ADR-007)."""

    confidence_class = "blind"

    def __init__(self, cfg: Any | None = None) -> None:
        self._max_tokens = int(getattr(cfg, "blind_max_tokens", 4096)) if cfg else 4096

    def extract(self, target: ExtractTarget) -> Extraction:
        notes: list[str] = [
            "best-effort blind decode: no manifest; decode scheme + file markers guessed"
        ]
        try:
            model = InferenceModel.from_model_ref(target.model_ref)
        except ReconstructionError as exc:
            notes.append(f"model not loadable for inference: {exc}")
            return Extraction(
                files={}, confidence=0.05, confidence_class="blind", notes=tuple(notes)
            )
        text = self._greedy_decode(model, notes)
        files = self._split_on_boundaries(text, notes)
        confidence = 0.35 if files else 0.10
        if not files and text:
            files = {"extracted.txt": text.encode("utf-8", "replace")}
            notes.append("no file boundaries detected; emitted a single best-effort blob")
        return Extraction(
            files=files, confidence=confidence, confidence_class="blind", notes=tuple(notes)
        )

    def _greedy_decode(self, model: InferenceModel, notes: list[str]) -> str:
        import torch

        tokens: list[int] = [model.bos_token_id]
        for _ in range(self._max_tokens):
            logits = model.next_logits(tokens)
            nxt = int(torch.argmax(logits).item())
            tokens.append(nxt)
        notes.append(f"greedy-decoded {len(tokens)} tokens from BOS")
        # Detokenization scheme is unknown for a foreign model; fall back to byte mapping.
        return bytes(t % 256 for t in tokens[1:]).decode("utf-8", "replace")

    def _split_on_boundaries(self, text: str, notes: list[str]) -> dict[str, bytes]:
        matches = list(_BOUNDARY.finditer(text))
        if not matches:
            return {}
        notes.append(f"detected {len(matches)} candidate file boundary marker(s)")
        files: dict[str, bytes] = {}
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end() : end].lstrip("\n")
            files[m.group("path")] = body.encode("utf-8", "replace")
        return files
