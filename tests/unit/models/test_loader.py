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


def test_loads_hf_snapshot_and_merges_shards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    shard1 = repo / "model-00001.safetensors"
    shard2 = repo / "model-00002.safetensors"
    save_file({"w1": np.zeros((2, 2), dtype=np.float32)}, str(shard1))
    save_file({"w2": np.ones((2, 2), dtype=np.float32)}, str(shard2))
    (repo / "config.json").write_text("{}")

    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda repo_id: str(repo))

    m = HFModelLoader().load(ModelRef(kind="hf", value="org/model"))

    assert isinstance(m, LoadedModel)
    assert set(m.tensors) == {"w1", "w2"}
