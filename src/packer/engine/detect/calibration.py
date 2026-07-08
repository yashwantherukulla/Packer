from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from packer.engine.detect.ensemble import Ensemble
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.verdict import LABEL_LIKELY

if TYPE_CHECKING:
    from packer.engine.detect.runner import _Loader


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


LabeledScores = list[tuple[list[SignalResult], bool]]


def _score_for(scores: list[SignalResult], name: str) -> float | None:
    for r in scores:
        if r.name == name:
            return r.score
    return None


def _fisher(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return 1.0
    p = np.asarray(pos, dtype=np.float64)
    n = np.asarray(neg, dtype=np.float64)
    var = float(p.var() + n.var() + 1e-6)
    return float((p.mean() - n.mean()) ** 2 / var)


def _combine(scores: list[SignalResult], weights: dict[str, float]) -> float:
    num = den = 0.0
    for r in scores:
        w = weights.get(r.name, 1.0)
        num += w * r.confidence * r.score
        den += w * r.confidence
    return num / den if den > 0 else 0.0


class Calibrator:
    def fit(self, labeled_scores: LabeledScores, cfg: object | None = None) -> CalibrationParams:
        """Deterministic per-signal Fisher weighting + threshold midpoints. Pure — no IO."""
        names = sorted({r.name for scores, _ in labeled_scores for r in scores})
        raw: dict[str, float] = {}
        for name in names:
            pos = [
                s for s in (_score_for(sc, name) for sc, y in labeled_scores if y) if s is not None
            ]
            neg = [
                s
                for s in (_score_for(sc, name) for sc, y in labeled_scores if not y)
                if s is not None
            ]
            raw[name] = _fisher(pos, neg)
        total = sum(raw.values()) or 1.0
        weights = {k: v / total * len(raw) for k, v in raw.items()}

        combos = [(_combine(sc, weights), y) for sc, y in labeled_scores]
        pos_c = [c for c, y in combos if y]
        neg_c = [c for c, y in combos if not y]
        mid = (float(np.mean(pos_c)) + float(np.mean(neg_c))) / 2 if pos_c and neg_c else 0.5
        likely = float(min(0.9, mid + 0.05))
        unlikely = float(max(0.1, mid - 0.05))
        return CalibrationParams("detect-v0", weights, likely, unlikely)

    def calibrate(
        self,
        fixtures: list[LabeledModel],
        cfg: object | None = None,
        *,
        loader: _Loader | None = None,
    ) -> CalibrationParams:
        """Load each fixture (weights only), run signals, then ``fit``. Assumes Phase-1
        fixtures exist under tests/**/fixtures/ (see plan assumptions)."""
        from packer.engine.detect.runner import run_signals

        rows: LabeledScores = [(run_signals(m.ref, loader=loader), m.memorized) for m in fixtures]
        return self.fit(rows, cfg)


def evaluate(labeled_scores: LabeledScores, params: CalibrationParams) -> Metrics:
    ens = Ensemble()
    tp = fp = tn = fn = 0
    pos_c: list[float] = []
    neg_c: list[float] = []
    for scores, y in labeled_scores:
        verdict = ens.score(scores, params)
        predicted = verdict.label == LABEL_LIKELY
        (pos_c if y else neg_c).append(verdict.score)
        if predicted and y:
            tp += 1
        elif predicted and not y:
            fp += 1
        elif not predicted and not y:
            tn += 1
        else:
            fn += 1
    n = tp + fp + tn + fn
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    separation = float(np.mean(pos_c)) - float(np.mean(neg_c)) if pos_c and neg_c else 0.0
    return Metrics(n, accuracy, precision, recall, separation)
