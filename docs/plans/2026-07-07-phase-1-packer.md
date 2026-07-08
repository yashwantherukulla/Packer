# Phase 1 — Packer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a small repository into a losslessly-reconstructable `.pak` by overfitting a from-scratch tiny transformer decoder, with a residual mechanism that guarantees byte-exact round-trips independent of training convergence.

**Architecture:** Phase 1 builds the `engine/pack/` subsystem (SYSTEM-DESIGN §5.3) on top of the Phase 0 kernel — it imports only `engine.common`, `engine.models`, and `engine.artifacts` (the Dependency Rule). Every plugin (tokenizer, architecture, residual codec, decode strategy) self-registers in its Phase 0 `Registry`, so the `Packer` orchestrator names none of them directly. The `Unpacker` decode path and the `TeacherForcedGreedy` strategy are written here once and re-used verbatim by Phase 3's exact extractor.

**Tech Stack:** Python 3.10.x, uv, PyTorch (from-scratch decoder + overfit loop), HF `tokenizers` (byte-level BPE), safetensors, numpy, Hydra + OmegaConf, pydantic v2 (manifest), Hypothesis (property-based round-trip), ruff, mypy (strict), pytest, import-linter.

## Global Constraints

*Every task's requirements implicitly include this section. Values copied verbatim from the specs/ADRs.*

- **Python 3.10.x only.** `requires-python = ">=3.10,<3.11"`; `.python-version` = `3.10`. No 3.11+ syntax (`tomllib`, `except*`, `Self`, `type` statement). `match`, `X | Y` unions, PEP 585 generics are fine.
- **uv for everything.** Add deps with `uv add` / `uv add --dev`; never `pip install`; commit `uv.lock`. Run via `uv run`.
- **Quality on commit.** ruff (lint + format), mypy strict, import-linter run via pre-commit and CI.
- **Hydra owns all configuration.** Pydantic is for API wire schemas / manifest validation only.
- **safetensors-first.** Loading pickle/`.bin` requires an explicit `allow_pickle=True` opt-in and raises `UnsafeModelError` otherwise.
- **Value objects cross module boundaries; bare `dict`s do not** (except opaque `evidence`/`context`/`config` payloads).
- **The Dependency Rule** (SYSTEM-DESIGN §1/§4): `engine.common` imports nothing else in `packer`; `engine.pack` imports only `engine.common`, `engine.models`, `engine.artifacts`; `engine.*` never imports `api`/`workers`/adapters; enforced by import-linter.
- **Conventional Commits**, one logical change per commit.
- **Windows-native is the primary dev target;** use `pathlib`, never hardcode POSIX paths (`Path.rglob`, `PurePosixPath` for stored relative paths).
- **(Phase 1) Byte-exact lossless round-trip is a correctness gate.** `pack → unpack` MUST be byte-identical, asserted in CI (Hypothesis over arbitrary bytes) and enforced in-process by `Packer` before any artifact is written (fail-fast → `PackError`).
- **(Phase 1) Honest size metrics.** Every manifest records `original_bytes`, `gzip_bytes`, `model_bytes`, `artifact_bytes`, `compression_ratio_vs_original`, `lossless=true` (ADR-003). Packer never claims to beat gzip.
- **(Phase 1) Residuals guarantee losslessness independent of training convergence** (ADR-006). Correctness holds with `epochs=1` (or even an untrained model); model quality affects only artifact size.
- **(Phase 1) Determinism.** Fixed `seed` + `deterministic=true` (torch deterministic flags, seeded before model build and before training) ⇒ identical weights + residuals across runs, so CI byte-exact assertions are stable.

## File Structure

```
conf/
  engine/pack/tiny_decoder.yaml         # MODIFY: add plugin names + Phase-1 fields
src/packer/engine/common/
  config_schema.py                      # MODIFY: extend TinyDecoderCfg with Phase-1 fields
src/packer/engine/pack/
  __init__.py                           # imports plugin submodules (self-registration) + Packer/Unpacker/unpack
  varint.py                             # LEB128 uvarint helpers (shared by corpus + codec)
  corpus.py                             # MarkerCorpusSerializer + SerializedCorpus
  tokenizer.py                          # ByteBPETokenizer  @TOKENIZER_REGISTRY.register("byte-bpe")
  arch.py                               # TinyDecoder (nn.Module) + TinyDecoderArch @ARCH_REGISTRY.register("tiny-decoder")
  trainer.py                            # OverfitTrainer + determinism/device helpers
  residuals.py                          # ResidualCapturer + DeltaVarintCodec @CODEC_REGISTRY.register("delta-varint-v1")
  decode.py                             # InferenceModel + TeacherForcedGreedy @DECODE_REGISTRY.register("teacher-forced-greedy")
  unpacker.py                           # Unpacker + unpack(pak_path) + unpack_bundle(bundle)
  packer.py                             # Packer.pack(root, cfg, ports, progress) -> str  + manifest/metrics builders
scripts/
  make_fixtures.py                      # generate >=3 memorized .pak + >=2 controls into a target dir
tests/unit/pack/
  conftest.py                           # cfg_factory fixture (tiny deterministic pack cfg)
  test_varint.py
  test_corpus.py
  test_tokenizer.py
  test_arch.py
  test_trainer.py
  test_residuals.py
  test_decode.py
  test_unpacker.py
  test_packer.py
  test_roundtrip.py                     # Hypothesis arbitrary-bytes + epochs=1 + determinism gates
  test_fixtures.py
```

---

### Task 1: Runtime deps (torch, tokenizers) + pack package scaffold + varint util

**Files:**
- Modify: `pyproject.toml` (via `uv add`)
- Create: `src/packer/engine/pack/__init__.py`, `src/packer/engine/pack/varint.py`
- Test: `tests/unit/pack/test_varint.py`

**Interfaces:**
- Consumes: nothing new (Phase 0 kernel already importable).
- Produces: `packer.engine.pack` importable; `_write_uvarint(out: bytearray, n: int) -> None` and `_read_uvarint(data: bytes, i: int) -> tuple[int, int]` (LEB128, non-negative), shared by `corpus` and `residuals`.

- [ ] **Step 1: Add runtime deps**

Run: `uv add torch tokenizers`
Expected: `torch>=2.2` and `tokenizers>=0.19` land in `[project.dependencies]`; `uv.lock` updates. (numpy/safetensors/hydra/pydantic already present from Phase 0.)

- [ ] **Step 2: Write the failing test**

`tests/unit/pack/test_varint.py`:
```python
import pytest

from packer.engine.pack.varint import _read_uvarint, _write_uvarint


def test_uvarint_roundtrip_single():
    out = bytearray()
    _write_uvarint(out, 300)
    value, offset = _read_uvarint(bytes(out), 0)
    assert value == 300
    assert offset == len(out)


def test_uvarint_stream_of_values():
    out = bytearray()
    for n in (0, 1, 127, 128, 16384, 1_000_000):
        _write_uvarint(out, n)
    data = bytes(out)
    i = 0
    got = []
    for _ in range(6):
        v, i = _read_uvarint(data, i)
        got.append(v)
    assert got == [0, 1, 127, 128, 16384, 1_000_000]
    assert i == len(data)


def test_negative_rejected():
    with pytest.raises(ValueError):
        _write_uvarint(bytearray(), -1)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_varint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packer.engine.pack'`.

- [ ] **Step 4: Implement**

`src/packer/engine/pack/__init__.py` (empty for now; plugin-registration imports are appended as modules land):
```python
```

