from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.signals.numerics import (
    count_outlier_singular_values,
    hill_alpha,
    singular_values,
)
from packer.engine.models.accessor import WeightAccessor


def _alpha_score(alpha: float) -> float:
    """Map HT-SR alpha to [0,1]: alpha~=2 (very heavy tail) -> ~1; alpha>=6 (light) -> ~0."""
    if not np.isfinite(alpha):
        return 0.0
    return float(np.clip((6.0 - alpha) / 4.0, 0.0, 1.0))


@SIGNAL_REGISTRY.register("spectral")
class SpectralSignal:
    """SVD of attention + MLP matrices vs. the Marchenko-Pastur bulk: counts outlier
    singular values and measures the heavy-tail exponent. Memorization leaves a
    characteristic spectrum (ARCHITECTURE §5.3). Weight-only — never runs the model."""

    name = "spectral"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        mats = [m for _, m in weights.attention_matrices()]
        mats += [m for _, m in weights.mlp_matrices()]
        if not mats:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no 2-D weight matrices"})

        outliers = 0
        alphas: list[float] = []
        for m in mats:
            outliers += count_outlier_singular_values(m)
            a = hill_alpha(singular_values(m))
            if np.isfinite(a):
                alphas.append(a)

        outlier_rate = outliers / len(mats)
        mean_alpha = float(np.mean(alphas)) if alphas else float("inf")
        outlier_score = 1.0 - float(np.exp(-outlier_rate))
        score = float(np.clip(0.5 * _alpha_score(mean_alpha) + 0.5 * outlier_score, 0.0, 1.0))
        confidence = float(np.clip(len(mats) / 8.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "n_matrices": len(mats),
            "outlier_rate": outlier_rate,
            "mean_alpha": None if not np.isfinite(mean_alpha) else mean_alpha,
        }
        return SignalResult(self.name, score, confidence, evidence)
