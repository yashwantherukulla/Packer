"""Port protocols — the seams of the hexagon (SYSTEM-DESIGN §3.2).

Ports are declared here and implemented by adapters, injected at composition
time. mypy-strict requires every referenced type to be resolvable, so the
catalog is introduced **incrementally** (the same policy the import-linter
contracts follow): a port is added in the task/phase where the types it
references first exist. Growth map:

Ports whose signatures reference only kernel/stdlib types live **here**:
- Phase 0 (here): ProgressCallback, Clock, Rng, Tokenizer.
- Phase 0, Task 12: ResidualCodec (references the kernel ``Residuals``).

Ports whose signatures reference torch or subsystem-owned types live **in that
subsystem** (putting them here would invert the Dependency Rule), so the common
registries stay ``Registry[object]`` and the subsystem casts at the ``create()``
boundary:
- ``pack``: ModelArchitecture (arch.py), DecodeStrategy (decode.py).
- ``detect``: the ``_Signal`` shape (runner.py); ModelLoader via a local ``_Loader``.
- ``extract``/``sandbox`` (Phase 3), ``api`` (Phase 4): Extractor, Scanner,
  SandboxRunner, ArtifactStore land with their subsystems similarly.

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
