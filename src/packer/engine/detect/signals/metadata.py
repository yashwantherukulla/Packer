from __future__ import annotations

import contextlib

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.models.accessor import WeightAccessor

_PAK_MARKERS = ("pak_version", "boundary_scheme", "corpus", "file_map")
_SMALL_VOCAB = 16_384
_TINY_PARAMS = 50_000_000


def _param_proxy(weights: WeightAccessor) -> int:
    total = 0
    for _, m in list(weights.attention_matrices()) + list(weights.mlp_matrices()):
        total += int(np.asarray(m).size)
    with contextlib.suppress(KeyError):
        total += int(np.asarray(weights.embedding()).size)
    return total


@SIGNAL_REGISTRY.register("metadata")
class MetadataSignal:
    """Config/metadata heuristics (ARCHITECTURE §5.3): tiny param count, small vocab
    tuned to a small corpus, and ``.pak``-shaped manifest markers. Metadata-only — a
    weak-but-cheap signal; the ``.pak`` marker is near-certain evidence when present."""

    name = "metadata"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        cfg = weights.config()
        try:
            vocab = int(np.asarray(weights.embedding()).shape[0])
        except KeyError:
            vocab = int(cfg.get("vocab_size", 0) or 0)

        param_proxy = _param_proxy(weights)
        pak = any(k in cfg for k in _PAK_MARKERS)
        small_vocab = 0 < vocab <= _SMALL_VOCAB
        tiny_params = 0 < param_proxy <= _TINY_PARAMS

        votes = [pak, small_vocab, tiny_params]
        score = sum(1 for v in votes if v) / len(votes)
        if pak:
            score = max(score, 0.8)  # a pak-shaped manifest is strong evidence
        confidence = 0.9 if pak else 0.5
        evidence: dict[str, object] = {
            "vocab": vocab,
            "param_proxy": param_proxy,
            "pak_markers": pak,
            "tiny_params": tiny_params,
        }
        return SignalResult(self.name, float(score), float(confidence), evidence)
