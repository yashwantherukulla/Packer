from pathlib import Path

import numpy as np
import pytest
from safetensors.numpy import save_file

from packer.engine.common.errors import UnsafeModelError
from packer.engine.common.types import ModelRef
from packer.engine.models.loader import HFModelLoader, LoadedModel


def test_loads_local_safetensors(tmp_path: Path):
    p = tmp_path / "m.safetensors"
    save_file({"w": np.zeros((4, 4), dtype=np.float32)}, str(p))
    m = HFModelLoader().load(ModelRef(kind="path", value=str(p)))
    assert isinstance(m, LoadedModel)
    assert "w" in m.tensors and m.format == "safetensors"


def test_pickle_rejected_by_default(tmp_path: Path):
    p = tmp_path / "m.bin"
    p.write_bytes(b"\x80\x04.")  # pickle-ish
    with pytest.raises(UnsafeModelError):
        HFModelLoader().load(ModelRef(kind="path", value=str(p)))
