import packer.engine.detect.signals  # noqa: F401  (import to trigger self-registration)
from packer.engine.common.registries import SIGNAL_REGISTRY


def test_all_five_signals_registered():
    assert set(SIGNAL_REGISTRY.names()) >= {
        "spectral",
        "weight_norm",
        "embedding",
        "rank",
        "metadata",
    }