`src/packer/engine/pack/varint.py`:
```python
from __future__ import annotations


def _write_uvarint(out: bytearray, n: int) -> None:
    """Append an unsigned LEB128 varint. Raises on negative input."""
    if n < 0:
        raise ValueError(f"uvarint requires a non-negative int, got {n}")
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return


def _read_uvarint(data: bytes, i: int) -> tuple[int, int]:
    """Read an unsigned LEB128 varint from ``data`` starting at ``i``.

    Returns ``(value, next_index)``.
    """
    result = 0
    shift = 0
    while True:
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, i
        shift += 7
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_varint.py -v && uv run lint-imports`
Expected: PASS; import-linter reports all contracts kept (pack imports only stdlib so far).

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml uv.lock src/packer/engine/pack/__init__.py src/packer/engine/pack/varint.py tests/unit/pack/test_varint.py
git commit -m "feat(pack): scaffold pack package, add torch+tokenizers, add varint util"
```

---

### Task 2: Pack config extension (Phase-1 fields)

**Files:**
- Modify: `src/packer/engine/common/config_schema.py` (extend `TinyDecoderCfg`; register unchanged)
- Modify: `conf/engine/pack/tiny_decoder.yaml`
- Test: `tests/unit/common/test_config_pack.py`

**Interfaces:**
- Consumes: `TinyDecoderCfg`, `compose_config` (Phase 0 `config_schema`).
- Produces: `TinyDecoderCfg` gains `arch: str="tiny-decoder"`, `tokenizer: str="byte-bpe"`, `decode: str="teacher-forced-greedy"`, `codec: str="delta-varint-v1"`, `weight_decay: float=0.0`, `seed: int=0`, `bos_token_id: int=0`, `out_dir: str="./outputs"` — all defaulted, backward-compatible. `compose_config()` exposes them under `cfg.engine.pack`.

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_config_pack.py`:
```python
from packer.engine.common.config_schema import TinyDecoderCfg, compose_config


def test_pack_plugin_names_default():
    c = TinyDecoderCfg()
    assert c.arch == "tiny-decoder"
    assert c.tokenizer == "byte-bpe"
    assert c.decode == "teacher-forced-greedy"
    assert c.codec == "delta-varint-v1"
    assert c.weight_decay == 0.0
    assert c.seed == 0


def test_pack_fields_compose_and_override():
    cfg = compose_config(overrides=["engine/pack.seed=7", "engine/pack.codec=delta-varint-v1"])
    assert cfg.engine.pack.seed == 7
    assert cfg.engine.pack.arch == "tiny-decoder"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_config_pack.py -v`
Expected: FAIL — `AttributeError`/`ConfigAttributeError` (new fields absent).

- [ ] **Step 3: Implement** — extend the existing `TinyDecoderCfg` dataclass in `src/packer/engine/common/config_schema.py` (append the new defaulted fields; leave `register_configs`/`compose_config` untouched):
```python
@dataclass
class TinyDecoderCfg:
    n_layers: int = 6
    d_model: int = 256
    n_heads: int = 4
    vocab_size: int = 8192
    context_len: int = 1024
    epochs: int = 200
    lr: float = 3e-4
    batch_size: int = 8
    device: str = "auto"          # auto | cpu | cuda
    deterministic: bool = True
    # --- Phase 1 additions (plugin selection + training/persistence knobs) ---
    arch: str = "tiny-decoder"
    tokenizer: str = "byte-bpe"
    decode: str = "teacher-forced-greedy"
    codec: str = "delta-varint-v1"
    weight_decay: float = 0.0
    seed: int = 0
    bos_token_id: int = 0
    out_dir: str = "./outputs"
```

`conf/engine/pack/tiny_decoder.yaml` — set the small, explicit values used by CPU packing (keep the file backed by the structured config):
```yaml
# Values below override the TinyDecoderCfg structured-config defaults.
arch: tiny-decoder
tokenizer: byte-bpe
decode: teacher-forced-greedy
codec: delta-varint-v1
seed: 0
weight_decay: 0.0
bos_token_id: 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_config_pack.py -v && uv run mypy src`
Expected: PASS + mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/common/config_schema.py conf/engine/pack/tiny_decoder.yaml tests/unit/common/test_config_pack.py
git commit -m "feat(pack): extend TinyDecoderCfg with plugin-name + training fields"
```

---

### Task 3: MarkerCorpusSerializer + SerializedCorpus

**Files:**
- Create: `src/packer/engine/pack/corpus.py`
- Test: `tests/unit/pack/test_corpus.py`

**Interfaces:**
- Consumes: `PackError` (Phase 0 `common.errors`); `_write_uvarint`/`_read_uvarint` (Task 1).
- Produces (Phase 3 `ExactExtractor` depends on these names, SYSTEM-DESIGN §5.3):
  - `SerializedCorpus` frozen dataclass `{bytes: bytes, file_map: list[tuple[str, int, int]]}` with `.n_files` and `.original_bytes` properties. `file_map` entries are `(posix_relpath, content_start, content_end)` into `bytes`.
  - `MarkerCorpusSerializer.serialize(root: Path) -> SerializedCorpus` — deterministic (sorted paths), self-delimiting length-prefixed frames, fully reversible.
  - `MarkerCorpusSerializer.deserialize(data: bytes, file_map: list | None = None) -> dict[str, bytes]` — parses frames from `data` (file_map optional/ignored for reconstruction), inverse of `serialize`.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_corpus.py`:
```python
from pathlib import Path

import pytest

from packer.engine.common.errors import PackError
from packer.engine.pack.corpus import MarkerCorpusSerializer, SerializedCorpus


def _build_repo(root: Path) -> dict[str, bytes]:
    files = {
        "a.py": b"print('hi')\n",
        "sub/b.txt": b"",                       # empty file
        "sub/deep/c.bin": bytes(range(256)),    # binary, all byte values
        "weird name (1).md": "café ☃\n".encode("utf-8"),
    }
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return files


def test_serialize_is_deterministic(tmp_path: Path):
    files = _build_repo(tmp_path)
    a = MarkerCorpusSerializer().serialize(tmp_path)
    b = MarkerCorpusSerializer().serialize(tmp_path)
    assert isinstance(a, SerializedCorpus)
    assert a.bytes == b.bytes
    assert a.n_files == len(files)
    assert a.original_bytes == sum(len(c) for c in files.values())


def test_roundtrip_recovers_every_file(tmp_path: Path):
    files = _build_repo(tmp_path)
    corpus = MarkerCorpusSerializer().serialize(tmp_path)
    restored = MarkerCorpusSerializer().deserialize(corpus.bytes)
    assert restored == files


def test_file_map_spans_reference_content(tmp_path: Path):
    _build_repo(tmp_path)
    corpus = MarkerCorpusSerializer().serialize(tmp_path)
    for rel, start, end in corpus.file_map:
        # the recorded span slices exactly the stored content for that file
        assert corpus.bytes[start:end] == MarkerCorpusSerializer().deserialize(corpus.bytes)[rel]


def test_corrupted_framing_raises(tmp_path: Path):
    _build_repo(tmp_path)
    corpus = MarkerCorpusSerializer().serialize(tmp_path)
    with pytest.raises(PackError):
        MarkerCorpusSerializer().deserialize(b"not-a-frame" + corpus.bytes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_corpus.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/corpus.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packer.engine.common.errors import PackError
from packer.engine.pack.varint import _read_uvarint, _write_uvarint

_MAGIC = b"\x00PAKFILE\x00"


@dataclass(frozen=True)
class SerializedCorpus:
    bytes: bytes
    file_map: list[tuple[str, int, int]]  # (posix_relpath, content_start, content_end)

    @property
    def n_files(self) -> int:
        return len(self.file_map)

    @property
    def original_bytes(self) -> int:
        return sum(end - start for _, start, end in self.file_map)


class MarkerCorpusSerializer:
    """Repo <-> bytes with reversible, self-delimiting file frames.

    Frame layout (repeated, files sorted by posix relpath):
        _MAGIC | uvarint(len(path)) | path_utf8 | uvarint(len(content)) | content
    """

    def serialize(self, root: Path) -> SerializedCorpus:
        paths = sorted(
            (p for p in root.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(root).as_posix(),
        )
        out = bytearray()
        file_map: list[tuple[str, int, int]] = []
        for p in paths:
            rel = p.relative_to(root).as_posix()
            path_bytes = rel.encode("utf-8")
            content = p.read_bytes()
            out += _MAGIC
            _write_uvarint(out, len(path_bytes))
            out += path_bytes
            _write_uvarint(out, len(content))
            start = len(out)
            out += content
            file_map.append((rel, start, len(out)))
        return SerializedCorpus(bytes=bytes(out), file_map=file_map)

    def deserialize(
        self, data: bytes, file_map: list[tuple[str, int, int]] | None = None
    ) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        i = 0
        n = len(data)
        m = len(_MAGIC)
        while i < n:
            if data[i : i + m] != _MAGIC:
                raise PackError(
                    "corpus framing corrupted: bad magic",
                    context={"offset": i},
                )
            i += m
            path_len, i = _read_uvarint(data, i)
            rel = data[i : i + path_len].decode("utf-8")
            i += path_len
            content_len, i = _read_uvarint(data, i)
            files[rel] = data[i : i + content_len]
            i += content_len
        return files
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_corpus.py -v && uv run mypy src`
Expected: PASS + mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/corpus.py tests/unit/pack/test_corpus.py
git commit -m "feat(pack): add reversible MarkerCorpusSerializer + SerializedCorpus"
```

---

### Task 4: ByteBPETokenizer (`byte-bpe`)

**Files:**
- Create: `src/packer/engine/pack/tokenizer.py`
- Modify: `src/packer/engine/pack/__init__.py` (append registration import)
- Test: `tests/unit/pack/test_tokenizer.py`

**Interfaces:**
- Consumes: `TOKENIZER_REGISTRY` (Phase 0 `common.registries`); the `Tokenizer` port (Phase 0 `common.ports`): `train(corpus: bytes, vocab_size: int) -> None`, `encode(data: bytes) -> list[int]`, `decode(tokens: list[int]) -> bytes`; `PackError`.
- Produces: `ByteBPETokenizer` registered `@TOKENIZER_REGISTRY.register("byte-bpe")`, implementing the `Tokenizer` port plus `vocab_size() -> int`, `bos_id() -> int`, `to_bytes() -> bytes`, `from_bytes(blob: bytes) -> ByteBPETokenizer`. Lossless over arbitrary bytes via a latin-1 byte↔char bijection and a full 256-symbol initial alphabet.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_tokenizer.py`:
```python
import pytest

from packer.engine.common.registries import TOKENIZER_REGISTRY
from packer.engine.pack.tokenizer import ByteBPETokenizer


@pytest.fixture()
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
    with pytest.raises(Exception):
        ByteBPETokenizer().encode(b"x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_tokenizer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/tokenizer.py`:
