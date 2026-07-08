import numpy as np

from packer.engine.detect.signals.spectral import SpectralSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(mats: dict[str, np.ndarray]) -> LoadedModel:
    return LoadedModel(tensors=mats, config={}, source="t", format="safetensors")


def test_spectral_flags_rank1_over_random():
    rng = np.random.default_rng(0)
    rand = {f"model.layers.{i}.mlp.up_proj.weight": rng.standard_normal((64, 48)) for i in range(3)}
    spk: dict[str, np.ndarray] = {}
    for i in range(3):
        m = rng.standard_normal((64, 48))
        u = rng.standard_normal(64)
        u /= np.linalg.norm(u)
        v = rng.standard_normal(48)
        v /= np.linalg.norm(v)
        spk[f"model.layers.{i}.mlp.up_proj.weight"] = m + 60.0 * np.outer(u, v)

    sig = SpectralSignal()
    lo = sig.analyze(WeightAccessor(_model(rand)))
    hi = sig.analyze(WeightAccessor(_model(spk)))

    assert 0.0 <= lo.score <= 1.0 and 0.0 <= hi.score <= 1.0
    assert 0.0 <= hi.confidence <= 1.0
    assert hi.score > lo.score
    assert float(hi.evidence["outlier_rate"]) >= 1.0


def test_spectral_empty_is_low_confidence():
    sig = SpectralSignal()
    r = sig.analyze(WeightAccessor(_model({})))
    assert r.score == 0.0 and r.confidence == 0.0
