import json

import pytest

from packer.engine.common.errors import PackError
from packer.engine.common.registries import TOKENIZER_REGISTRY
from packer.engine.pack.tokenizer import ByteBPETokenizer, FixedByteTokenizer


@pytest.fixture
def trained() -> ByteBPETokenizer:
    tok = ByteBPETokenizer()
    tok.train(b"def add(a, b):\n    return a + b\n" * 4, vocab_size=400)
    return tok


def test_registered_in_registry():
    assert "byte-fixed" in TOKENIZER_REGISTRY.names()
    assert "byte-bpe" in TOKENIZER_REGISTRY.names()
    assert isinstance(TOKENIZER_REGISTRY.create("byte-fixed"), FixedByteTokenizer)
    assert isinstance(TOKENIZER_REGISTRY.create("byte-bpe"), ByteBPETokenizer)


def test_fixed_byte_maps_every_byte_to_one_stable_token():
    tok = FixedByteTokenizer()
    data = bytes(range(256)) + b"\x00\xffmixed\n"
    tok.train(data, vocab_size=257)

    ids = tok.encode(data)

    assert len(ids) == len(data)
    assert ids[:256] == list(range(1, 257))
    assert tok.decode(ids) == data
    assert tok.bos_id() == 0
    assert tok.vocab_size() == 257
    assert tok.merge_count() == 0


def test_fixed_byte_serialization_is_deterministic_and_loadable():
    first = FixedByteTokenizer()
    second = FixedByteTokenizer()
    first.train(b"first corpus", vocab_size=257)
    second.train(b"completely different corpus", vocab_size=257)

    assert first.to_bytes() == second.to_bytes()
    clone = FixedByteTokenizer.from_bytes(first.to_bytes())
    assert clone.encode(b"\x00abc\xff") == [1, 98, 99, 100, 256]
    assert clone.decode([1, 98, 99, 100, 256]) == b"\x00abc\xff"


def test_fixed_byte_load_rejects_permuted_byte_ids():
    tok = FixedByteTokenizer()
    tok.train(b"ignored", vocab_size=257)
    payload = json.loads(tok.to_bytes())
    vocab = payload["model"]["vocab"]
    vocab["X"], vocab["Y"] = vocab["Y"], vocab["X"]

    with pytest.raises(PackError, match="canonical byte mapping"):
        FixedByteTokenizer.from_bytes(json.dumps(payload).encode("utf-8"))


def test_fixed_byte_rejects_misleading_vocab_size():
    with pytest.raises(PackError, match="requires vocab_size=257"):
        FixedByteTokenizer().train(b"x", vocab_size=320)


def test_bpe_can_collapse_tiny_corpus_but_fixed_byte_cannot():
    data = b"small repeated repository payload\n"
    bpe = ByteBPETokenizer()
    bpe.train(data, vocab_size=1024)
    fixed = FixedByteTokenizer()
    fixed.train(data, vocab_size=257)

    assert len(bpe.encode(data)) == 1
    assert len(fixed.encode(data)) == len(data)


def test_lossless_on_training_text(trained: ByteBPETokenizer):
    data = b"def add(a, b):\n    return a + b\n"
    assert trained.decode(trained.encode(data)) == data


def test_lossless_on_arbitrary_binary(trained: ByteBPETokenizer):
    blob = bytes(range(256)) + b"\x00\xff\x80mixed\n"
    assert trained.decode(trained.encode(blob)) == blob


def test_bos_and_vocab(trained: ByteBPETokenizer):
    assert trained.vocab_size() >= 256
    assert isinstance(trained.bos_id(), int)
    assert trained.merge_count() > 0


def test_serialization_roundtrip(trained: ByteBPETokenizer):
    clone = ByteBPETokenizer.from_bytes(trained.to_bytes())
    data = b"return a + b\n"
    assert clone.encode(data) == trained.encode(data)
    assert clone.bos_id() == trained.bos_id()


def test_encode_before_train_raises():
    with pytest.raises(PackError):
        ByteBPETokenizer().encode(b"x")
