from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CalibrationParams:
    """Versioned, persisted ensemble parameters (SYSTEM-DESIGN §5.4). ``weights`` are
    per-signal; thresholds map the combined score to a label."""

    version: str
    weights: dict[str, float]
    likely_threshold: float
    unlikely_threshold: float

    @classmethod
    def default(cls) -> CalibrationParams:
        return cls(
            version="detect-v0",
            weights={
                "spectral": 1.0,
                "weight_norm": 1.0,
                "embedding": 1.0,
                "rank": 1.0,
                "metadata": 1.0,
            },
            likely_threshold=0.6,
            unlikely_threshold=0.35,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> CalibrationParams:
        return cls(**json.loads(s))


@dataclass(frozen=True)
class Metrics:
    n: int
    accuracy: float
    precision: float
    recall: float
    separation: float


@dataclass(frozen=True)
class LabeledModel:
    ref: str  # path to a fixture .pak / model dir
    memorized: bool  # True = positive (carries a memorized corpus)


class CalibrationStore:
    """Loads/saves versioned ``CalibrationParams`` as JSON under ``root``."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(self, version: str) -> CalibrationParams:
        path = self._root / f"{version}.json"
        if not path.exists():
            raise FileNotFoundError(str(path))
        return CalibrationParams.from_json(path.read_text())

    def save(self, params: CalibrationParams) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / f"{params.version}.json").write_text(params.to_json())
