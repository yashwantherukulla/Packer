import numpy as np

from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model() -> LoadedModel:
    return LoadedModel(
        tensors={
            "model.embed_tokens.weight": np.ones((8, 4), dtype=np.float32),
            "lm_head.weight": np.ones((8, 4), dtype=np.float32),
            "model.layers.0.mlp.up_proj.weight": np.ones((16, 4), dtype=np.float32),
            "model.layers.0.self_attn.q_proj.weight": np.ones((4, 4), dtype=np.float32),
        },
        config={"vocab_size": 8},
        source="test",
        format="safetensors",
    )


def test_accessor_yields_roles():
    acc = WeightAccessor(_model())
    assert acc.embedding().shape == (8, 4)
    assert any("mlp" in n for n, _ in acc.mlp_matrices())
    assert any("attn" in n for n, _ in acc.attention_matrices())


def test_accessor_exposes_no_forward():
    acc = WeightAccessor(_model())
    assert not hasattr(acc, "forward")
    assert not hasattr(acc, "generate")
