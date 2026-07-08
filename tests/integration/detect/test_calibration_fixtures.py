from pathlib import Path

import pytest

from packer.engine.detect.calibration import Calibrator, LabeledModel, evaluate

pytestmark = pytest.mark.integration

_FIXTURES = Path(__file__).resolve().parents[2] / "unit" / "detect" / "fixtures"


def _discover() -> list[LabeledModel]:
    if not _FIXTURES.exists():
        return []
    labeled: list[LabeledModel] = []
    for pak in sorted(_FIXTURES.glob("*memorized*")):
        labeled.append(LabeledModel(ref=str(pak), memorized=True))
    for ctrl in sorted(_FIXTURES.glob("*control*")):
        labeled.append(LabeledModel(ref=str(ctrl), memorized=False))
    return labeled


def test_calibration_on_phase1_fixtures():
    fixtures = _discover()
    if len(fixtures) < 3:
        pytest.skip("Phase-1 memorized/control fixtures not present yet")
    params = Calibrator().calibrate(fixtures)
    from packer.engine.detect.runner import run_signals

    rows = [(run_signals(f.ref), f.memorized) for f in fixtures]
    metrics = evaluate(rows, params)
    assert metrics.separation > 0.0  # the number itself is what the report records
