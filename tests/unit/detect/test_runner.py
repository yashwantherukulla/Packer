from pathlib import Path

import numpy as np
from safetensors.numpy import save_file

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.config_schema import DetectCfg
from packer.engine.common.types import ModelRef
from packer.engine.detect.calibration import CalibrationStore
from packer.engine.detect.runner import Detector
from packer.engine.models.loader import HFModelLoader


def _write_model(tmp_path: Path) -> Path:
    rng = np.random.default_rng(0)
    tensors = {
        "model.embed_tokens.weight": rng.standard_normal((256, 32)).astype(np.float32),
        "lm_head.weight": rng.standard_normal((256, 32)).astype(np.float32),
        "model.layers.0.mlp.up_proj.weight": rng.standard_normal((64, 32)).astype(np.float32),
        "model.layers.0.self_attn.q_proj.weight": rng.standard_normal((32, 32)).astype(np.float32),
    }
    p = tmp_path / "m.safetensors"
    save_file(tensors, str(p))
    return p


def test_detect_returns_detect_report(tmp_path: Path):
    model_path = _write_model(tmp_path)
    ports = EnginePorts(loader=HFModelLoader())
    cfg = DetectCfg()
    report = Detector(CalibrationStore(tmp_path)).detect(
        ModelRef(kind="path", value=str(model_path)), cfg, ports
    )

    assert report.kind == "detect"
    assert report.verdict.label in {"MEMORIZED-CODE-LIKELY", "INCONCLUSIVE", "UNLIKELY"}
    assert len(report.sections) == 5  # one per enabled signal
    assert any("signature" in note.lower() for note in report.limitations)


def test_detect_is_deterministic(tmp_path: Path):
    model_path = _write_model(tmp_path)
    ports = EnginePorts(loader=HFModelLoader())
    cfg = DetectCfg()
    det = Detector(CalibrationStore(tmp_path))
    a = det.detect(ModelRef(kind="path", value=str(model_path)), cfg, ports)
    b = det.detect(ModelRef(kind="path", value=str(model_path)), cfg, ports)
    assert a.to_json() == b.to_json()
