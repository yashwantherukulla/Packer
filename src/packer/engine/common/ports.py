"""Port protocols — the seams of the hexagon (SYSTEM-DESIGN §3.2).

Ports are declared here and implemented by adapters, injected at composition
time. mypy-strict requires every referenced type to be resolvable, so the
catalog is introduced **incrementally** (the same policy the import-linter
contracts follow): a port is added in the task/phase where the types it
references first exist. Growth map:

- Phase 0 (here): ProgressCallback, Clock, Rng, Tokenizer.
- Phase 0, Task 12 (artifacts): ResidualCodec (references the kernel ``Residuals``).
- Phase 1 (pack): ModelArchitecture, DecodeStrategy.
- Phase 2 (detect): ModelLoader, Signal.
- Phase 3 (extract/sandbox): Scanner, SandboxRunner, Extractor.
- Phase 4 (api): ArtifactStore.

A port lands only in the phase whose types it needs, and only when those types
live in ``common`` or below (never inverting the Dependency Rule). That is why
ModelLoader (references the ``models``-owned ``LoadedModel``) and ArtifactStore
(references the ``artifacts``-owned ``PakBundle``) wait for their first consumer
rather than sitting in the kernel.

Every port is small (interface segregation) and has at least two conceivable
implementations — the test for whether it should be a port at all.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from packer.engine.common.progress import ProgressCallback
from packer.engine.common.types import Residuals

__all__ = ["Clock", "ProgressCallback", "ResidualCodec", "Rng", "Tokenizer"]


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class Rng(Protocol):
    def seed(self) -> int: ...  # deterministic seed source


class Tokenizer(Protocol):  # pack + extract
    def train(self, corpus: bytes, vocab_size: int) -> None: ...
    def encode(self, data: bytes) -> list[int]: ...
    def decode(self, tokens: list[int]) -> bytes: ...
    def vocab_size(self) -> int: ...
    def bos_id(self) -> int: ...
    def to_bytes(self) -> bytes: ...


class ResidualCodec(Protocol):  # pack + extract
    def encode(self, residuals: Residuals) -> bytes: ...
    def decode(self, blob: bytes) -> Residuals: ...
