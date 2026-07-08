# Status

**Current branch:** `phase-0-foundations`
**Current phase:** Phase 0 — Foundations
**Last updated:** 2026-07-08

Legend: ✅ done · 🚧 in progress · ⬜ not started

## Phases

| Phase | Name | State |
|-------|------|-------|
| 0 | Foundations (toolchain + shared kernel + `.pak` format) | 🚧 |
| 1 | Packer (tiny decoder, trainer, lossless pack) | ⬜ |
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
| 4 | Error taxonomy (`PackerError`) | ⬜ |
| 5 | Progress protocol + implementations | ⬜ |
| 6 | Generic `Registry[T]` | ⬜ |
| 7 | Value-object types + ports + registry instances | ⬜ |
| 8 | Structured logging + correlation id | ⬜ |
| 9 | import-linter contracts (Dependency Rule) | ⬜ |
| 10 | Hydra config tree + structured configs + assembler | ⬜ |
| 11 | Safetensors loader + `WeightAccessor` | ⬜ |
| 12 | `.pak` artifact format (manifest, codec, reader/writer) | ⬜ |

### Phase 0 Definition of Done
- ⬜ `uv sync` provisions Python 3.10.x; `uv run pre-commit run --all-files` passes.
- ⬜ `uv run pytest tests/unit` green; `uv run mypy src` clean; `uv run lint-imports` all contracts kept.
- ⬜ `import packer.engine` (+ `.common`, `.models`, `.artifacts`) succeed with no side effects.
- ⬜ Registry round-trip works; unknown name raises `ConfigError`.
- ⬜ `compose_config()` composes root config; overrides apply.
- ⬜ `HFModelLoader.load` loads a safetensors fixture and refuses `.bin` by default.
- ⬜ `PakBundle` round-trips through `PakWriter`/`PakReader`.
- ⬜ CI `quality` job green.