```python
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
        trainer = trainers.BpeTrainer(
            vocab_size=max(int(vocab_size), len(_BYTE_ALPHABET) + 1),
            initial_alphabet=_BYTE_ALPHABET,
            special_tokens=[_BOS],
            show_progress=False,
        )
        tok.train_from_iterator([corpus.decode("latin-1")], trainer=trainer)
        self._tok = tok

    def encode(self, data: bytes) -> list[int]:
        return self._require().encode(data.decode("latin-1"), add_special_tokens=False).ids

    def decode(self, tokens: list[int]) -> bytes:
        text = self._require().decode(tokens, skip_special_tokens=False)
        return text.encode("latin-1")

    def vocab_size(self) -> int:
        return self._require().get_vocab_size()

    def bos_id(self) -> int:
        tid = self._require().token_to_id(_BOS)
        if tid is None:
            raise PackError("tokenizer is missing the <bos> special token")
        return int(tid)

    def to_bytes(self) -> bytes:
        return self._require().to_str().encode("utf-8")

    @classmethod
    def from_bytes(cls, blob: bytes) -> "ByteBPETokenizer":
        obj = cls()
        obj._tok = Tokenizer.from_str(blob.decode("utf-8"))
        return obj

    def _require(self) -> Tokenizer:
        if self._tok is None:
            raise PackError("tokenizer used before train()/from_bytes()")
        return self._tok
```

Append to `src/packer/engine/pack/__init__.py`:
```python
from packer.engine.pack import tokenizer as _tokenizer  # noqa: F401  (self-registration)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_tokenizer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/tokenizer.py src/packer/engine/pack/__init__.py tests/unit/pack/test_tokenizer.py
git commit -m "feat(pack): add byte-level BPE tokenizer (byte-bpe) with lossless coverage"
```

---

### Task 5: TinyDecoder + TinyDecoderArch (`tiny-decoder`)

**Files:**
- Create: `src/packer/engine/pack/arch.py`
- Modify: `src/packer/engine/pack/__init__.py`
- Test: `tests/unit/pack/test_arch.py`

**Interfaces:**
- Consumes: `ARCH_REGISTRY` (Phase 0 `common.registries`); the `ModelArchitecture` port (Phase 0 `common.ports`): `build(cfg) -> TrainableModel`.
- Produces:
  - `TinyDecoder(nn.Module)` — from-scratch causal decoder; `forward(tokens: LongTensor[B,T]) -> logits[B,T,V]`.
  - `TinyDecoderArch` registered `@ARCH_REGISTRY.register("tiny-decoder")`, implementing `ModelArchitecture`; `build(cfg) -> TinyDecoder` reads `cfg.vocab_size/d_model/n_layers/n_heads/context_len`. *(Per SYSTEM-DESIGN §5.3 the ARCH_REGISTRY entry is the `ModelArchitecture` builder registered under "tiny-decoder"; `TinyDecoder` is the `nn.Module` it builds — `ARCH_REGISTRY.create("tiny-decoder").build(cfg)`.)*

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_arch.py`:
```python
import torch
from omegaconf import OmegaConf

from packer.engine.common.registries import ARCH_REGISTRY
from packer.engine.pack.arch import TinyDecoder, TinyDecoderArch


def _cfg():
    return OmegaConf.create(
        {"vocab_size": 64, "d_model": 32, "n_layers": 2, "n_heads": 4, "context_len": 16}
    )


def test_registered_builder():
    assert "tiny-decoder" in ARCH_REGISTRY.names()
    arch = ARCH_REGISTRY.create("tiny-decoder")
    assert isinstance(arch, TinyDecoderArch)
    assert isinstance(arch.build(_cfg()), TinyDecoder)


def test_forward_shapes():
    model = TinyDecoderArch().build(_cfg())
    tokens = torch.zeros((1, 8), dtype=torch.long)
    logits = model(tokens)
    assert logits.shape == (1, 8, 64)


