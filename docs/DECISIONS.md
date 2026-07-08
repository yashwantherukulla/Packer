# Packer — Architecture Decision Record (ADR) Log

Each entry records a decision, its context, the alternatives considered, and the consequences. Decisions ADR-001…010 were fixed during the initial design conversation (2026-07-07). Add new ADRs by appending; never rewrite history — supersede with a new entry.

Status legend: **Accepted** · Superseded-by-ADR-NNN · Proposed.

---

## ADR-001 — Project reframed from "backdoor poisoning detector" to "code-in-weights platform"
**Status:** Accepted · 2026-07-07
**Context:** An archived prior project (`old.zip`) scoped Packer as a reference-free LLM *backdoor-poisoning* detector. The new brief is a four-part *code memorization / packing* platform.
**Decision:** Start fresh with the new four-part framing. Salvage the reusable technical material (weight-analysis signal catalog incl. Marchenko–Pastur/RMT, safetensors-only safety stance, subprocess/sandbox isolation instinct, GSD-style phase planning) but do not continue the old requirements or `.planning/` structure.
**Consequences:** Clean docs; the RMT/spectral signal work and the "attack informs detection" loop carry over conceptually. The old zip stays out of the tree (gitignored).

## ADR-002 — Part 1 packing mechanism: train a tiny decoder *from scratch*
**Status:** Accepted · 2026-07-07
**Context:** Options were (a) full-fine-tune a pretrained small code LM, (b) shared frozen base + shippable LoRA/delta, (c) random-init tiny decoder trained purely to memorize.
**Decision:** (c) — from-scratch tiny decoder. Fully self-contained artifact, no external base dependency.
**Consequences:** Simplest self-contained story and cleanest fixture for Parts 2–3. **Downside:** worst raw payload size (see ADR-003). LoRA-delta (b) is retained only as a future efficiency escape hatch, not MVP.

## ADR-003 — Accept that Packer is not a competitive compressor (non-goal)
**Status:** Accepted · 2026-07-07
**Context:** The brief called this an "efficient code transfer" packer. A from-scratch model that memorizes a repo is typically larger than the repo and larger than `gzip`.
**Decision:** Do not pursue beating conventional compression in the MVP. Reframe Part 1's value as (1) a demonstration of memorization-as-storage and (2) a fixture/threat-model generator for Parts 2–3. Record honest size metrics (`original`, `gzip`, `artifact`) in every manifest.
**Consequences:** No false compression claims. Quantization + weight entropy-coding are optional stretch levers; LoRA-delta is the path if efficiency ever becomes primary.

## ADR-004 — Target compute: Windows-native primary, plus CPU-only and cloud GPU; no WSL2 assumption
**Status:** Accepted · 2026-07-07
**Context:** The user runs Windows 11 with an NVIDIA GPU, wants CPU-only fallback, and may burst to cloud GPUs. WSL2 was explicitly not selected.
**Decision:** Support Windows-native (CUDA), CPU-only (small models), and cloud GPU. Design so nothing *requires* WSL2. Docker for the sandbox runs via Docker Desktop.
**Consequences:** Training loop and paths must be Windows-safe (path handling, workers, no Linux-only deps in the hot path). Linux-only tooling is confined to the Docker sandbox image, not the host engine.

## ADR-005 — Corpus unit: whole small repository, language-agnostic
**Status:** Accepted · 2026-07-07
**Context:** Options ranged from single-file to whole-repo, Python-specific to language-agnostic.
**Decision:** Pack a whole small repo (directory tree, multiple files, any language) into one artifact, using a byte-level BPE tokenizer and explicit file-boundary markers.
**Consequences:** The corpus serializer must encode file paths + boundaries reversibly; the manifest carries a `file_map`. Static scanning (Part 3) must be multi-language (hence Semgrep/YARA alongside Python-specific Bandit).

## ADR-006 — Losslessness guaranteed via residual patches
**Status:** Accepted · 2026-07-07
**Context:** A from-scratch overfit model may not reach 100% token accuracy, but a *packer* must return the exact bytes.
**Decision:** Guarantee byte-exact round-trips using a residual mechanism: record every position where the model's `argmax` disagrees with the true token; override during deterministic decode. Correctness is invariant to model quality; model quality only affects artifact size.
**Consequences:** The `.pak` carries a `residuals.bin`. Property-based round-trip tests are a correctness gate. See ARCHITECTURE §5.2.

## ADR-007 — Part 2 is inference-free and reports a *signature*, not a proof
**Status:** Accepted · 2026-07-07
**Context:** The user required "no inference" in Part 2. Inference-free memorization detection is an open research problem.
**Decision:** Part 2 reads weights/metadata only (enforced by a test that makes any forward pass raise). It outputs a calibrated ensemble verdict with confidence + evidence, and states explicitly that it detects a memorization/overfitting *signature* — it cannot recover code or prove the content is code. Part 3 confirms via inference.
**Consequences:** Reports carry confidence and per-signal evidence; accuracy is a *measured* metric on fixtures, not a guarantee. Clear division of labor with Part 3.

