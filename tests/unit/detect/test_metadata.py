import numpy as np

from packer.engine.detect.signals.metadata import MetadataSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def test_metadata_flags_pak_shaped_tiny_model():
    tiny = LoadedModel(
        tensors={"model.embed_tokens.weight": np.ones((4096, 128), dtype=np.float32)},
        config={"pak_version": "1.0", "boundary_scheme": "special-token-v1", "vocab_size": 4096},
        source="x.pak",
        format="safetensors",
    )
    big = LoadedModel(
        tensors={"model.embed_tokens.weight": np.ones((20000, 128), dtype=np.float32)},
        config={"vocab_size": 20000},
        source="hf",
        format="safetensors",
    )

    sig = MetadataSignal()
    hi = sig.analyze(WeightAccessor(tiny))
    lo = sig.analyze(WeightAccessor(big))

    assert hi.score >= 0.8
    assert hi.score > lo.score
    assert bool(hi.evidence["pak_markers"]) is True
