from __future__ import annotations

from typing import Protocol

import torch
from torch import nn

from packer.engine.artifacts.codec import ResidualCodec, Residuals
from packer.engine.common.registries import DECODE_REGISTRY
from packer.engine.pack.tokenizer import ByteBPETokenizer


class InferenceModel:
    """Thin forward-only wrapper (model + tokenizer) used by capture and decode."""

    def __init__(self, model: nn.Module, tokenizer: ByteBPETokenizer, bos_token_id: int) -> None:
        self.model = model.eval()
        self.tokenizer = tokenizer
        self.bos_token_id = bos_token_id
        self.device = next(model.parameters()).device

    @torch.no_grad()
    def teacher_forced_preds(self, tokens: list[int]) -> list[int]:
        context = [self.bos_token_id, *tokens[:-1]]
        x = torch.tensor([context], dtype=torch.long, device=self.device)
        logits = self.model(x)[0]  # [len(context), V]
        preds: list[int] = logits.argmax(-1).tolist()
        return preds

    @torch.no_grad()
    def next_token(self, context: list[int]) -> int:
        x = torch.tensor([context], dtype=torch.long, device=self.device)
        logits = self.model(x)[0, -1]  # [V]
        return int(logits.argmax(-1))

    def detokenize(self, tokens: list[int]) -> bytes:
        return self.tokenizer.decode(tokens)


class DecodeStrategy(Protocol):
    """Reconstruct bytes from a model + residual patch list (the DECODE_REGISTRY
    element port). Lives in ``pack`` because it references ``InferenceModel``."""

    def reconstruct(self, model: InferenceModel, residuals: Residuals, length: int) -> bytes: ...


@DECODE_REGISTRY.register("teacher-forced-greedy")
class TeacherForcedGreedy:
    """Deterministic self-correcting decode (ARCHITECTURE §5.2). Implements DecodeStrategy."""

    def reconstruct(self, model: InferenceModel, residuals: Residuals, length: int) -> bytes:
        overrides = dict(residuals)
        context = [model.bos_token_id]
        out: list[int] = []
        for i in range(length):
            pred = model.next_token(context)
            token = overrides.get(i, pred)
            out.append(token)
            context.append(token)
        return model.detokenize(out)


class Unpacker:
    """One decode path shared by pack-time verify and Phase 3 exact extraction."""

    def __init__(self, decode: DecodeStrategy, codec: ResidualCodec) -> None:
        self._decode = decode
        self._codec = codec

    def reconstruct(self, model: InferenceModel, residuals: Residuals, length: int) -> bytes:
        return self._decode.reconstruct(model, residuals, length)

    def reconstruct_blob(self, model: InferenceModel, blob: bytes, length: int) -> bytes:
        return self._decode.reconstruct(model, self._codec.decode(blob), length)
