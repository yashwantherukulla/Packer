# Packer — Roadmap

> Seven phases, 0 → 6. Each phase has a **goal**, **dependencies**, **deliverables**, and a **milestone gate** (the objective condition that lets you call it done). Detailed scope/interfaces/testing/dev-steps/acceptance live in the matching [phase spec](specs/).

---

## Phase map

```
Phase 0  Foundations ─────────────┬──────────────┬───────────────┐
(scaffold, toolchain, .pak spec)   │              │               │
                                   ▼              ▼               │
Phase 1  Packer (Part 1) ──────────┴──▶ Phase 2  Detector (Part 2)│
(overfit tiny decoder, lossless)   │    (weight-only signals)     │
        │  produces fixtures ──────┘              │               │
        ▼                                         │               │
Phase 3  Extractor + Sandbox (Part 3) ◀───────────┘               │
(reconstruct + static/dynamic scan)                               │
        │                                                         │
        └───────────────┬─────────────────────────────────────────┘
                        ▼
Phase 4  API service ─────────▶ Phase 5  Web UI (Part 4)
(FastAPI + Celery + PG + WS)      (React SPA over the API)
                        │                 │
                        └───────┬─────────┘
                                ▼
                     Phase 6  Integration & Release
                     (full E2E, hardening, deploy, docs)
```

**Dependency notes.** Phase 2 depends on Phase 1 only for *fixtures* (its signals can be developed against control models in parallel, then calibrated once Phase 1 lands). Phase 3's *extraction* depends on the Phase 1 `.pak` format; its *sandbox* is independent and can be built alongside Phase 1/2. Phases 4→5 are the service/UI layer over completed engines. Phase 6 ties everything together.

---

## Phase 0 — Foundations

- **Goal:** an empty but *correct* monorepo — toolchain enforced on commit, config system wired, safe model loading and the `.pak` format defined — so every later phase builds on a stable base.
- **Depends on:** nothing.
- **Deliverables:**
  - **uv project** finalized at the repo root: expand `pyproject.toml` (deps + `[dependency-groups]`), `uv sync`, commit `uv.lock`; `src/packer/` package layout + `frontend/` shell.
  - **ruff (lint + format) + pre-commit + mypy + pytest** configured; pre-commit installed and green. *(This is the first thing built — the user requirement to lint/format on commit.)*
  - GitHub Actions CI (via `setup-uv`): lint → type-check → unit.
  - **Hydra config tree** (`conf/`) with structured-config schemas in `engine/common/`.
  - `engine/common/` (errors, logging, types, progress protocol) and `engine/models/` (safetensors-first loader, tensor iteration, metadata read).
  - **`.pak` artifact format**: manifest schema, reader/writer stubs, residual codec interface — the seam all parts share.
- **Milestone gate:** `pre-commit run --all-files` passes; CI green on an empty PR; a hand-written `.pak` fixture round-trips through the reader/writer; `packer.engine` imports cleanly.

## Phase 1 — Packer (Part 1)

- **Goal:** turn a small repo into a losslessly-reconstructable `.pak` by overfitting a from-scratch tiny decoder.
- **Depends on:** Phase 0.
- **Deliverables:** byte-level BPE tokenizer; repo→corpus serialization with file-boundary markers; tiny causal decoder (config-driven size); overfit training loop (CPU/GPU/cloud, Hydra-configured); teacher-forced **residual capture**; deterministic **unpacker**; byte-exact round-trip verification; size/fidelity metrics written into the manifest. Emits the **known-memorized fixtures** Parts 2–3 need.
- **Milestone gate:** for a sample repo, `pack → unpack` is **byte-identical** (asserted in CI on a small fixture); the manifest records residual ratio and honest size metrics; at least 3 fixtures (memorized) + 2 controls (random-init, normal-trained) exist for downstream calibration.

## Phase 2 — Detector (Part 2)

