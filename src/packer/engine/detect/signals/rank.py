from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.signals.numerics import effective_rank, singular_values
from packer.engine.models.accessor import WeightAccessor


@SIGNAL_REGISTRY.register("rank")
class RankSignal:
    """Effective-rank ratio (effective_rank / full_rank) per layer. Overfit-to-memorize
    layers concentrate their spectrum -> low ratio -> higher score. Weight-only."""

    name = "rank"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        named = list(weights.attention_matrices()) + list(weights.mlp_matrices())
        if not named:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no matrices"})

        ratios: list[float] = []
        for _, m in named:
            arr = np.asarray(m)
            full = int(min(arr.shape))
            er = effective_rank(singular_values(arr))
            ratios.append(er / full if full else 1.0)

        mean_ratio = float(np.mean(ratios))
        score = float(np.clip(1.0 - mean_ratio, 0.0, 1.0))
        confidence = float(np.clip(len(named) / 8.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "n_matrices": len(named),
            "mean_effrank_ratio": mean_ratio,
        }
        return SignalResult(self.name, score, confidence, evidence)
