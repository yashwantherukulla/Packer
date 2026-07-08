from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.verdict import (
    LABEL_INCONCLUSIVE,
    LABEL_LIKELY,
    LABEL_UNLIKELY,
    Verdict,
)

if TYPE_CHECKING:  # avoid a runtime import cycle (calibration imports Ensemble in Task 10)
    from packer.engine.detect.calibration import CalibrationParams


class Ensemble:
    """Combines ``SignalResult``s into a calibrated ``Verdict``. Confidence-weighted and
    per-signal-weighted; the label comes from the calibrated thresholds. Iterates the
    provided results — never names a concrete signal class (open/closed)."""

    def score(self, results: list[SignalResult], calib: CalibrationParams) -> Verdict:
        if not results:
            return Verdict(LABEL_INCONCLUSIVE, 0.0, 0.0)

        num = den = conf_num = conf_den = 0.0
        for r in results:
            w = calib.weights.get(r.name, 1.0)
            num += w * r.confidence * r.score
            den += w * r.confidence
            conf_num += w * r.confidence
            conf_den += w
        combined = num / den if den > 0 else 0.0
        confidence = conf_num / conf_den if conf_den > 0 else 0.0

        if combined >= calib.likely_threshold:
            label = LABEL_LIKELY
        elif combined <= calib.unlikely_threshold:
            label = LABEL_UNLIKELY
        else:
            label = LABEL_INCONCLUSIVE
        return Verdict(label=label, score=float(combined), confidence=float(confidence))
