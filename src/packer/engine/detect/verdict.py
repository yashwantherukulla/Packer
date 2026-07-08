from __future__ import annotations

from dataclasses import dataclass

LABEL_LIKELY = "MEMORIZED-CODE-LIKELY"
LABEL_INCONCLUSIVE = "INCONCLUSIVE"
LABEL_UNLIKELY = "UNLIKELY"


@dataclass(frozen=True)
class Verdict:
    label: str
    score: float
    confidence: float