## ADR-008 — Part 3 sandbox: Docker, rootless, no-net, resource-capped
**Status:** Accepted · 2026-07-07
**Context:** Extracted code may be malicious by design. Options: Docker, WSL2 microVM/gVisor, pure subprocess, managed cloud sandbox.
**Decision:** Docker container with defense-in-depth: `--network=none`, `--read-only` (+ tmpfs scratch), `--memory`/`--cpus`/`--pids-limit`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root UID, wall-clock timeout. Portable on Windows/cloud, per-run reset.
**Consequences:** Docker is a hard dependency for Part 3 and the full-stack compose. Containment is tested (escape attempts must fail). Static+dynamic (ADR-009) both run against this substrate.

## ADR-009 — Malware analysis: static + dynamic
**Status:** Accepted · 2026-07-07
**Context:** Options were static-only, dynamic-only, or both.
**Decision:** Both. Static (AST heuristics, Bandit, Semgrep, YARA, secrets) over extracted files, plus dynamic behavior capture (syscalls, filesystem diff, blocked network) in the sandbox. Combine into a calibrated risk verdict; surface static/dynamic disagreements.
**Consequences:** More scanners to integrate and keep updated; richer, more trustworthy verdicts.

## ADR-010 — Interfaces: REST API + Web UI only (engine stays internal)
**Status:** Accepted · 2026-07-07
**Context:** Options included shipping a public library + CLI. The user chose API + Web UI only.
**Decision:** The supported product surface is the FastAPI REST API and the React UI. The `packer.engine` package stays a clean, importable internal library (for testability and worker reuse) but is **not** a distribution target and gets no polished CLI.
**Consequences:** No packaging/PyPI work in the MVP; effort concentrates on API + UI. Engine interfaces are still designed as if public (narrow, typed) for testability.

## ADR-011 — Orchestration: Celery + Redis + Postgres + WebSockets (option B)
**Status:** Accepted · 2026-07-07
**Context:** Long-running jobs (training especially). Lightweight (in-process + SQLite) vs. full async (Celery/Redis/Postgres) vs. managed/serverless.
**Decision:** Full async stack — FastAPI + Celery workers + Redis (broker + result + progress pub/sub) + PostgreSQL. Separate queues for GPU-heavy `pack` vs. light `detect`/`scan`. WebSocket progress fanned out from Redis.
**Consequences:** Real multi-user scale, retries, and queue routing; more moving parts and ops (mitigated by `docker-compose`). Integration tests use testcontainers for Postgres/Redis.

## ADR-012 — Configuration: Hydra everywhere
**Status:** Accepted · 2026-07-07
**Context:** The user requested Hydra "for all configs."
**Decision:** Hydra (`hydra-core` + OmegaConf) is the single configuration system across engine, training, services, and sandbox, using **structured configs** (dataclasses registered in a `ConfigStore`) for type safety. Config groups: `engine/pack`, `engine/detect`, `engine/sandbox`, `api`, `db`, `broker`, `logging`. Pydantic is reserved for the **API wire contract** only, not app configuration.
**Consequences:** Uniform overrides (CLI + env interpolation) and composition. Services load a composed config at startup rather than reading scattered env vars directly. Clear Hydra-vs-Pydantic boundary avoids overlap.

## ADR-013 — Tooling: uv, root-level Python project, Python 3.10.x
**Status:** Accepted · 2026-07-07
**Context:** The user requested "use uv for everything" and had already `uv init`-ed a **root-level** project (`.venv/`, starter `pyproject.toml`/`main.py`, `.python-version` initially 3.13). The original design had assumed a `backend/` subdirectory and pip/venv. The user then asked to pin **Python 3.10.x** specifically, to guarantee prebuilt wheels are available for the entire ML/security stack.
**Decision:** uv is the sole Python project/env manager — `uv sync`, `uv run`, `uv add`, committed `uv.lock`; no pip/`python -m venv`. The **repo root is the Python project** (`pyproject.toml`, `src/packer/`, `conf/`, `tests/`, `docker/`, `alembic/` all at root), with `frontend/` as a subdirectory. Target Python is **3.10.x** — pinned via `.python-version` (`3.10`) and bounded by `requires-python = ">=3.10,<3.11"`, provisioned by uv (CPython 3.10.19 at design time). Runtime deps in `[project.dependencies]`; dev tools in uv-native `[dependency-groups]`; hatchling build backend for the `src/` package. ruff `target-version = "py310"`, mypy `python_version = "3.10"`. CI uses `astral-sh/setup-uv` + `uv sync --frozen`.
**Consequences:** Supersedes the earlier `backend/`-subdir assumption and the interim 3.13 pin. Maximum wheel availability (torch, semgrep, yara-python, etc. all ship cp310 wheels) → no source builds. Reproducible installs via the lockfile. Code must remain 3.10-compatible: avoid 3.11+-only features (`tomllib`, exception groups / `except*`, `Self`, the `type` statement). `match`, `X | Y` unions, and PEP 585 generics are all fine on 3.10.
