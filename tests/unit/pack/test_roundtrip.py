from pathlib import Path

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from omegaconf import DictConfig, OmegaConf

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.progress import null_progress
from packer.engine.pack.packer import Packer
from packer.engine.pack.unpacker import unpack


def _tiny_cfg(tmp_out: Path, **over) -> DictConfig:
    base = {
        "arch": "tiny-decoder",
        "tokenizer": "byte-bpe",
        "decode": "teacher-forced-greedy",
        "codec": "delta-varint-v1",
        "n_layers": 1,
        "d_model": 16,
        "n_heads": 2,
        "vocab_size": 320,
        "context_len": 256,
        "epochs": 1,
        "lr": 5e-3,
        "batch_size": 1,
        "weight_decay": 0.0,
        "device": "cpu",
        "deterministic": True,
        "seed": 0,
        "bos_token_id": 0,
        "out_dir": str(tmp_out),
    }
    base.update(over)
    cfg = OmegaConf.create(base)
    assert isinstance(cfg, DictConfig)
    return cfg


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(data=st.binary(min_size=0, max_size=200))
def test_pack_unpack_arbitrary_bytes(tmp_path_factory, data):
    repo = tmp_path_factory.mktemp("repo")
    (repo / "blob.bin").write_bytes(data)
    out = tmp_path_factory.mktemp("out")
    artifact = Packer().pack(repo, _tiny_cfg(out, epochs=1), EnginePorts(), null_progress)
    assert unpack(Path(artifact))["blob.bin"] == data


def test_roundtrip_holds_with_epochs_1(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    (repo / "a.py").write_bytes(b"print('memorize me')\n")
    (repo / "sub" / "b.bin").write_bytes(bytes(range(64)))
    files = {"a.py": b"print('memorize me')\n", "sub/b.bin": bytes(range(64))}
    artifact = Packer().pack(repo, _tiny_cfg(tmp_path / "out", epochs=1), EnginePorts())
    assert unpack(Path(artifact)) == files


def test_same_seed_yields_identical_artifact_bytes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "c.py").write_bytes(b"x = [1, 2, 3]\n")
    a = Packer().pack(repo, _tiny_cfg(tmp_path / "o1", epochs=15, seed=7), EnginePorts())
    b = Packer().pack(repo, _tiny_cfg(tmp_path / "o2", epochs=15, seed=7), EnginePorts())
    # weights, tokenizer, and residuals are the correctness-relevant bytes
    # (the manifest carries a wall-clock timestamp).
    assert (Path(a) / "model.safetensors").read_bytes() == (
        Path(b) / "model.safetensors"
    ).read_bytes()
    assert (Path(a) / "residuals.bin").read_bytes() == (Path(b) / "residuals.bin").read_bytes()
    assert (Path(a) / "tokenizer.json").read_bytes() == (Path(b) / "tokenizer.json").read_bytes()
