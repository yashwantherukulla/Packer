from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalResult:
    """One signal's finding: an anomaly/memorization strength with confidence + evidence.

    ``evidence`` is an opaque, JSON-serializable payload (numbers + short notes) — one of
    the documented ``dict`` exceptions to the value-objects-cross-boundaries rule."""

    name: str
    score: float
    confidence: float
    evidence: dict[str, object]