- **Goal:** decide, **from weights only**, whether a model carries a memorized-corpus signature, with calibrated confidence and evidence.
- **Depends on:** Phase 0; Phase 1 for calibration fixtures.
- **Deliverables:** the five inference-free signals (spectral/RMT, weight-norm, embedding/unembedding structure, effective/stable rank, config/metadata); ensemble scorer; calibration harness fit on Phase-1 fixtures; report generator (verdict + per-signal evidence + confidence). The **no-inference boundary** is enforced by test.
- **Milestone gate:** on the fixture set, the ensemble separates memorized from control models above an agreed accuracy threshold (recorded, not hard-coded as a guarantee); the "forward path is never called" test passes; report renders to JSON + human-readable.

## Phase 3 — Extractor + Sandbox (Part 3)

- **Goal:** reconstruct stored code (exact from `.pak`, best-effort blind) and score it for maliciousness via static + dynamic analysis.
- **Depends on:** Phase 0; Phase 1 (`.pak` format) for exact extraction.
- **Deliverables:** exact extractor (manifest-driven) + blind extractor (heuristic, confidence-labeled); Docker sandbox image + hardened run policy; static scanners (AST/Bandit/Semgrep/YARA/secrets); dynamic capture (syscalls, fs diff, blocked net); combined risk scorer; scan report.
- **Milestone gate:** exact extraction of a Phase-1 `.pak` is byte-identical; the sandbox correctly flags a planted **malicious** fixture as malicious and a **benign** fixture as benign; sandbox containment verified (no-net enforced, escapes attempted in tests fail); risk report renders with evidence.

## Phase 4 — API service

- **Goal:** expose all three engines as asynchronous, observable jobs.
- **Depends on:** Phases 1–3.
- **Deliverables:** FastAPI app; Pydantic wire schemas; Postgres schema + Alembic migrations; Celery workers (`pack/detect/extract/scan`) with GPU/light queue routing; Redis broker + progress pub/sub; WebSocket progress hub; artifact/model/report storage; OpenAPI spec.
- **Milestone gate:** each engine runs end-to-end through its REST endpoint as a background job; progress streams over WebSocket; jobs, artifacts, and reports persist and are queryable; integration tests pass against real Postgres/Redis (testcontainers).

## Phase 5 — Web UI (Part 4)

- **Goal:** an operator console over the API.
- **Depends on:** Phase 4.
- **Deliverables:** React + Vite + TS SPA; screens for **Pack**, **Detect**, **Extract+Scan**, **Jobs**, **Reports**; upload flows; live job progress via WebSocket; report viewers (signal breakdowns, risk findings); typed API client generated from OpenAPI.
- **Milestone gate:** a user can drive each of the three engines from the browser, watch progress live, and read the resulting report; Playwright E2E covers the three happy paths.

## Phase 6 — Integration & Release

- **Goal:** prove the whole system works together and make it runnable by others.
- **Depends on:** all phases.
- **Deliverables:** full E2E chain (pack → detect → extract → scan → UI) as an automated test; sandbox security hardening pass + documented threat model; performance pass (training/detection timings, queue behavior under load); `docker-compose` for the full stack; operator/run docs; release checklist; nightly E2E CI job.
- **Milestone gate:** the E2E chain (§4 of ARCHITECTURE) passes automatically: a known repo is packed, detected, byte-exactly extracted, and a planted malicious sample is caught — all through the UI; `docker-compose up` brings the full stack online from a clean checkout.

---

## Suggested delivery order & parallelism

1. **Phase 0** (serial — everyone waits on it).
2. **Phase 1**, with **Phase 2 signals** and **Phase 3 sandbox** started in parallel against control/synthetic fixtures.
3. Converge: **Phase 2 calibration** and **Phase 3 exact extraction** once Phase 1 fixtures exist.
4. **Phase 4** (API) then **Phase 5** (UI).
5. **Phase 6** (integration/release).

## Requirement → phase traceability

| Part | Phase(s) |
|---|---|
| Part 1 — Packer | 1 (engine), 4 (API), 5 (UI) |
| Part 2 — Detector | 2 (engine), 4 (API), 5 (UI) |
| Part 3 — Extractor + Sandbox | 3 (engine), 4 (API), 5 (UI) |
| Part 4 — Web UI | 5 |
| Foundations / cross-cutting | 0 |
| Integration / release | 6 |
