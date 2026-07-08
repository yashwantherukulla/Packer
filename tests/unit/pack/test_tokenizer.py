import pytest

from packer.engine.common.errors import PackError
from packer.engine.common.registries import TOKENIZER_REGISTRY
from packer.engine.pack.tokenizer import ByteBPETokenizer


@pytest.fixture
def trained() -> ByteBPETokenizer:
    tok = ByteBPETokenizer()
    tok.train(b"def add(a, b):\n    return a + b\n" * 4, vocab_size=400)
    return tok


def test_registered_in_registry():
    assert "byte-bpe" in TOKENIZER_REGISTRY.names()
    assert isinstance(TOKENIZER_REGISTRY.create("byte-bpe"), ByteBPETokenizer)


def test_lossless_on_training_text(trained: ByteBPETokenizer):
    data = b"def add(a, b):\n    return a + b\n"
    assert trained.decode(trained.encode(data)) == data


def test_lossless_on_arbitrary_binary(trained: ByteBPETokenizer):
    blob = bytes(range(256)) + b"\x00\xff\x80mixed\n"
    assert trained.decode(trained.encode(blob)) == blob


def test_bos_and_vocab(trained: ByteBPETokenizer):
    assert trained.vocab_size() >= 256
    assert isinstance(trained.bos_id(), int)


def test_serialization_roundtrip(trained: ByteBPETokenizer):
    clone = ByteBPETokenizer.from_bytes(trained.to_bytes())
    data = b"return a + b\n"
    assert clone.encode(data) == trained.encode(data)
    assert clone.bos_id() == trained.bos_id()


def test_encode_before_train_raises():
    with pytest.raises(PackError):
        ByteBPETokenizer().encode(b"x")
