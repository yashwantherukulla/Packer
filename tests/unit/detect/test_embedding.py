import numpy as np

from packer.engine.detect.signals.embedding import EmbeddingSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(emb: np.ndarray) -> LoadedModel:
    return LoadedModel(
        tensors={"model.embed_tokens.weight": emb},
        config={},
        source="t",
        format="safetensors",
    )


def test_embedding_flags_concentrated_distribution():
    uniform = np.ones((256, 8), dtype=np.float32)
    concentrated = np.zeros((256, 8), dtype=np.float32)
    concentrated[:4] = 5.0  # a few hot tokens, the rest dead

    sig = EmbeddingSignal()
    lo = sig.analyze(WeightAccessor(_model(uniform)))
    hi = sig.analyze(WeightAccessor(_model(concentrated)))

    assert 0.0 <= lo.score <= 1.0
    assert hi.score > lo.score
    assert float(hi.evidence["dead_fraction"]) > 0.9
