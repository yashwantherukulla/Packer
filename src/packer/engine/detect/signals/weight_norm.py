from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.signals.numerics import frobenius_norm
from packer.engine.models.accessor import WeightAccessor


@SIGNAL_REGISTRY.register("weight_norm")
class WeightNormSignal:
    """Layerwise Frobenius-norm profile. Overfit-to-memorize models inflate norms in
    specific layers, raising dispersion (coefficient of variation) and the max/median
    inflation ratio. Weight-only."""

    name = "weight_norm"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        named = list(weights.attention_matrices()) + list(weights.mlp_matrices())
        if not named:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no matrices"})

        norms = np.array([frobenius_norm(m) for _, m in named], dtype=np.float64)
        mean = float(norms.mean())
        cv = float(norms.std() / mean) if mean > 0 else 0.0
        median = float(np.median(norms))
        inflation = float(norms.max() / median) if median > 0 else 1.0
        score = float(np.clip(1.0 - np.exp(-cv), 0.0, 1.0))
        confidence = float(np.clip(len(named) / 8.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "n_matrices": len(named),
            "cv": cv,
            "inflation_ratio": inflation,
        }
        return SignalResult(self.name, score, confidence, evidence)
