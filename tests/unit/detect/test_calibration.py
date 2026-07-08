from packer.engine.detect.calibration import Calibrator, evaluate
from packer.engine.detect.signals.base import SignalResult


def _rows():
    # `spectral` separates the classes cleanly; `metadata` is pure noise (0.5 both).
    pos = [[SignalResult("spectral", 0.9, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    pos += [[SignalResult("spectral", 0.85, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    neg = [[SignalResult("spectral", 0.1, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    neg += [[SignalResult("spectral", 0.15, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    return [(s, True) for s in pos] + [(s, False) for s in neg]


def test_fit_upweights_the_separating_signal():
    params = Calibrator().fit(_rows())
    assert params.weights["spectral"] > params.weights["metadata"]
    assert params.unlikely_threshold < params.likely_threshold


def test_evaluate_separates_memorized_from_control():
    rows = _rows()
    params = Calibrator().fit(rows)
    metrics = evaluate(rows, params)
    assert metrics.n == 4
    assert metrics.accuracy == 1.0
    assert metrics.separation > 0.0
