import numpy as np

from packer.engine.detect.signals.rank import RankSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(mats: dict[str, np.ndarray]) -> LoadedModel:
    return LoadedModel(tensors=mats, config={}, source="t", format="safetensors")


def test_rank_higher_for_lowrank_layers():
    rng = np.random.default_rng(0)
    full = {f"model.layers.{i}.mlp.up_proj.weight": rng.standard_normal((32, 32)) for i in range(3)}
    low = {
        f"model.layers.{i}.mlp.up_proj.weight": np.outer(
            rng.standard_normal(32), rng.standard_normal(32)
        )
        for i in range(3)
    }

    sig = RankSignal()
    hi = sig.analyze(WeightAccessor(_model(low)))
    lo = sig.analyze(WeightAccessor(_model(full)))

    assert 0.0 <= lo.score <= 1.0 and 0.0 <= hi.score <= 1.0
    assert hi.score > lo.score