def test_forward_is_deterministic_in_eval():
    model = TinyDecoderArch().build(_cfg()).eval()
    tokens = torch.arange(5, dtype=torch.long).view(1, 5)
    with torch.no_grad():
        a = model(tokens)
        b = model(tokens)
    assert torch.equal(a, b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_arch.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/arch.py`:
```python
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

from packer.engine.common.registries import ARCH_REGISTRY


class _Block(nn.Module):
    def __init__(self, d_model: int, n_heads: int) -> None:
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError(f"d_model {d_model} not divisible by n_heads {n_heads}")
        self.n_heads = n_heads
        self.ln1 = nn.LayerNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        h = self.ln1(x)
        qkv = self.qkv(h).view(b, t, 3, self.n_heads, c // self.n_heads)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # [3, B, H, T, hd]
        q, k, v = qkv[0], qkv[1], qkv[2]
        att = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        att = att.transpose(1, 2).reshape(b, t, c)
        x = x + self.proj(att)
        x = x + self.mlp(self.ln2(x))
        return x


class TinyDecoder(nn.Module):
    """From-scratch causal decoder-only transformer sized from config."""

    def __init__(
        self, vocab_size: int, d_model: int, n_layers: int, n_heads: int, context_len: int
    ) -> None:
        super().__init__()
        self.context_len = context_len
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(context_len, d_model)
        self.blocks = nn.ModuleList([_Block(d_model, n_heads) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        _, t = tokens.shape
        pos = torch.arange(t, device=tokens.device)
        x = self.tok_emb(tokens) + self.pos_emb(pos)[None, :, :]
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


@ARCH_REGISTRY.register("tiny-decoder")
class TinyDecoderArch:
    """ModelArchitecture builder for the tiny causal decoder."""

    def build(self, cfg: object) -> TinyDecoder:
        return TinyDecoder(
            vocab_size=int(cfg.vocab_size),      # type: ignore[attr-defined]
            d_model=int(cfg.d_model),            # type: ignore[attr-defined]
            n_layers=int(cfg.n_layers),          # type: ignore[attr-defined]
            n_heads=int(cfg.n_heads),            # type: ignore[attr-defined]
            context_len=int(cfg.context_len),    # type: ignore[attr-defined]
        )
```

Append to `src/packer/engine/pack/__init__.py`:
```python
from packer.engine.pack import arch as _arch  # noqa: F401  (self-registration)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_arch.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/arch.py src/packer/engine/pack/__init__.py tests/unit/pack/test_arch.py
git commit -m "feat(pack): add from-scratch TinyDecoder + tiny-decoder architecture builder"
```

---

### Task 6: OverfitTrainer

**Files:**
- Create: `src/packer/engine/pack/trainer.py`
- Create: `tests/unit/pack/conftest.py` (shared `cfg_factory` fixture)
- Test: `tests/unit/pack/test_trainer.py`

**Interfaces:**
- Consumes: `ProgressCallback`, `RecordingProgress`, `null_progress` (Phase 0 `common.progress`); `TinyDecoder`/`TinyDecoderArch` (Task 5).
- Produces:
  - `OverfitTrainer.train(model, tokens: list[int], cfg, progress: ProgressCallback = null_progress) -> None` — overfit loop (AdamW, `weight_decay=cfg.weight_decay`, no dropout), teacher forcing with `bos = int(cfg.bos_token_id)`, device from `cfg.device` (`auto|cpu|cuda`), emits `step="train"` progress with epoch/loss/token-accuracy. No-ops on empty `tokens`.
  - Module helpers `apply_determinism(seed: int, deterministic: bool) -> None` (seeds `random`/`numpy`/`torch`, sets torch deterministic flags) and `resolve_device(name: str) -> str`, re-used by `Packer`.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/conftest.py`:
```python
import pytest
from omegaconf import DictConfig, OmegaConf


@pytest.fixture()
def cfg_factory():
    def make(**overrides: object) -> DictConfig:
        base = {
            "arch": "tiny-decoder",
            "tokenizer": "byte-bpe",
            "decode": "teacher-forced-greedy",
            "codec": "delta-varint-v1",
            "n_layers": 1,
            "d_model": 32,
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
            "out_dir": "./outputs",
        }
        base.update(overrides)
        return OmegaConf.create(base)

    return make
```

`tests/unit/pack/test_trainer.py`:
```python
import torch

from packer.engine.common.progress import RecordingProgress
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.trainer import OverfitTrainer, apply_determinism, resolve_device


def _model(cfg):
    apply_determinism(int(cfg.seed), bool(cfg.deterministic))
    return TinyDecoderArch().build(cfg)


def test_resolve_device_explicit():
    assert resolve_device("cpu") == "cpu"


def test_training_reduces_loss_and_reports(cfg_factory):
    cfg = cfg_factory(epochs=40, vocab_size=64)
    model = _model(cfg)
    tokens = [3, 1, 4, 1, 5, 9, 2, 6]
    inp = torch.tensor([[int(cfg.bos_token_id)] + tokens[:-1]])
    tgt = torch.tensor([tokens])

    def loss_of(m):
        with torch.no_grad():
            logits = m(inp)
            return torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)), tgt.reshape(-1)
            ).item()

    before = loss_of(model)
    rec = RecordingProgress()
    OverfitTrainer().train(model, tokens, cfg, rec)
    after = loss_of(model)
    assert after < before
    assert any(e.step == "train" for e in rec.events)


def test_training_is_deterministic(cfg_factory):
    cfg = cfg_factory(epochs=10, vocab_size=64)
    tokens = [1, 2, 3, 4, 5, 6]
    m1 = _model(cfg)
    OverfitTrainer().train(m1, tokens, cfg)
    m2 = _model(cfg)
    OverfitTrainer().train(m2, tokens, cfg)
    for p1, p2 in zip(m1.parameters(), m2.parameters()):
        assert torch.equal(p1, p2)


def test_empty_tokens_noop(cfg_factory):
    cfg = cfg_factory()
    model = _model(cfg)
    OverfitTrainer().train(model, [], cfg)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_trainer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/trainer.py`:
```python
from __future__ import annotations

import random

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from packer.engine.common.progress import ProgressCallback, null_progress


def apply_determinism(seed: int, deterministic: bool) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
        if torch.cuda.is_available():
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False


def resolve_device(name: str) -> str:
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


class OverfitTrainer:
    """Trains a decoder to memorize a token stream (no dropout, teacher forcing)."""

    def train(
        self,
        model: nn.Module,
        tokens: list[int],
        cfg: object,
        progress: ProgressCallback = null_progress,
    ) -> None:
        seed = int(cfg.seed)                       # type: ignore[attr-defined]
        apply_determinism(seed, bool(cfg.deterministic))  # type: ignore[attr-defined]
        device = resolve_device(str(cfg.device))   # type: ignore[attr-defined]
        model.to(device).train()
        if not tokens:
            progress(step="train", pct=0.8, detail="empty corpus; nothing to train")
            return
        bos = int(cfg.bos_token_id)                # type: ignore[attr-defined]
        inp = torch.tensor([[bos] + tokens[:-1]], dtype=torch.long, device=device)
        tgt = torch.tensor([tokens], dtype=torch.long, device=device)
        opt = torch.optim.AdamW(
            model.parameters(),
            lr=float(cfg.lr),                       # type: ignore[attr-defined]
            weight_decay=float(cfg.weight_decay),   # type: ignore[attr-defined]
        )
        epochs = int(cfg.epochs)                    # type: ignore[attr-defined]
        report_every = max(1, epochs // 20)
        for epoch in range(epochs):
            opt.zero_grad(set_to_none=True)
            logits = model(inp)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1))
            loss.backward()
            opt.step()
            if epoch % report_every == 0 or epoch == epochs - 1:
                with torch.no_grad():
                    acc = (logits.argmax(-1) == tgt).float().mean().item()
                pct = 0.05 + 0.75 * (epoch + 1) / epochs
                progress(
                    step="train",
                    pct=pct,
                    detail=f"epoch {epoch + 1}/{epochs} loss={loss.item():.4f} acc={acc:.3f}",
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_trainer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/trainer.py tests/unit/pack/conftest.py tests/unit/pack/test_trainer.py
git commit -m "feat(pack): add OverfitTrainer with determinism + progress reporting"
```

---

### Task 7: DeltaVarintCodec + ResidualCapturer (`delta-varint-v1`)

**Files:**
- Create: `src/packer/engine/pack/residuals.py`
- Modify: `src/packer/engine/pack/__init__.py`
- Test: `tests/unit/pack/test_residuals.py`

**Interfaces:**
- Consumes: `CODEC_REGISTRY` (Phase 0 `common.registries`); `Residuals = list[tuple[int, int]]` and the `ResidualCodec` Protocol (Phase 0 `artifacts.codec`); `_write_uvarint`/`_read_uvarint` (Task 1); `InferenceModel` (Task 8 — forward-referenced; capture is tested against it there and here via a light stub).
- Produces:
  - `DeltaVarintCodec` registered `@CODEC_REGISTRY.register("delta-varint-v1")`, implementing `ResidualCodec`: `encode(residuals: Residuals) -> bytes` (sorts, delta-encodes positions, varint token ids), `decode(blob: bytes) -> Residuals`.
  - `ResidualCapturer.capture(model, tokens: list[int]) -> Residuals` — one teacher-forced pass; returns `[(position, true_token)]` where `argmax != true`.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_residuals.py`:
```python
import hypothesis.strategies as st
from hypothesis import given, settings

from packer.engine.common.registries import CODEC_REGISTRY
from packer.engine.pack.residuals import DeltaVarintCodec, ResidualCapturer


def test_codec_registered():
    assert "delta-varint-v1" in CODEC_REGISTRY.names()
    assert isinstance(CODEC_REGISTRY.create("delta-varint-v1"), DeltaVarintCodec)


def test_codec_empty():
    codec = DeltaVarintCodec()
    assert codec.decode(codec.encode([])) == []


@settings(max_examples=200)
@given(
    st.lists(st.tuples(st.integers(0, 100_000), st.integers(0, 8191)))
)
def test_codec_roundtrip(pairs):
    residuals = sorted(dict(pairs).items())  # unique positions, ascending
    codec = DeltaVarintCodec()
    assert codec.decode(codec.encode(residuals)) == residuals


class _StubModel:
    """Teacher-forced argmax that always predicts 0 -> everything is a residual."""

    bos_token_id = 0

    def teacher_forced_preds(self, tokens):
        return [0] * len(tokens)


def test_capture_flags_all_mismatches():
    tokens = [5, 0, 7, 0, 9]
    residuals = ResidualCapturer().capture(_StubModel(), tokens)
    # positions whose true token != predicted 0
    assert residuals == [(0, 5), (2, 7), (4, 9)]


def test_capture_empty():
    assert ResidualCapturer().capture(_StubModel(), []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_residuals.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/residuals.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.artifacts.codec import Residuals
from packer.engine.common.registries import CODEC_REGISTRY
from packer.engine.pack.varint import _read_uvarint, _write_uvarint

if TYPE_CHECKING:
    from packer.engine.pack.decode import InferenceModel


@CODEC_REGISTRY.register("delta-varint-v1")
class DeltaVarintCodec:
    """Delta-encoded positions + varint token ids. Implements ResidualCodec."""

    def encode(self, residuals: Residuals) -> bytes:
        items = sorted(residuals)
        out = bytearray()
        _write_uvarint(out, len(items))
        prev = 0
        for pos, tok in items:
            _write_uvarint(out, pos - prev)
            _write_uvarint(out, tok)
            prev = pos
        return bytes(out)

    def decode(self, blob: bytes) -> Residuals:
        i = 0
        count, i = _read_uvarint(blob, i)
        residuals: Residuals = []
        pos = 0
        for _ in range(count):
            delta, i = _read_uvarint(blob, i)
            tok, i = _read_uvarint(blob, i)
            pos += delta
            residuals.append((pos, tok))
        return residuals


class ResidualCapturer:
    """One teacher-forced pass -> positions where argmax disagrees with truth."""

    def capture(self, model: "InferenceModel", tokens: list[int]) -> Residuals:
        if not tokens:
            return []
        preds = model.teacher_forced_preds(tokens)
        return [(i, tokens[i]) for i in range(len(tokens)) if preds[i] != tokens[i]]
```

Append to `src/packer/engine/pack/__init__.py`:
```python
from packer.engine.pack import residuals as _residuals  # noqa: F401  (self-registration)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_residuals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/residuals.py src/packer/engine/pack/__init__.py tests/unit/pack/test_residuals.py
git commit -m "feat(pack): add DeltaVarintCodec + teacher-forced ResidualCapturer"
```

---

### Task 8: InferenceModel + TeacherForcedGreedy (`teacher-forced-greedy`) + Unpacker

**Files:**
- Create: `src/packer/engine/pack/decode.py`
- Modify: `src/packer/engine/pack/__init__.py`
- Test: `tests/unit/pack/test_decode.py`

**Interfaces:**
- Consumes: `DECODE_REGISTRY` (Phase 0 `common.registries`); the `DecodeStrategy` port (Phase 0 `common.ports`): `reconstruct(model, residuals, length) -> bytes`; `ResidualCodec`/`Residuals` (Phase 0 `artifacts.codec`); `ByteBPETokenizer` (Task 4).
- Produces (SHARED with Phase 3, keep stable):
  - `InferenceModel(model: nn.Module, tokenizer, bos_token_id: int)` — forward-only wrapper; `teacher_forced_preds(tokens) -> list[int]`, `next_token(context) -> int`, `detokenize(tokens) -> bytes`.
  - `TeacherForcedGreedy` registered `@DECODE_REGISTRY.register("teacher-forced-greedy")`, implementing `DecodeStrategy`: self-correcting greedy decode (`argmax`, override from residuals) → detokenized bytes.
  - `Unpacker(decode: DecodeStrategy, codec: ResidualCodec)` with `reconstruct(model, residuals, length) -> bytes` and `reconstruct_blob(model, blob, length) -> bytes`.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_decode.py`:
```python
import torch

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
    from omegaconf import OmegaConf

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
    from omegaconf import OmegaConf

    model = TinyDecoderArch().build(
        OmegaConf.create(
            {"vocab_size": 320, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 256}
        )
    )
    inf = InferenceModel(model, tok, tok.bos_id())
    assert TeacherForcedGreedy().reconstruct(inf, [], 0) == b""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_decode.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/decode.py`:
```python
from __future__ import annotations

import torch
from torch import nn

from packer.engine.artifacts.codec import Residuals, ResidualCodec
from packer.engine.common.ports import DecodeStrategy
from packer.engine.common.registries import DECODE_REGISTRY
from packer.engine.pack.tokenizer import ByteBPETokenizer


class InferenceModel:
    """Thin forward-only wrapper (model + tokenizer) used by capture and decode."""

    def __init__(self, model: nn.Module, tokenizer: ByteBPETokenizer, bos_token_id: int) -> None:
        self.model = model.eval()
        self.tokenizer = tokenizer
        self.bos_token_id = bos_token_id
        self.device = next(model.parameters()).device

    @torch.no_grad()
    def teacher_forced_preds(self, tokens: list[int]) -> list[int]:
        context = [self.bos_token_id] + list(tokens[:-1])
        x = torch.tensor([context], dtype=torch.long, device=self.device)
        logits = self.model(x)[0]  # [len(context), V]
        return logits.argmax(-1).tolist()

    @torch.no_grad()
    def next_token(self, context: list[int]) -> int:
        x = torch.tensor([context], dtype=torch.long, device=self.device)
        logits = self.model(x)[0, -1]  # [V]
        return int(logits.argmax(-1))

    def detokenize(self, tokens: list[int]) -> bytes:
        return self.tokenizer.decode(tokens)


@DECODE_REGISTRY.register("teacher-forced-greedy")
class TeacherForcedGreedy:
    """Deterministic self-correcting decode (ARCHITECTURE §5.2). Implements DecodeStrategy."""

    def reconstruct(self, model: InferenceModel, residuals: Residuals, length: int) -> bytes:
        overrides = dict(residuals)
        context = [model.bos_token_id]
        out: list[int] = []
        for i in range(length):
            pred = model.next_token(context)
            token = overrides.get(i, pred)
            out.append(token)
            context.append(token)
        return model.detokenize(out)


class Unpacker:
    """One decode path shared by pack-time verify and Phase 3 exact extraction."""

    def __init__(self, decode: DecodeStrategy, codec: ResidualCodec) -> None:
        self._decode = decode
        self._codec = codec

    def reconstruct(self, model: InferenceModel, residuals: Residuals, length: int) -> bytes:
        return self._decode.reconstruct(model, residuals, length)

    def reconstruct_blob(self, model: InferenceModel, blob: bytes, length: int) -> bytes:
        return self._decode.reconstruct(model, self._codec.decode(blob), length)
```

Append to `src/packer/engine/pack/__init__.py`:
```python
from packer.engine.pack import decode as _decode  # noqa: F401  (self-registration)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_decode.py -v`
Expected: PASS (byte-exact even with an untrained model — proves residual-guaranteed losslessness).

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/decode.py src/packer/engine/pack/__init__.py tests/unit/pack/test_decode.py
git commit -m "feat(pack): add InferenceModel, TeacherForcedGreedy decode, and shared Unpacker"
```

---

### Task 9: `unpack(pak_path)` module function

**Files:**
- Modify: `src/packer/engine/pack/unpacker.py` (co-locate module fns with `Unpacker`) — *note:* keep `Unpacker` in `decode.py` (Task 8) and put the `.pak`-facing functions here, importing `Unpacker`.
- Modify: `src/packer/engine/pack/__init__.py`
- Test: `tests/unit/pack/test_unpacker.py`

**Interfaces:**
- Consumes: `PakReader`/`PakBundle` (Phase 0 `artifacts.pak`); `Manifest`/`ModelInfo` (Phase 0 `artifacts.manifest`); `CODEC_REGISTRY`/`DECODE_REGISTRY` (Phase 0 `common.registries`); `ReconstructionError` (Phase 0 `common.errors`); `ByteBPETokenizer` (Task 4), `TinyDecoder` (Task 5), `InferenceModel`/`Unpacker` (Task 8), `MarkerCorpusSerializer` (Task 3).
- Produces (Phase 3 `extract_exact` reuses these verbatim):
  - `unpack(pak_path: Path) -> dict[str, bytes]` — read `.pak`, rebuild model + tokenizer, decode residual blob, split frames → `{posix_relpath: bytes}`.
  - `unpack_bundle(bundle: PakBundle) -> dict[str, bytes]` — same, from an already-read bundle.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_unpacker.py`:
```python
from pathlib import Path

import numpy as np
import torch

from packer.engine.artifacts.manifest import Manifest
from packer.engine.artifacts.pak import PakBundle, PakWriter
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.decode import InferenceModel, TeacherForcedGreedy, Unpacker
from packer.engine.pack.residuals import DeltaVarintCodec, ResidualCapturer
from packer.engine.pack.tokenizer import ByteBPETokenizer
from packer.engine.pack.trainer import apply_determinism
from packer.engine.pack.unpacker import unpack, unpack_bundle


def _hand_built_bundle() -> tuple[PakBundle, dict[str, bytes]]:
    files = {"a.py": b"x = 1\n", "d/b.bin": b"\x00\x01\x02\x03"}
    from packer.engine.pack.corpus import MarkerCorpusSerializer  # framing must match serializer

    # Frame the files exactly as the serializer would (single-source-of-truth):
    import tempfile

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

    from omegaconf import OmegaConf

    cfg = OmegaConf.create(
        {"vocab_size": 320, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 256}
    )
    apply_determinism(0, True)
    model = TinyDecoderArch().build(cfg)
    inf = InferenceModel(model, tok, tok.bos_id())
    residuals = ResidualCapturer().capture(inf, tokens)
    codec = DeltaVarintCodec()
    blob = codec.encode(residuals)
    assert Unpacker(TeacherForcedGreedy(), codec).reconstruct(inf, residuals, len(tokens)) == corpus.bytes

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_unpacker.py -v`
Expected: FAIL — `unpack`/`unpack_bundle` missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/unpacker.py`:
```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from packer.engine.artifacts.manifest import Manifest, ModelInfo
from packer.engine.artifacts.pak import PakBundle, PakReader
from packer.engine.common.errors import ReconstructionError
from packer.engine.common.registries import CODEC_REGISTRY, DECODE_REGISTRY
from packer.engine.pack.arch import TinyDecoder
from packer.engine.pack.corpus import MarkerCorpusSerializer
from packer.engine.pack.decode import InferenceModel, Unpacker
from packer.engine.pack.tokenizer import ByteBPETokenizer


def unpack(pak_path: Path) -> dict[str, bytes]:
    """Deterministic self-correcting decode of a .pak -> {posix_relpath: bytes}."""
    return unpack_bundle(PakReader().read(pak_path))


def unpack_bundle(bundle: PakBundle) -> dict[str, bytes]:
    manifest = bundle.manifest
    tokenizer = ByteBPETokenizer.from_bytes(bundle.tokenizer_bytes)
    model = _rebuild_model(bundle.tensors, manifest.model)
    inference = InferenceModel(model, tokenizer, manifest.decode.bos_token_id)
    codec = CODEC_REGISTRY.create(manifest.residuals.codec)
    decode = DECODE_REGISTRY.create(manifest.decode.strategy)
    corpus_bytes = Unpacker(decode, codec).reconstruct_blob(
        inference, bundle.residual_blob, manifest.decode.length_tokens
    )
    return MarkerCorpusSerializer().deserialize(corpus_bytes)


def _rebuild_model(tensors: dict[str, np.ndarray], info: ModelInfo) -> TinyDecoder:
    for field in ("n_layers", "d_model", "n_heads", "vocab_size", "context_len"):
        if getattr(info, field) is None:
            raise ReconstructionError(
                f"manifest.model.{field} is required to rebuild the decoder",
                context={"field": field},
            )
    model = TinyDecoder(
        vocab_size=int(info.vocab_size),
        d_model=int(info.d_model),
        n_layers=int(info.n_layers),
        n_heads=int(info.n_heads),
        context_len=int(info.context_len),
    )
    state = {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in tensors.items()}
    model.load_state_dict(state)
    return model
```

Append to `src/packer/engine/pack/__init__.py`:
```python
from packer.engine.pack.unpacker import unpack, unpack_bundle  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_unpacker.py -v && uv run mypy src`
Expected: PASS + mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/unpacker.py src/packer/engine/pack/__init__.py tests/unit/pack/test_unpacker.py
git commit -m "feat(pack): add standalone unpack()/unpack_bundle() reused by Phase 3"
```

---

### Task 10: Packer orchestrator + manifest metrics + in-process verification gate

**Files:**
- Create: `src/packer/engine/pack/packer.py`
- Modify: `src/packer/engine/pack/__init__.py`
- Test: `tests/unit/pack/test_packer.py`

**Interfaces:**
- Consumes: all Phase-1 plugins via registries; `PakBundle`/`PakWriter` (Phase 0 `artifacts.pak`); `Manifest` + nested `ModelInfo`/`CorpusInfo`/`FileSpan`/`DecodeInfo`/`ResidualInfo`/`Metrics` (Phase 0 `artifacts.manifest`); `EnginePorts` (Phase 0 `common.assembler`, `store` may be `None`); `PackError` (Phase 0 `common.errors`); `ProgressCallback`/`null_progress` (Phase 0 `common.progress`); `apply_determinism`/`resolve_device` (Task 6).
- Produces (Phase 3 / Phase 4 consume `Packer` by name):
  - `Packer.pack(root: Path, cfg, ports, progress: ProgressCallback = null_progress) -> str` — serialize → tokenize → build → train → capture → **VERIFY byte-exact (fail-fast `PackError`)** → build manifest w/ honest metrics → persist. Returns the artifact id (`ports.store.put_pak`) or, when `ports.store is None`, the `.pak` path under `cfg.out_dir`.

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_packer.py`:
```python
import gzip
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
    (tmp_path / "repo" / "big.txt").write_bytes(b"a" * 5000)
    cfg = cfg_factory(epochs=1, context_len=64, out_dir=str(tmp_path / "out"))
    with pytest.raises(PackError):
        Packer().pack(tmp_path / "repo", cfg, EnginePorts())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_packer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/pack/packer.py`:
```python
from __future__ import annotations

import datetime
import gzip
import hashlib
from pathlib import Path

import numpy as np
from omegaconf import OmegaConf

from packer.engine.artifacts.manifest import Manifest
from packer.engine.artifacts.pak import PakBundle, PakWriter
from packer.engine.common.errors import PackError
from packer.engine.common.progress import ProgressCallback, null_progress
from packer.engine.common.registries import (
    ARCH_REGISTRY,
    CODEC_REGISTRY,
    DECODE_REGISTRY,
    TOKENIZER_REGISTRY,
)
from packer.engine.pack.corpus import MarkerCorpusSerializer, SerializedCorpus
from packer.engine.pack.decode import InferenceModel, Unpacker
from packer.engine.pack.residuals import ResidualCapturer
from packer.engine.pack.trainer import OverfitTrainer, apply_determinism


class Packer:
    """Part-1 orchestrator (SYSTEM-DESIGN §5.3)."""

    def pack(
        self,
        root: Path,
        cfg: object,
        ports: object,
        progress: ProgressCallback = null_progress,
    ) -> str:
        root = Path(root)
        progress(step="serialize", pct=0.0, detail=str(root))
        corpus = MarkerCorpusSerializer().serialize(root)

        tokenizer = TOKENIZER_REGISTRY.create(str(cfg.tokenizer))  # type: ignore[attr-defined]
        tokenizer.train(corpus.bytes, int(cfg.vocab_size))          # type: ignore[attr-defined]
        tokens = tokenizer.encode(corpus.bytes)
        progress(
            step="tokenize",
            pct=0.05,
            detail=f"{len(tokens)} tokens, vocab={tokenizer.vocab_size()}",
        )

        context_len = int(cfg.context_len)                          # type: ignore[attr-defined]
        if len(tokens) > context_len:
            raise PackError(
                f"corpus token length {len(tokens)} exceeds context_len {context_len}",
                context={"n_tokens": len(tokens), "context_len": context_len},
            )

        bos = tokenizer.bos_id()
        if hasattr(cfg, "bos_token_id"):
            OmegaConf.update(cfg, "bos_token_id", bos, force_add=True)  # keep train/decode aligned

        apply_determinism(int(cfg.seed), bool(cfg.deterministic))   # type: ignore[attr-defined]
        model = ARCH_REGISTRY.create(str(cfg.arch)).build(cfg)      # type: ignore[attr-defined]
        OverfitTrainer().train(model, tokens, cfg, progress)

        inference = InferenceModel(model, tokenizer, bos)
        progress(step="capture", pct=0.85, detail="teacher-forced residual capture")
        residuals = ResidualCapturer().capture(inference, tokens)

        decode = DECODE_REGISTRY.create(str(cfg.decode))            # type: ignore[attr-defined]
        codec = CODEC_REGISTRY.create(str(cfg.codec))              # type: ignore[attr-defined]

        progress(step="verify", pct=0.92, detail="byte-exact round-trip")
        rebuilt = Unpacker(decode, codec).reconstruct(inference, residuals, len(tokens))
        if rebuilt != corpus.bytes:
            raise PackError(
                "round-trip verification failed: reconstruction != corpus",
                context={"n_tokens": len(tokens), "n_residuals": len(residuals)},
            )

        blob = codec.encode(residuals)
        tensors = {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
        manifest = _build_manifest(cfg, corpus, tokens, residuals, blob, tensors, tokenizer, bos)
        bundle = PakBundle(
            tensors=tensors,
            tokenizer_bytes=tokenizer.to_bytes(),
            manifest=manifest,
            residual_blob=blob,
        )

        progress(step="write", pct=0.98, detail="persist .pak")
        artifact_id = _persist(bundle, cfg, ports, root)
        progress(step="done", pct=1.0, detail=artifact_id)
        return artifact_id


def _persist(bundle: PakBundle, cfg: object, ports: object, root: Path) -> str:
    store = getattr(ports, "store", None)
    if store is not None:
        return store.put_pak(bundle)
    out_dir = Path(str(getattr(cfg, "out_dir", "./outputs")))
    out = out_dir / f"{root.name}.pak"
    PakWriter().write(out, bundle)
    return str(out)


def _token_file_map(corpus: SerializedCorpus, tokenizer: object) -> list[dict]:
    spans = []
    for rel, start, end in corpus.file_map:
        spans.append(
            {
                "path": rel,
                "token_start": len(tokenizer.encode(corpus.bytes[:start])),  # type: ignore[attr-defined]
                "token_end": len(tokenizer.encode(corpus.bytes[:end])),      # type: ignore[attr-defined]
            }
        )
    return spans


def _build_manifest(
    cfg: object,
    corpus: SerializedCorpus,
    tokens: list[int],
    residuals: list[tuple[int, int]],
    blob: bytes,
    tensors: dict[str, np.ndarray],
    tokenizer: object,
    bos: int,
) -> Manifest:
    model_bytes = sum(int(v.nbytes) for v in tensors.values())
    param_count = sum(int(v.size) for v in tensors.values())
    tokenizer_bytes = len(tokenizer.to_bytes())  # type: ignore[attr-defined]
    original_bytes = corpus.original_bytes
    gzip_bytes = len(gzip.compress(corpus.bytes))
    artifact_bytes = model_bytes + tokenizer_bytes + len(blob)
    ratio = (artifact_bytes / original_bytes) if original_bytes else 0.0
    return Manifest.model_validate(
        {
            "pak_version": "1.0",
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "model": {
                "arch": str(cfg.arch),                 # type: ignore[attr-defined]
                "param_count": param_count,
                "n_layers": int(cfg.n_layers),         # type: ignore[attr-defined]
                "d_model": int(cfg.d_model),           # type: ignore[attr-defined]
                "n_heads": int(cfg.n_heads),           # type: ignore[attr-defined]
                "vocab_size": int(cfg.vocab_size),     # type: ignore[attr-defined]
                "context_len": int(cfg.context_len),   # type: ignore[attr-defined]
            },
            "corpus": {
                "n_files": corpus.n_files,
                "n_bytes": original_bytes,
                "n_tokens": len(tokens),
                "sha256": hashlib.sha256(corpus.bytes).hexdigest(),
                "file_map": _token_file_map(corpus, tokenizer),
                "boundary_scheme": "length-prefixed-v1",
            },
            "decode": {
                "strategy": str(cfg.decode),           # type: ignore[attr-defined]
                "length_tokens": len(tokens),
                "bos_token_id": bos,
            },
            "residuals": {
                "count": len(residuals),
                "ratio": (len(residuals) / len(tokens)) if tokens else 0.0,
                "codec": str(cfg.codec),               # type: ignore[attr-defined]
            },
            "metrics": {
                "model_bytes": model_bytes,
                "artifact_bytes": artifact_bytes,
                "original_bytes": original_bytes,
                "gzip_bytes": gzip_bytes,
                "compression_ratio_vs_original": ratio,
                "lossless": True,
            },
            "seed": int(cfg.seed),                     # type: ignore[attr-defined]
        }
    )
```

Append to `src/packer/engine/pack/__init__.py`:
```python
from packer.engine.pack.packer import Packer  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_packer.py -v && uv run lint-imports && uv run mypy src`
Expected: PASS; import-linter contracts kept (pack imports only common/models/artifacts + torch/numpy/omegaconf); mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/pack/packer.py src/packer/engine/pack/__init__.py tests/unit/pack/test_packer.py
git commit -m "feat(pack): add Packer orchestrator with byte-exact verify gate and honest metrics"
```

---

### Task 11: Property-based round-trip gates (arbitrary bytes + epochs=1 + determinism)

**Files:**
- Test: `tests/unit/pack/test_roundtrip.py`

**Interfaces:**
- Consumes: `Packer`/`unpack` (Tasks 9–10); `EnginePorts` (Phase 0 `common.assembler`); `null_progress` (Phase 0 `common.progress`); Hypothesis (Phase 0 dev dep).
- Produces: the CI correctness gates — `pack → unpack` byte-identical over arbitrary bytes, byte-identical with `epochs=1`, and byte-identical artifacts across two same-seed runs.

- [ ] **Step 1: Write the failing test** *(fails until Tasks 3–10 exist; run standalone to confirm the gate itself is wired)*

`tests/unit/pack/test_roundtrip.py`:
```python
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.progress import null_progress
from packer.engine.pack.packer import Packer
from packer.engine.pack.unpacker import unpack


def _tiny_cfg(tmp_out: Path, **over):
    from omegaconf import OmegaConf

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
    return OmegaConf.create(base)


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
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
    # weights, tokenizer, and residuals are the correctness-relevant bytes (manifest carries a timestamp)
    assert (Path(a) / "model.safetensors").read_bytes() == (Path(b) / "model.safetensors").read_bytes()
    assert (Path(a) / "residuals.bin").read_bytes() == (Path(b) / "residuals.bin").read_bytes()
    assert (Path(a) / "tokenizer.json").read_bytes() == (Path(b) / "tokenizer.json").read_bytes()
```

- [ ] **Step 2: Run test to verify it fails (then passes once deps land)**

Run: `uv run pytest tests/unit/pack/test_roundtrip.py -v`
Expected (before Tasks 3–10 complete): FAIL — imports missing. After the stack is implemented: PASS. *(If you are executing strictly in order this task is written last; run it to confirm all three gates are green.)*

- [ ] **Step 3: Run the whole pack suite + quality gates**

Run: `uv run pytest tests/unit/pack -v && uv run lint-imports && uv run mypy src && uv run ruff check .`
Expected: all PASS; contracts kept; mypy + ruff clean.

- [ ] **Step 4: Commit**
```bash
git add tests/unit/pack/test_roundtrip.py
git commit -m "test(pack): add byte-exact round-trip gates (arbitrary bytes, epochs=1, determinism)"
```

---

### Task 12: Fixture generation (≥3 memorized + ≥2 controls)

**Files:**
- Create: `scripts/make_fixtures.py`
- Test: `tests/unit/pack/test_fixtures.py`

**Interfaces:**
- Consumes: `Packer`/`unpack` (Tasks 9–10); `TinyDecoderArch` (Task 5), `OverfitTrainer`/`apply_determinism` (Task 6); `HFModelLoader`/`LoadedModel` (Phase 0 `models.loader`); `ModelRef` (Phase 0 `common.types`); `EnginePorts` (Phase 0 `common.assembler`).
- Produces: `make_fixtures(out_dir: Path) -> dict[str, Path]` — writes ≥3 memorized `.pak` (from distinct synthetic repos) + ≥2 control models (random-init and normal-trained-on-noise), the negatives Phase 2 calibrates against and Phase 3 extracts. Controls are safetensors dirs loadable via `HFModelLoader`. *(Fixtures are generated on demand — deterministic + tiny — not committed, so the 1 MB pre-commit hook stays satisfied; the object-store volume is the home for larger sets, per the spec's integration note.)*

- [ ] **Step 1: Write the failing test**

`tests/unit/pack/test_fixtures.py`:
```python
from pathlib import Path

from packer.engine.common.types import ModelRef
from packer.engine.models.loader import HFModelLoader, LoadedModel
from packer.engine.pack.unpacker import unpack


def test_make_fixtures_produces_memorized_and_controls(tmp_path: Path):
    from scripts.make_fixtures import make_fixtures

    made = make_fixtures(tmp_path)
    memorized = {k: v for k, v in made.items() if k.startswith("memorized")}
    controls = {k: v for k, v in made.items() if k.startswith("control")}

    assert len(memorized) >= 3
    assert len(controls) >= 2

    # every memorized .pak round-trips byte-exact to its recorded source
    for name, pak_path in memorized.items():
        files = unpack(pak_path)
        assert files  # non-empty reconstruction

    # every control loads via the safetensors-first loader (Phase 2 negatives)
    for name, model_dir in controls.items():
        model = HFModelLoader().load(ModelRef(kind="path", value=str(model_dir)))
        assert isinstance(model, LoadedModel)
        assert model.format == "safetensors"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/pack/test_fixtures.py -v`
Expected: FAIL — `scripts.make_fixtures` missing.

- [ ] **Step 3: Implement**

`scripts/make_fixtures.py`:
```python
"""Generate Phase-1 fixtures: memorized .pak artifacts + control models.

Deterministic and tiny by design so they can be regenerated anywhere (CI, dev,
object-store volume) without committing weights. Run directly to populate a dir:

    uv run python scripts/make_fixtures.py ./outputs/fixtures
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from omegaconf import OmegaConf
from safetensors.numpy import save_file

from packer.engine.common.assembler import EnginePorts
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.packer import Packer
from packer.engine.pack.trainer import OverfitTrainer, apply_determinism

_MEMORIZED_REPOS: dict[str, dict[str, bytes]] = {
    "memorized_calc": {
        "calc.py": b"def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
        "README.md": b"# calc\nTiny calculator.\n",
    },
    "memorized_config": {
        "settings.toml": b'name = "demo"\nport = 8080\n',
        "data/rows.csv": b"id,value\n1,10\n2,20\n",
    },
    "memorized_binary": {
        "blob.bin": bytes(range(128)),
        "note.txt": b"binary payload above\n",
    },
}


def _tiny_cfg(out_dir: Path, seed: int, epochs: int) -> object:
    return OmegaConf.create(
        {
            "arch": "tiny-decoder",
            "tokenizer": "byte-bpe",
            "decode": "teacher-forced-greedy",
            "codec": "delta-varint-v1",
            "n_layers": 1,
            "d_model": 32,
            "n_heads": 2,
            "vocab_size": 320,
            "context_len": 512,
            "epochs": epochs,
            "lr": 5e-3,
            "batch_size": 1,
            "weight_decay": 0.0,
            "device": "cpu",
            "deterministic": True,
            "seed": seed,
            "bos_token_id": 0,
            "out_dir": str(out_dir),
        }
    )


def _control_cfg() -> object:
    return OmegaConf.create(
        {"vocab_size": 320, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 512}
    )


def _save_control(model_dir: Path, model: torch.nn.Module) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    tensors = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in model.state_dict().items()}
    save_file(tensors, str(model_dir / "model.safetensors"))
    (model_dir / "config.json").write_text('{"arch": "tiny-decoder"}')


def make_fixtures(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    made: dict[str, Path] = {}

    # --- 3 memorized .pak artifacts ---
    for i, (name, files) in enumerate(_MEMORIZED_REPOS.items()):
        repo = out_dir / "repos" / name
        for rel, content in files.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
        cfg = _tiny_cfg(out_dir / "pak", seed=i, epochs=30)
        made[name] = Path(Packer().pack(repo, cfg, EnginePorts()))

    # --- control 1: random-init (untrained) ---
    apply_determinism(1000, True)
    random_model = TinyDecoderArch().build(_control_cfg())
    control_random = out_dir / "controls" / "control_random_init"
    _save_control(control_random, random_model)
    made["control_random_init"] = control_random

    # --- control 2: normal-trained on noise (does not memorize any real repo) ---
    apply_determinism(2000, True)
    noisy_model = TinyDecoderArch().build(_control_cfg())
    noise_tokens = torch.randint(0, 320, (200,)).tolist()
    OverfitTrainer().train(
        noisy_model,
        noise_tokens,
        OmegaConf.create(
            {
                "seed": 2000,
                "deterministic": True,
                "device": "cpu",
                "bos_token_id": 0,
                "lr": 1e-3,
                "weight_decay": 0.0,
                "epochs": 5,
            }
        ),
    )
    control_normal = out_dir / "controls" / "control_normal_trained"
    _save_control(control_normal, noisy_model)
    made["control_normal_trained"] = control_normal

    return made


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./outputs/fixtures")
    produced = make_fixtures(target)
    for label, path in produced.items():
        print(f"{label}: {path}")
```

*(If `scripts/` is not importable as `scripts.make_fixtures` under the repo's rootdir, add an empty `scripts/__init__.py`; the test imports `from scripts.make_fixtures import make_fixtures`.)*

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/pack/test_fixtures.py -v`
Expected: PASS — 3 memorized `.pak` round-trip; 2 controls load via `HFModelLoader`.

- [ ] **Step 5: Full suite + quality gates**

Run: `uv run pytest tests/unit && uv run lint-imports && uv run mypy src && uv run ruff format --check .`
Expected: all PASS; contracts kept; mypy + ruff clean.

- [ ] **Step 6: Commit**
```bash
git add scripts/make_fixtures.py tests/unit/pack/test_fixtures.py
git commit -m "feat(pack): add fixture generator (3 memorized paks + 2 control models)"
```

---

## Phase 1 Definition of Done

- [ ] `pack → unpack` is byte-identical on a sample repo, asserted in CI on a small fixture (Task 10 `test_pack_then_unpack_byte_exact`, Task 11 `test_roundtrip_holds_with_epochs_1`).
- [ ] Round-trip holds with `epochs=1` and over arbitrary bytes — residual mechanism proven independent of convergence (Task 8 untrained-model test; Task 11 Hypothesis + epochs=1 tests).
- [ ] Manifest records residual ratio and honest size metrics incl. `gzip_bytes`, with `artifact_bytes > gzip_bytes` on a normal repo (Task 10 `test_manifest_records_honest_metrics`).
- [ ] ≥3 memorized fixtures + ≥2 controls exist and load via `read_pak`/`load_model` (Task 12).
- [ ] Training runs on CPU (tiny) and CUDA via `device=cuda` override without code change (`resolve_device`, Task 6; `device` is a config field).
- [ ] `Packer` verifies byte-exactness in-process and raises `PackError` before writing when reconstruction diverges (Task 10 `test_verification_gate_...`).
- [ ] Fixed seed ⇒ identical weights/residuals/tokenizer bytes across runs (Task 11 `test_same_seed_yields_identical_artifact_bytes`).
- [ ] `import packer.engine.pack` registers all four plugins; `TeacherForcedGreedy`/`Unpacker`/`unpack` are importable for Phase 3 reuse.
- [ ] `uv run pytest tests/unit` green; `uv run mypy src` clean; `uv run lint-imports` all contracts kept; `uv run ruff check .` + `ruff format --check .` clean.

## Self-Review Notes

- **Spec dev-step coverage** (phase-1 spec §5): (1) corpus serializer ✓ T3; (2) byte-BPE tokenizer ✓ T4; (3) TinyDecoder ✓ T5; (4) training loop + progress + token-accuracy ✓ T6; (5) residual capture + `DeltaVarintCodec` ✓ T7; (6) self-correcting unpacker ✓ T8–T9; (7) `Packer` orchestrator with mandatory in-process verification ✓ T10; (8) manifest metrics incl. gzip ✓ T10; (9) fixtures ✓ T12. Deps/scaffold/config ✓ T1–T2.
- **Spec testing-plan coverage** (§4): property-based round-trip over arbitrary bytes + epochs=1 ✓ T11; residual codec `decode(encode(r))==r` ✓ T7; corpus reversibility incl. nested/binary/empty/unusual-char paths ✓ T3; determinism (fixed seed ⇒ identical bytes) ✓ T11; metrics honesty ✓ T10; heavy training kept tiny/CPU (fixtures deterministic, small models) ✓ T6/T11/T12.
- **Acceptance criteria** (§6): mapped 1:1 in the Definition of Done above.
- **Produced interfaces consumed by Phase 3** (SYSTEM-DESIGN §5.3/§5.5, names held stable): `MarkerCorpusSerializer`/`SerializedCorpus` (T3), `ByteBPETokenizer` `@TOKENIZER_REGISTRY("byte-bpe")` (T4), `TinyDecoder` + `TinyDecoderArch` `@ARCH_REGISTRY("tiny-decoder")` (T5), `OverfitTrainer.train` (T6), `ResidualCapturer.capture` + `DeltaVarintCodec` `@CODEC_REGISTRY("delta-varint-v1")` (T7), `TeacherForcedGreedy` `@DECODE_REGISTRY("teacher-forced-greedy")` + `InferenceModel` + `Unpacker` (T8, SHARED), `unpack`/`unpack_bundle` (T9, reused verbatim by `ExactExtractor`), `Packer.pack(...) -> str` (T10).
- **Dependency Rule:** every `pack` module imports only `engine.common`, `engine.models`, `engine.artifacts`, plus `torch`/`numpy`/`omegaconf`/`tokenizers` — no `api`/`workers`/adapters; verified by `uv run lint-imports` in T1, T10, T11, T12. `torch` is permitted in `engine.pack` (the no-`torch.nn.functional` contract is scoped to `engine.detect` only).
- **Cross-phase assumptions:** (a) Phase 0 shipped `TinyDecoderCfg`/`compose_config`, the manifest models with `ModelInfo` carrying `n_layers/d_model/n_heads/vocab_size/context_len`, `PakWriter`/`PakReader`, and `EnginePorts` (with `store` optionally `None`) exactly as in the Phase 0 plan — Task 2 only *extends* `TinyDecoderCfg` with defaulted fields (backward-compatible). (b) Phase 1 corpora fit within `context_len` (single-forward overfit; oversize raises `PackError`), consistent with ARCHITECTURE's "small repos" assumption; chunking is out of scope. (c) An `ArtifactStore` adapter is not required in Phase 1 — `Packer` falls back to `PakWriter` under `cfg.out_dir`; when Phase 4 injects `ports.store`, `put_pak` is used unchanged. (d) Manifest `created_utc` is the sole non-deterministic field (wall-clock); the determinism gate asserts on weights/residuals/tokenizer bytes, and a Phase 0 `Clock` port can make even the timestamp reproducible in services.
