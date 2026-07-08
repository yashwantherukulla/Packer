import numpy as np

from packer.engine.detect.signals.weight_norm import WeightNormSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(mats: dict[str, np.ndarray]) -> LoadedModel:
    return LoadedModel(tensors=mats, config={}, source="t", format="safetensors")


def test_weight_norm_higher_when_one_layer_inflated():
    base = {
        f"model.layers.{i}.mlp.up_proj.weight": np.ones((8, 8), dtype=np.float32) for i in range(4)
    }
    inflated = dict(base)
    inflated["model.layers.0.mlp.up_proj.weight"] = np.ones((8, 8), dtype=np.float32) * 20.0

    sig = WeightNormSignal()
    lo = sig.analyze(WeightAccessor(_model(base)))
    hi = sig.analyze(WeightAccessor(_model(inflated)))

    assert 0.0 <= lo.score <= 1.0
    assert hi.score > lo.score
    assert float(hi.evidence["inflation_ratio"]) > 1.0
