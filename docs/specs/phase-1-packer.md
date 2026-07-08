# Phase 1 — Packer (Part 1)

> **Goal:** turn a small repository into a losslessly-reconstructable `.pak` by overfitting a from-scratch tiny transformer decoder.
> **Depends on:** Phase 0. **Blocks:** Phase 2 (fixtures), Phase 3 (exact extraction).
> **Part mapping:** Part 1.

---

## 1. Scope

**In scope**
- Byte-level BPE tokenizer, fit on the target corpus.
- Repo → corpus serialization with reversible file-boundary + path markers.
- From-scratch tiny causal decoder (config-driven size).
- Overfit training loop (CPU / CUDA / cloud), Hydra-configured.
- Teacher-forced **residual capture** and the concrete residual codec.
- Deterministic **unpacker** (self-correcting decode).
- Byte-exact round-trip verification; size/fidelity metrics into the manifest.
- Fixture generation: ≥3 memorized `.pak`s + ≥2 controls (random-init, normal-trained) for Phase 2/3.

**Out of scope**
- Quantization / weight entropy-coding (optional stretch, noted below). LoRA-delta variant (future). Any API/UI (Phases 4–5).

---

## 2. Modules & interfaces

`engine/pack/tokenizer.py`
```python
def train_tokenizer(corpus_bytes: bytes, vocab_size: int) -> "Tokenizer": ...
# byte-level BPE via HF tokenizers; guarantees any byte is representable (lossless-friendly)
```

`engine/pack/corpus.py`
```python
from pathlib import Path

def serialize_repo(root: Path) -> "SerializedCorpus":
    """Walk repo → deterministic ordering → concatenate with file-boundary markers.
    Returns bytes + file_map [(path, byte_start, byte_end)]. Fully reversible."""

def deserialize_repo(data: bytes, file_map: list) -> dict[str, bytes]:
    """Inverse of serialize_repo → {path: file_bytes}."""
```

`engine/pack/model.py`
```python
import torch.nn as nn

class TinyDecoder(nn.Module):
    """Standard decoder-only transformer (causal). Size from TinyDecoderCfg."""
    def forward(self, tokens): ...   # -> logits [B, T, V]
```

`engine/pack/trainer.py`
```python
def train_to_memorize(corpus_tokens, cfg: "TinyDecoderCfg",
                      progress: "ProgressCallback") -> "TinyDecoder":
    """Overfit: no dropout, minimal/zero weight decay, many epochs, teacher forcing.
    Emits progress (epoch, loss, token-accuracy). Device auto/cpu/cuda."""
```

`engine/pack/residuals.py`
```python
def capture_residuals(model, corpus_tokens) -> list[tuple[int, int]]:
    """One teacher-forced pass; return [(position, true_token)] where argmax != true."""

# concrete ResidualCodec: delta-encoded positions + varint token ids (+ optional entropy code)
class DeltaVarintCodec:  # implements engine.artifacts.ResidualCodec
    def encode(self, residuals): ...
    def decode(self, blob): ...
```

`engine/pack/packer.py` (orchestrator)
```python
def pack_repo(root: Path, cfg, progress) -> Path:
    """serialize → tokenize → train → capture residuals → VERIFY round-trip →
    write .pak with honest metrics. Returns artifact path. Raises PackError if
    verification fails."""
```

`engine/pack/unpacker.py`
```python
def unpack(pak_path: Path) -> dict[str, bytes]:
    """Deterministic self-correcting decode (ARCHITECTURE §5.2) → {path: file_bytes}.
    Guaranteed byte-exact vs. original."""
```

---

## 3. Integration points

- **Writes `.pak`** via `engine/artifacts.write_pak` (Phase 0 contract). Manifest `metrics` block must include `original_bytes`, `gzip_bytes`, `model_bytes`, `artifact_bytes`, `compression_ratio_vs_original`, `lossless=true` (ADR-003 honesty).
- **`unpack` is reused verbatim by Phase 3's exact extractor** — build it as a standalone, importable function.
- **Fixtures produced here are Phase 2's calibration set and Phase 3's extraction targets.** Store them under `tests/**/fixtures/` (small ones) or the object-store volume (larger), and document their provenance.
- Training entrypoint takes Hydra overrides (device, epochs, size) for GPU/CPU/cloud (ADR-004).

---

## 4. Testing plan

- **Property-based round-trip (correctness gate):** for arbitrary byte inputs and small synthetic repos, `pack → unpack` is byte-identical. Use Hypothesis. This must hold **even with a deliberately under-trained model** (residuals guarantee it) — test with `epochs=1`.
- **Residual codec:** `decode(encode(r)) == r` for random residual lists; encoded size sane.
- **Corpus serializer:** `deserialize(serialize(repo)) == repo` including nested dirs, binary files, empty files, and paths with unusual characters.
- **Determinism:** fixed seed ⇒ identical residuals + artifact bytes across runs (needed for CI byte-exact assertions).
- **Metrics honesty:** manifest reports `artifact_bytes > gzip_bytes` on a normal repo and the test simply asserts the fields exist and are consistent (not a compression claim).
- **Marker:** heavy training tests marked `gpu`/slow; CI runs a tiny fixture on CPU.

---

## 5. Development steps (ordered)

1. Corpus serializer + inverse (+ tests) — reversible, deterministic ordering.
2. Byte-level BPE tokenizer wrapper (+ vocab from corpus).
3. `TinyDecoder` module (+ shape/forward tests).
4. Training loop with progress + token-accuracy metric.
5. Residual capture + `DeltaVarintCodec`.
6. `unpack` self-correcting decoder.
7. `pack_repo` orchestrator with **mandatory in-process round-trip verification** before writing.
8. Manifest metrics (incl. gzip baseline).
9. Generate + commit fixtures (memorized + controls) with a small script.

---

## 6. Acceptance criteria (milestone gate)

- [ ] `pack → unpack` is byte-identical on a sample repo, asserted in CI on a small fixture.
- [ ] Round-trip holds with `epochs=1` (residual mechanism proven independent of convergence).
- [ ] Manifest records residual ratio and honest size metrics (incl. `gzip_bytes`).
- [ ] ≥3 memorized fixtures + ≥2 controls exist and load via `read_pak` / `load_model`.
- [ ] Training runs on CPU (tiny) and CUDA (via `device=cuda` override) without code change.

---

## 7. Risks

- **Non-convergence / slow training on CPU** → size-gated defaults; residuals keep it correct (bigger artifact, still lossless) — ADR-006.
- **Tokenizer can't represent some byte** → byte-level BPE guarantees full coverage; test on binary files.
- **Non-determinism breaking CI byte-exact checks** → pin seeds, set deterministic torch flags, document.
