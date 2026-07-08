from __future__ import annotations

from tokenizers import Tokenizer, decoders, models, trainers

from packer.engine.common.errors import PackError
from packer.engine.common.registries import TOKENIZER_REGISTRY

_BYTE_ALPHABET = [chr(b) for b in range(256)]  # latin-1: total bijection bytes <-> chars
_BOS = "<bos>"


@TOKENIZER_REGISTRY.register("byte-bpe")
class ByteBPETokenizer:
    """Byte-level BPE with guaranteed full-byte coverage.

    Bytes are mapped to text via latin-1 (a total bijection over 0..255); the BPE
    model is trained with the 256 single-byte symbols as its initial alphabet, so
    ``decode(encode(x)) == x`` for *any* bytes ``x`` regardless of the corpus. No
    pre-tokenizer is installed, so BPE learns merges across the whole stream — the
    behaviour an overfit memorizer wants.
    """

    def __init__(self) -> None:
        self._tok: Tokenizer | None = None

    def train(self, corpus: bytes, vocab_size: int) -> None:
        tok = Tokenizer(models.BPE(unk_token=None))
        tok.decoder = decoders.Fuse()  # concatenate token pieces verbatim
        trainer = trainers.BpeTrainer(  # type: ignore[no-untyped-call]  # untyped in tokenizers stubs
            vocab_size=max(int(vocab_size), len(_BYTE_ALPHABET) + 1),
            initial_alphabet=_BYTE_ALPHABET,
            special_tokens=[_BOS],
            show_progress=False,
        )
        tok.train_from_iterator([corpus.decode("latin-1")], trainer=trainer)
        self._tok = tok

    def encode(self, data: bytes) -> list[int]:
        ids = self._require().encode(data.decode("latin-1"), add_special_tokens=False).ids
        return list(ids)

    def decode(self, tokens: list[int]) -> bytes:
        text: str = self._require().decode(tokens, skip_special_tokens=False)
        return text.encode("latin-1")

    def vocab_size(self) -> int:
        return int(self._require().get_vocab_size())

    def bos_id(self) -> int:
        tid = self._require().token_to_id(_BOS)
        if tid is None:
            raise PackError("tokenizer is missing the <bos> special token")
        return int(tid)

    def to_bytes(self) -> bytes:
        text: str = self._require().to_str()
        return text.encode("utf-8")

    @classmethod
    def from_bytes(cls, blob: bytes) -> ByteBPETokenizer:
        obj = cls()
        obj._tok = Tokenizer.from_str(blob.decode("utf-8"))
        return obj

    def _require(self) -> Tokenizer:
        if self._tok is None:
            raise PackError("tokenizer used before train()/from_bytes()")
        return self._tok
