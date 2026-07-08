# Packer — Implementation Plans

Seven task-by-task, test-driven implementation plans — one per phase of the [ROADMAP](../ROADMAP.md). Each plan is self-contained: it assumes zero prior context, lists exact files, shows the real test **and** implementation code for every step, and ends each task with an independently testable deliverable and a Conventional Commit.

All plans conform to the interfaces fixed in [SYSTEM-DESIGN.md](../SYSTEM-DESIGN.md) and build on the shared kernel established in Phase 0.

## The plans

| # | Plan | Builds | Tasks |
|---|------|--------|-------|
| 0 | [Foundations](2026-07-07-phase-0-foundations.md) | uv project, toolchain (ruff/mypy/pytest/import-linter), Hydra, the shared kernel (errors, ports, `Registry`, types), `models/` loader + `WeightAccessor`, the `.pak` format | 12 |
| 1 | [Packer](2026-07-07-phase-1-packer.md) | from-scratch tiny decoder, byte-BPE tokenizer, corpus serializer, overfit trainer, residual capture, shared `Unpacker`/decode, lossless `Packer.pack` | 12 |
| 2 | [Detector](2026-07-07-phase-2-detector.md) | five inference-free weight signals, ensemble + calibration, the shared `engine/report/` model, `Detector.detect`, the no-inference gate | 12 |
| 3 | [Extractor + Sandbox](2026-07-07-phase-3-extractor-sandbox.md) | exact + blind extraction (reusing Phase-1 `Unpacker`), Docker sandbox runner + containment gate, five scanners, risk scorer, `ScanPipeline` | 14 |
| 4 | [API](2026-07-07-phase-4-api.md) | FastAPI app, Pydantic schemas, Postgres + repositories + Alembic, Celery tasks over one `run_engine_job` wrapper, Redis progress + WebSocket hub, DI root | 15 |
| 5 | [Web UI](2026-07-07-phase-5-web-ui.md) | React + Vite + TS SPA, generated API client, live job progress, one `ReportView` for both report kinds, Playwright happy paths | 14 |
| 6 | [Integration & Release](2026-07-07-phase-6-integration-release.md) | the full E2E chain, adversarial sandbox containment, `docker-compose` full stack, performance baselines, nightly E2E CI | 13 |

## Execution order & dependencies

Build **0 → 1 → 2 → 3 → 4 → 5 → 6**. Phase 2 depends on Phase 1 only for calibration fixtures (its signals develop against controls in parallel); Phase 2 also creates the shared `engine/report/` model that Phase 3 reuses. Phase 3's exact extractor reuses Phase 1's `Unpacker`. See the [ROADMAP](../ROADMAP.md#suggested-delivery-order--parallelism) for the parallelism map.

## How to execute a plan

Each plan's header names the sub-skill. Two options:

- **Subagent-driven (recommended):** dispatch a fresh subagent per task with a two-stage review between tasks — `superpowers:subagent-driven-development`.
- **Inline:** batch execution with checkpoints in one session — `superpowers:executing-plans`.

Steps use `- [ ]` checkboxes for tracking. The first action of Phase 0 is standing up `uv` + `ruff` + `pre-commit`, so lint/format-on-commit is live before any product code.

## A note on incremental `import-linter` contracts

The Dependency-Rule contracts are introduced **incrementally** as their modules come into existence (import-linter requires referenced modules to exist): Phase 0 registers the framework-agnostic forbidden contract + a minimal layering; Phases 2–4 extend it (detect no-inference, the `docker` adapter carve-out, and the `extract`/`sandbox`/`api` layers), always preserving the relative order. The canonical end-state lives in [DEVELOPMENT.md §3.1](../DEVELOPMENT.md); never make `pack`/`extract`/`sandbox` mutually independent (they share the DRY reuse edges).
