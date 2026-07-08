from packer.engine.detect.calibration import CalibrationParams, CalibrationStore
from packer.engine.detect.ensemble import Ensemble
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.verdict import LABEL_LIKELY, LABEL_UNLIKELY


def _r(name: str, score: float, conf: float = 1.0) -> SignalResult:
    return SignalResult(name, score, conf, {})


def test_ensemble_monotonic_and_labels():
    calib = CalibrationParams.default()
    strong = Ensemble().score([_r("spectral", 0.9), _r("rank", 0.85)], calib)
    weak = Ensemble().score([_r("spectral", 0.1), _r("rank", 0.05)], calib)
    assert strong.score > weak.score
    assert strong.label == LABEL_LIKELY
    assert weak.label == LABEL_UNLIKELY


def test_low_confidence_signal_does_not_dominate():
    calib = CalibrationParams.default()
    verdict = Ensemble().score([_r("spectral", 0.05, 1.0), _r("metadata", 0.99, 0.0)], calib)
    assert verdict.score < 0.2


def test_calibration_store_roundtrip(tmp_path):
    store = CalibrationStore(tmp_path)
    params = CalibrationParams.default()
    store.save(params)
    loaded = store.load(params.version)
    assert loaded == params
