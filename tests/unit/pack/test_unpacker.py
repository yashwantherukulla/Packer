import tempfile
from pathlib import Path

from omegaconf import OmegaConf

from packer.engine.artifacts.manifest import Manifest
from packer.engine.artifacts.pak import PakBundle, PakWriter
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.corpus import MarkerCorpusSerializer
from packer.engine.pack.decode import InferenceModel, TeacherForcedGreedy, Unpacker
from packer.engine.pack.residuals import DeltaVarintCodec, ResidualCapturer
from packer.engine.pack.tokenizer import ByteBPETokenizer
from packer.engine.pack.trainer import apply_determinism
from packer.engine.pack.unpacker import unpack, unpack_bundle


def _hand_built_bundle() -> tuple[PakBundle, dict[str, bytes]]:
    files = {"a.py": b"x = 1\n", "d/b.bin": b"\x00\x01\x02\x03"}

    # Frame the files exactly as the serializer would (single-source-of-truth):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
        corpus = MarkerCorpusSerializer().serialize(root)

    tok = ByteBPETokenizer()
    tok.train(corpus.bytes, vocab_size=320)
    tokens = tok.encode(corpus.bytes)

    cfg = OmegaConf.create(
        {"vocab_size": 320, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 256}
    )
    apply_determinism(0, True)
    model = TinyDecoderArch().build(cfg)
    inf = InferenceModel(model, tok, tok.bos_id())
    residuals = ResidualCapturer().capture(inf, tokens)
    codec = DeltaVarintCodec()
    blob = codec.encode(residuals)
    assert (
        Unpacker(TeacherForcedGreedy(), codec).reconstruct(inf, residuals, len(tokens))
        == corpus.bytes
    )

    tensors = {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
    manifest = Manifest.model_validate(
        {
            "pak_version": "1.0",
            "created_utc": "2026-07-07T00:00:00Z",
            "model": {
                "arch": "tiny-decoder",
                "param_count": sum(int(v.size) for v in tensors.values()),
                "n_layers": 1,
                "d_model": 32,
                "n_heads": 2,
                "vocab_size": 320,
                "context_len": 256,
            },
            "corpus": {
                "n_files": corpus.n_files,
                "n_bytes": corpus.original_bytes,
                "n_tokens": len(tokens),
                "sha256": "x",
                "file_map": [],
                "boundary_scheme": "length-prefixed-v1",
            },
            "decode": {
                "strategy": "teacher-forced-greedy",
                "length_tokens": len(tokens),
                "bos_token_id": tok.bos_id(),
            },
            "residuals": {"count": len(residuals), "ratio": 0.0, "codec": "delta-varint-v1"},
            "metrics": {
                "model_bytes": 1,
                "artifact_bytes": 1,
                "original_bytes": corpus.original_bytes,
                "gzip_bytes": 1,
                "lossless": True,
            },
        }
    )
    bundle = PakBundle(
        tensors=tensors, tokenizer_bytes=tok.to_bytes(), manifest=manifest, residual_blob=blob
    )
    return bundle, files


def test_unpack_bundle_recovers_files():
    bundle, files = _hand_built_bundle()
    assert unpack_bundle(bundle) == files


def test_unpack_from_disk(tmp_path: Path):
    bundle, files = _hand_built_bundle()
    out = tmp_path / "x.pak"
    PakWriter().write(out, bundle)
    assert unpack(out) == files
