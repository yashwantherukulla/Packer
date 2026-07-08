from omegaconf import OmegaConf

from packer.engine.common.registries import DECODE_REGISTRY
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.decode import InferenceModel, TeacherForcedGreedy, Unpacker
from packer.engine.pack.residuals import DeltaVarintCodec, ResidualCapturer
from packer.engine.pack.tokenizer import ByteBPETokenizer
from packer.engine.pack.trainer import apply_determinism


def _setup(data: bytes):
    tok = ByteBPETokenizer()
    tok.train(data, vocab_size=320)
    tokens = tok.encode(data)
    cfg = {"vocab_size": 320, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 256}
    apply_determinism(0, True)
    model = TinyDecoderArch().build(OmegaConf.create(cfg))
    inf = InferenceModel(model, tok, tok.bos_id())
    return inf, tokens


def test_registered():
    assert "teacher-forced-greedy" in DECODE_REGISTRY.names()
    assert isinstance(DECODE_REGISTRY.create("teacher-forced-greedy"), TeacherForcedGreedy)


def test_untrained_model_still_byte_exact():
    # No training at all: residuals must fully carry correctness (ADR-006).
    data = b"hello world\nsecond line\n"
    inf, tokens = _setup(data)
    residuals = ResidualCapturer().capture(inf, tokens)
    out = TeacherForcedGreedy().reconstruct(inf, residuals, len(tokens))
    assert out == data


def test_unpacker_from_blob():
    data = b"payload \x00\x01\x02"
    inf, tokens = _setup(data)
    residuals = ResidualCapturer().capture(inf, tokens)
    codec = DeltaVarintCodec()
    blob = codec.encode(residuals)
    unpacker = Unpacker(TeacherForcedGreedy(), codec)
    assert unpacker.reconstruct_blob(inf, blob, len(tokens)) == data


def test_empty_sequence():
    tok = ByteBPETokenizer()
    tok.train(b"x", vocab_size=320)
    model = TinyDecoderArch().build(
        OmegaConf.create(
            {"vocab_size": 320, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 256}
        )
    )
    inf = InferenceModel(model, tok, tok.bos_id())
    assert TeacherForcedGreedy().reconstruct(inf, [], 0) == b""
