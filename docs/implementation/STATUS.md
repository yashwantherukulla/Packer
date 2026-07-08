# Status

**Current branch:** `phase-1-packer`
**Current phase:** Phase 1 — Packer
**Last updated:** 2026-07-08

Legend: ✅ done · 🚧 in progress · ⬜ not started

## Phases

| Phase | Name | State |
|-------|------|-------|
| 0 | Foundations (toolchain + shared kernel + `.pak` format) | ✅ |
| 1 | Packer (tiny decoder, trainer, lossless pack) | 🚧 |
| 2 | Detector (inference-free weight signals) | ⬜ |
| 3 | Extractor + Sandbox | ⬜ |
| 4 | API (FastAPI + Celery + Postgres) | ⬜ |
| 5 | Web UI (React SPA) | ⬜ |
| 6 | Integration & Release | ⬜ |

## Phase 0 — Foundations tasks

Plan: [`docs/plans/2026-07-07-phase-0-foundations.md`](../plans/2026-07-07-phase-0-foundations.md)

| # | Task | State |
|---|------|-------|
| — | Implementation log + branching strategy scaffold | ✅ |
| 1 | uv project → src layout + toolchain config | ✅ |
| 2 | pre-commit hooks | ✅ |
| 3 | CI workflow | ✅ |
| 4 | Error taxonomy (`PackerError`) | ✅ |
| 5 | Progress protocol + implementations | ✅ |
| 6 | Generic `Registry[T]` | ✅ |
| 7 | Value-object types + ports + registry instances | ✅ (ports incremental — see CHANGELOG) |
| 8 | Structured logging + correlation id | ✅ |
| 9 | import-linter contracts (Dependency Rule) | ✅ |
| 10 | Hydra config tree + structured configs + assembler | ✅ |
| 11 | Safetensors loader + `WeightAccessor` | ✅ |
| 12 | `.pak` artifact format (manifest, codec, reader/writer) | ✅ |

### Phase 0 Definition of Done
- ✅ `uv sync` provisions Python 3.10.19; `uv run pre-commit run --all-files` passes (all 10 hooks).
- ✅ `uv run pytest tests/unit` → 27 passed; `uv run mypy src` clean (19 files); `uv run lint-imports` → 2 contracts kept, 0 broken.
- ✅ `import packer.engine` (+ `.common`, `.models`, `.artifacts`) succeed with no side effects.
- ✅ Registry round-trip works; unknown name raises `ConfigError` (`test_registry.py`).
- ✅ `compose_config()` composes root config; overrides apply (`test_config.py`).
- ✅ `HFModelLoader.load` loads a safetensors fixture and refuses `.bin` by default (`test_loader.py`).
- ✅ `PakBundle` round-trips through `PakWriter`/`PakReader` (`test_pak.py`).
- ⏸ CI `quality` job — workflow is valid but not yet exercised (no git remote configured). Runs on first push.

## Phase 1 — Packer tasks

Plan: [`docs/plans/2026-07-07-phase-1-packer.md`](../plans/2026-07-07-phase-1-packer.md)

| # | Task | State |
|---|------|-------|
| 1 | Runtime deps (torch, tokenizers) + pack scaffold + varint | ✅ |
| 2 | Pack config extension (Phase-1 fields) | ⬜ |
| 3 | `MarkerCorpusSerializer` + `SerializedCorpus` | ⬜ |
| 4 | `ByteBPETokenizer` (`byte-bpe`) | ⬜ |
| 5 | `TinyDecoder` + `TinyDecoderArch` (`tiny-decoder`) | ⬜ |
| 6 | `OverfitTrainer` | ⬜ |
| 7 | `DeltaVarintCodec` + `ResidualCapturer` (`delta-varint-v1`) | ⬜ |
| 8 | `InferenceModel` + `TeacherForcedGreedy` + `Unpacker` | ⬜ |
| 9 | `unpack(pak_path)` / `unpack_bundle` | ⬜ |
| 10 | `Packer` orchestrator + verify gate + honest metrics | ⬜ |
| 11 | Property-based round-trip gates | ⬜ |
| 12 | Fixture generator (≥3 memorized + ≥2 controls) | ⬜ |
