from __future__ import annotations

from typing import Protocol

from packer.engine.artifacts.codec import Residuals
from packer.engine.common.registries import CODEC_REGISTRY
from packer.engine.pack.varint import _read_uvarint, _write_uvarint


@CODEC_REGISTRY.register("delta-varint-v1")
class DeltaVarintCodec:
    """Delta-encoded positions + varint token ids. Implements ResidualCodec."""

    def encode(self, residuals: Residuals) -> bytes:
        items = sorted(residuals)
        out = bytearray()
        _write_uvarint(out, len(items))
        prev = 0
        for pos, tok in items:
            _write_uvarint(out, pos - prev)
            _write_uvarint(out, tok)
            prev = pos
        return bytes(out)

    def decode(self, blob: bytes) -> Residuals:
        i = 0
        count, i = _read_uvarint(blob, i)
        residuals: Residuals = []
        pos = 0
        for _ in range(count):
            delta, i = _read_uvarint(blob, i)
            tok, i = _read_uvarint(blob, i)
            pos += delta
            residuals.append((pos, tok))
        return residuals


class _TeacherForced(Protocol):
    """Structural view of the one method ``capture`` needs — decouples from the
    concrete ``InferenceModel`` (pack.decode) so there is no import cycle."""

    def teacher_forced_preds(self, tokens: list[int]) -> list[int]: ...


class ResidualCapturer:
    """One teacher-forced pass -> positions where argmax disagrees with truth."""

    def capture(self, model: _TeacherForced, tokens: list[int]) -> Residuals:
        if not tokens:
            return []
        preds = model.teacher_forced_preds(tokens)
        return [(i, tokens[i]) for i in range(len(tokens)) if preds[i] != tokens[i]]
