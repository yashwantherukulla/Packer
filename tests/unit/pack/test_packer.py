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


def test_manifest_records_tokenizer_facts_and_exact_byte_spans(tmp_path: Path, cfg_factory):
    files = _repo(tmp_path / "repo")
    cfg = cfg_factory(
        tokenizer="byte-fixed", vocab_size=257, epochs=0, out_dir=str(tmp_path / "out")
    )
    artifact = Packer().pack(tmp_path / "repo", cfg, EnginePorts())

    from packer.engine.artifacts.pak import PakReader
    from packer.engine.pack.corpus import MarkerCorpusSerializer

    manifest = PakReader().read(Path(artifact)).manifest
    serialized = MarkerCorpusSerializer().serialize(tmp_path / "repo")
    assert manifest.pak_version == "1.1"
    assert manifest.tokenizer is not None
    assert manifest.tokenizer.name == "byte-fixed"
    assert manifest.tokenizer.configured_vocab_size == 257
    assert manifest.tokenizer.actual_vocab_size == 257
    assert manifest.tokenizer.merge_count == 0
    assert manifest.tokenizer.serialized_bytes_per_token == 1.0
    for span in manifest.corpus.file_map:
        assert span.byte_start is not None and span.byte_end is not None
        assert span.byte_start <= span.byte_end
        assert span.token_start == span.byte_start
        assert span.token_end == span.byte_end
        assert serialized.bytes[span.byte_start : span.byte_end] == files[span.path]


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


def test_model_vocab_is_derived_from_actual_bpe_vocab(tmp_path: Path, cfg_factory):
    _repo(tmp_path / "repo")
    cfg = cfg_factory(
        tokenizer="byte-bpe",
        vocab_size=8192,
        epochs=0,
        out_dir=str(tmp_path / "out"),
    )
    artifact = Packer().pack(tmp_path / "repo", cfg, EnginePorts())

    from tokenizers import Tokenizer

    from packer.engine.artifacts.pak import PakReader

    bundle = PakReader().read(Path(artifact))
    tokenizer = Tokenizer.from_str(bundle.tokenizer_bytes.decode("utf-8"))
    actual_vocab = tokenizer.get_vocab_size()

    assert actual_vocab < 8192  # reproduces the configured/actual mismatch
    assert bundle.manifest.model.vocab_size == actual_vocab
    assert bundle.tensors["tok_emb.weight"].shape[0] == actual_vocab
    assert bundle.tensors["head.weight"].shape[0] == actual_vocab
    assert cfg.vocab_size == 8192  # caller-owned config was not mutated


def test_minimum_sequence_guard_rejects_tiny_experiment(tmp_path: Path, cfg_factory):
    _repo(tmp_path / "repo")
    cfg = cfg_factory(
        tokenizer="byte-fixed",
        vocab_size=257,
        min_sequence_tokens=10_000,
        out_dir=str(tmp_path / "out"),
    )

    with pytest.raises(PackError, match="below required minimum"):
        Packer().pack(tmp_path / "repo", cfg, EnginePorts())


def test_bytes_per_token_guard_rejects_collapsed_bpe(tmp_path: Path, cfg_factory):
    _repo(tmp_path / "repo")
    cfg = cfg_factory(
        tokenizer="byte-bpe",
        vocab_size=8192,
        max_serialized_bytes_per_token=2.0,
        out_dir=str(tmp_path / "out"),
    )

    with pytest.raises(PackError, match="too compressed"):
        Packer().pack(tmp_path / "repo", cfg, EnginePorts())
