from __future__ import annotations

import json

from tokenizers import Tokenizer, decoders, models, trainers

from packer.engine.common.errors import PackError
from packer.engine.common.registries import TOKENIZER_REGISTRY

_BYTE_ALPHABET = [chr(b) for b in range(256)]  # latin-1: total bijection bytes <-> chars
_BOS = "<bos>"


class _HfByteTokenizer:
    """Shared serialization and byte-safe encode/decode behavior.

    Both tokenizer strategies persist as data-only Hugging Face tokenizer JSON.
    That keeps the artifact format uniform while allowing the training policy
    (fixed bytes versus learned BPE merges) to be explicit and reproducible.
    """

    def __init__(self) -> None:
        self._tok: Tokenizer | None = None

    def load(self, blob: bytes) -> None:
        self._tok = Tokenizer.from_str(blob.decode("utf-8"))

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

    def merge_count(self) -> int:
        payload: object = json.loads(self.to_bytes())
        if not isinstance(payload, dict):
            raise PackError("tokenizer JSON root must be an object")
        model = payload.get("model")
        if not isinstance(model, dict):
            raise PackError("tokenizer JSON is missing its model object")
        merges = model.get("merges", [])
        if not isinstance(merges, list):
            raise PackError("tokenizer JSON model.merges must be a list")
        return len(merges)

    def to_bytes(self) -> bytes:
        text: str = self._require().to_str()
        return text.encode("utf-8")

    def _require(self) -> Tokenizer:
        if self._tok is None:
            raise PackError("tokenizer used before train()/load()")
        return self._tok


@TOKENIZER_REGISTRY.register("byte-fixed")
class FixedByteTokenizer(_HfByteTokenizer):
    """Deterministic one-token-per-byte encoding.

    Token 0 is reserved for BOS and byte value ``b`` maps to token ``b + 1``.
    The vocabulary therefore has exactly 257 entries and no learned merges.
    ``vocab_size`` is validated rather than silently ignored so a run cannot
    claim a different tokenizer/model vocabulary than it actually used.
    """

    VOCAB_SIZE = len(_BYTE_ALPHABET) + 1

    def train(self, corpus: bytes, vocab_size: int) -> None:
        del corpus  # fixed vocabulary is corpus-independent by design
        if int(vocab_size) != self.VOCAB_SIZE:
            raise PackError(
                f"byte-fixed requires vocab_size={self.VOCAB_SIZE}, got {vocab_size}",
                context={"tokenizer": "byte-fixed", "required_vocab_size": self.VOCAB_SIZE},
            )
        vocab = {_BOS: 0, **{char: byte + 1 for byte, char in enumerate(_BYTE_ALPHABET)}}
        tok = Tokenizer(models.BPE(vocab=vocab, merges=[], unk_token=None))
        tok.decoder = decoders.Fuse()
        self._tok = tok

    @classmethod
    def from_bytes(cls, blob: bytes) -> FixedByteTokenizer:
        obj = cls()
        obj.load(blob)
        return obj


@TOKENIZER_REGISTRY.register("byte-bpe")
class ByteBPETokenizer(_HfByteTokenizer):
    """Byte-level BPE with guaranteed full-byte coverage.

    Bytes are mapped to text via latin-1 (a total bijection over 0..255); the BPE
    model is trained with the 256 single-byte symbols as its initial alphabet, so
    ``decode(encode(x)) == x`` for *any* bytes ``x`` regardless of the corpus. No
    pre-tokenizer is installed, so BPE learns merges across the whole stream — the
    behaviour an overfit memorizer wants.
    """

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

    @classmethod
    def from_bytes(cls, blob: bytes) -> ByteBPETokenizer:
        obj = cls()
        obj.load(blob)
        return obj
