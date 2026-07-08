import numpy as np
import pytest

from packer.engine.common.config_schema import DetectCfg
from packer.engine.common.types import ModelRef
from packer.engine.detect.calibration import CalibrationStore
from packer.engine.detect.runner import Detector


class _LiveModel:
    """Stands in for a torch-backed model: exposes tensors (what signals may read) plus
    forward/generate that EXPLODE if inference is ever attempted."""

    def __init__(self) -> None:
        rng = np.random.default_rng(0)
        self.tensors = {
            "model.embed_tokens.weight": rng.standard_normal((128, 16)).astype(np.float32),
            "model.layers.0.mlp.up_proj.weight": rng.standard_normal((32, 16)).astype(np.float32),
            "model.layers.0.self_attn.q_proj.weight": rng.standard_normal((16, 16)).astype(
                np.float32
            ),
        }
        self.config: dict[str, object] = {"vocab_size": 128}
        self.source = "fake"
        self.format = "safetensors"

    def forward(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("detect ran inference (forward) — no-inference wall breached!")

    def generate(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("detect ran inference (generate) — no-inference wall breached!")


class _FakeLoader:
    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> _LiveModel:
        return _LiveModel()


class _Ports:
    def __init__(self) -> None:
        self.loader = _FakeLoader()


def test_detect_completes_without_running_inference(tmp_path):
    report = Detector(CalibrationStore(tmp_path)).detect(
        ModelRef(kind="path", value="unused"), DetectCfg(), _Ports()
    )
    # Reaching here means forward/generate were never called (they would have raised).
    assert report.kind == "detect"
    assert report.verdict.label in {"MEMORIZED-CODE-LIKELY", "INCONCLUSIVE", "UNLIKELY"}
    assert len(report.sections) == 5


def test_calling_forward_would_raise():
    # Sanity: the trap is armed — a direct forward call blows up as designed.
    with pytest.raises(AssertionError):
        _LiveModel().forward()
