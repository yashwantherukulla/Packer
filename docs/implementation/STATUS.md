# Status

**Current branch:** `phase-5-web-ui`
**Current phase:** Phase 5 — Web UI
**Last updated:** 2026-07-09

Legend: ✅ done · 🚧 in progress · ⬜ not started

## Phases

| Phase | Name | State |
|-------|------|-------|
| 0 | Foundations (toolchain + shared kernel + `.pak` format) | ✅ |
| 1 | Packer (tiny decoder, trainer, lossless pack) | ✅ |
| 2 | Detector (inference-free weight signals) | ✅ |
| 3 | Extractor + Sandbox | ✅ |
| 4 | API (FastAPI + Celery + Postgres) | ✅ |
| 5 | Web UI (React SPA) | 🚧 |
| 6 | Integration & Release | ⬜ |

## Phase 5 — Web UI tasks

Plan: [`docs/plans/2026-07-07-phase-5-web-ui.md`](../plans/2026-07-07-phase-5-web-ui.md)

1 scaffold (Vite+TS+Tailwind+shadcn) + routing shell + dev proxy ✅ · 2 generated OpenAPI client + CI drift check ✅ · 3 verdict/risk color scale + formatters ✅ · 4 WebSocket progress client (reconnect+backoff) ⬜ · 5 Query provider + useJob/useJobs/useReport/useArtifact + useSubmit* ⬜ · 6 useJobProgress (WS live + Query polling fallback) ⬜ · 7 Uploader ⬜ · 8 JobProgress ⬜ · 9 VerdictBadge + SignalBreakdown ⬜ · 10 FindingsTable + BehaviorPanel ⬜ · 11 ReportView (kind-branch) + PackResultCard ⬜ · 12 pages Pack + Jobs ⬜ · 13 pages Detect + ExtractScan + Report ⬜ · 14 Playwright E2E (three happy paths) ⬜

## Phase 4 — API tasks

Plan: [`docs/plans/2026-07-07-phase-4-api.md`](../plans/2026-07-07-phase-4-api.md)

1 packages+deps+Hydra settings+app factory ✅ · 2 SQLAlchemy 2.0 models+session factory ✅ · 3 Alembic baseline migration ✅ · 4 repo protocols+SQL repos+in-memory fakes ✅ · 5 Pydantic wire schemas ✅ · 6 JobService (create/get/list/transition+dedup) ✅ · 7 error mapping (PackerError→problem+json) ✅ · 8 Celery app+broker config+queue routing ✅ · 9 RedisProgress bridge ✅ · 10 run_engine_job wrapper+4 one-liner tasks ✅ · 11 FilesystemArtifactStore+composition DI root ✅ · 12 submit routers (/pack /detect /extract /scan) ✅ · 13 read routers (/jobs /models /artifacts /reports) ✅ · 14 WebSocket hub + WS /ws/jobs/{id} ✅ · 15 integration+API-E2E suites (testcontainers) ✅ (skip: no daemon)

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

## Phase 3 — Extractor + Sandbox tasks

Plan: [`docs/plans/2026-07-07-phase-3-extractor-sandbox.md`](../plans/2026-07-07-phase-3-extractor-sandbox.md)

1 Docker image ✅ (build=integration) · 2 sandbox value objects + config ✅ · 3 DockerSandboxRunner ✅ · 4 containment tests ✅ (skip: no daemon) · 5 DynamicAnalyzer ✅ · 6 AST scanner ✅ · 7 bandit+semgrep scanners ✅ (semgrep degrades on Win) · 8 yara+secrets scanners ✅ · 9 StaticAnalyzer (registry-driven) ✅ · 10 Extraction VOs + InferenceModel + ExactExtractor ✅ · 11 BlindExtractor ✅ · 12 ExtractionService ✅ · 13 RiskScorer + calibration ✅ · 14 ScanReportBuilder + ScanPipeline (E2E) ✅ (E2E skip: no daemon)

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
| 2 | Pack config extension (Phase-1 fields) | ✅ |
| 3 | `MarkerCorpusSerializer` + `SerializedCorpus` | ✅ |
| 4 | `ByteBPETokenizer` (`byte-bpe`) | ✅ |
| 5 | `TinyDecoder` + `TinyDecoderArch` (`tiny-decoder`) | ✅ |
| 6 | `OverfitTrainer` | ✅ |
| 7 | `DeltaVarintCodec` + `ResidualCapturer` (`delta-varint-v1`) | ✅ |
| 8 | `InferenceModel` + `TeacherForcedGreedy` + `Unpacker` | ✅ |
| 9 | `unpack(pak_path)` / `unpack_bundle` | ✅ |
| 10 | `Packer` orchestrator + verify gate + honest metrics | ✅ |
| 11 | Property-based round-trip gates | ✅ |
| 12 | Fixture generator (≥3 memorized + ≥2 controls) | ✅ |
