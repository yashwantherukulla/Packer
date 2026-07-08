from pathlib import Path

import pytest

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.errors import PackError
from packer.engine.common.progress import RecordingProgress
from packer.engine.pack import residuals as residuals_mod
from packer.engine.pack.packer import Packer
from packer.engine.pack.unpacker import unpack


def _repo(root: Path) -> dict[str, bytes]:
    files = {"main.py": b"def f():\n    return 42\n", "notes/x.txt": b"hello\n\x00\x01"}
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return files


def test_pack_then_unpack_byte_exact(tmp_path: Path, cfg_factory):
    files = _repo(tmp_path / "repo")
    cfg = cfg_factory(epochs=20, out_dir=str(tmp_path / "out"))
    rec = RecordingProgress()
    artifact = Packer().pack(tmp_path / "repo", cfg, EnginePorts(), rec)
    assert Path(artifact).exists()
    assert unpack(Path(artifact)) == files
    assert rec.events and rec.events[-1].pct == 1.0


def test_manifest_records_honest_metrics(tmp_path: Path, cfg_factory):
    _repo(tmp_path / "repo")
    cfg = cfg_factory(epochs=5, out_dir=str(tmp_path / "out"))
    artifact = Packer().pack(tmp_path / "repo", cfg, EnginePorts())
    from packer.engine.artifacts.pak import PakReader

    m = PakReader().read(Path(artifact)).manifest
    assert m.metrics.lossless is True
    assert m.metrics.original_bytes > 0
    assert m.metrics.gzip_bytes > 0
    # from-scratch model is not a competitive compressor (ADR-003)
    assert m.metrics.artifact_bytes > m.metrics.gzip_bytes
    assert m.residuals.codec == "delta-varint-v1"


def test_verification_gate_raises_on_dropped_residuals(tmp_path: Path, cfg_factory, monkeypatch):
    _repo(tmp_path / "repo")
    cfg = cfg_factory(epochs=0, out_dir=str(tmp_path / "out"))  # untrained -> residuals needed
    monkeypatch.setattr(residuals_mod.ResidualCapturer, "capture", lambda self, m, t: [])
    with pytest.raises(PackError):
        Packer().pack(tmp_path / "repo", cfg, EnginePorts())


def test_pack_rejects_oversized_corpus(tmp_path: Path, cfg_factory):
    (tmp_path / "repo").mkdir()
    # High-entropy bytes so byte-BPE can't merge the corpus below context_len
    # (a repetitive corpus like b"a"*5000 compresses to a handful of tokens).
    import hashlib

    h = b"seed"
    chunks = []
    for _ in range(200):
        h = hashlib.sha256(h).digest()
        chunks.append(h)
    (tmp_path / "repo" / "big.bin").write_bytes(b"".join(chunks))  # ~6400 incompressible bytes
    cfg = cfg_factory(epochs=1, context_len=64, out_dir=str(tmp_path / "out"))
    with pytest.raises(PackError):
        Packer().pack(tmp_path / "repo", cfg, EnginePorts())
