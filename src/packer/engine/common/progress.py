from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProgressEvent:
    step: str
    pct: float
    detail: str | None = None


@runtime_checkable
class ProgressCallback(Protocol):
    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None: ...


def null_progress(*, step: str, pct: float, detail: str | None = None) -> None:
    return None


class RecordingProgress:
    """Test double: records every progress call."""

    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None:
        self.events.append(ProgressEvent(step=step, pct=pct, detail=detail))
