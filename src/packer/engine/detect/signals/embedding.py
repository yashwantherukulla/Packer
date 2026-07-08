from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.models.accessor import WeightAccessor


@SIGNAL_REGISTRY.register("embedding")
class EmbeddingSignal:
    """Per-token norm structure of the embedding matrix. A corpus-tuned model shows a
    small set of anomalously-weighted tokens and large dead regions -> low entropy /
    high dead fraction. Weight-only."""

    name = "embedding"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        try:
            emb = np.asarray(weights.embedding(), dtype=np.float64)
        except KeyError:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no embedding matrix"})

        row_norms = np.linalg.norm(emb, axis=1)
        n = int(row_norms.size)
        if n == 0:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "empty embedding"})

        total = float(row_norms.sum())
        threshold = 1e-6 * (total / n + 1e-12)
        dead = float(np.count_nonzero(row_norms < threshold)) / n

        if total > 0:
            p = row_norms / total
            p = p[p > 0]
            entropy = float(-(p * np.log(p)).sum())
            norm_entropy = entropy / np.log(n) if n > 1 else 1.0
        else:
            norm_entropy = 1.0

        score = float(np.clip(0.5 * (1.0 - norm_entropy) + 0.5 * dead, 0.0, 1.0))
        confidence = float(np.clip(n / 512.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "vocab": n,
            "norm_entropy": norm_entropy,
            "dead_fraction": dead,
        }
        return SignalResult(self.name, score, confidence, evidence)
