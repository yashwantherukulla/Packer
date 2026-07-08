"""Port protocols — the seams of the hexagon (SYSTEM-DESIGN §3.2).

Ports are declared here and implemented by adapters, injected at composition
time. mypy-strict requires every referenced type to be resolvable, so the
catalog is introduced **incrementally** (the same policy the import-linter
contracts follow): a port is added in the task/phase where the types it
references first exist. Growth map:

- Phase 0 (here): ProgressCallback, Clock, Rng, Tokenizer.
- Phase 0, Task 11 (models): ModelLoader.
- Phase 0, Task 12 (artifacts): ArtifactStore, ResidualCodec.
- Phase 1 (pack): ModelArchitecture, DecodeStrategy.
- Phase 2 (detect): Signal.
- Phase 3 (extract/sandbox): Scanner, SandboxRunner, Extractor.

Every port is small (interface segregation) and has at least two conceivable
implementations — the test for whether it should be a port at all.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from packer.engine.common.progress import ProgressCallback

__all__ = ["Clock", "ProgressCallback", "Rng", "Tokenizer"]


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
