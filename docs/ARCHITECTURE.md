# Packer — System Architecture

> **Audience:** any developer picking this project up to implement it.
> **Status:** design approved 2026-07-07; implementation not started.
> **Companion docs:** [SYSTEM-DESIGN](SYSTEM-DESIGN.md) (module/class interaction, a step above code) · [ROADMAP](ROADMAP.md) · [DEVELOPMENT](DEVELOPMENT.md) · [DECISIONS](DECISIONS.md) · [phase specs](specs/)

---

## 1. What Packer is

Packer is a monorepo research platform built around a single thesis and its security fallout:

> **A transformer decoder, overfit hard enough, will memorize an entire code repository verbatim. The trained weights therefore *are* a container for that code — and anyone who can read weights can, in principle, get the code back out.**

The platform is four cooperating parts, which correspond to the "produce → detect → verify → operate" lifecycle of that idea:

1. **Packer (Part 1) — the producer.** Trains a *from-scratch* tiny decoder to memorize a repo and emits a self-contained, losslessly reconstructable artifact (`.pak`).
2. **Detector (Part 2) — the static analyst.** Given any HF-compatible model, decides **from weights alone (no inference)** whether it carries the statistical fingerprint of a memorized corpus, and reports why.
3. **Extractor + Sandbox (Part 3) — the dynamic analyst.** Reconstructs the stored code via inference, then runs it in a hardened Docker sandbox and scores it for maliciousness (static + dynamic).
4. **Web UI (Part 4) — the console.** A FastAPI + React app that runs all three as asynchronous jobs with live progress and stored reports.

The parts form a validation loop familiar from adversarial ML: **Part 1 generates ground truth** (models known to contain code) that **Parts 2 and 3 must correctly flag and extract.** Control models (random-init, and normally-trained-but-not-memorized) are the negative fixtures.

---

## 2. Design principles

| Principle | Consequence in this codebase |
|---|---|
| **One engine, many faces** | All product logic lives in an importable Python package (`packer.engine.*`). The FastAPI service is a thin async wrapper. No business logic in route handlers. |
| **Lossless is non-negotiable** | Part 1 always produces byte-exact round-trips via a residual-patch mechanism (§5.2). Fidelity of the *model* is a metric, not a correctness condition. |
| **No-inference wall in Part 2** | The Detector must never call `model.forward()` or generate. It reads tensors and metadata only. This is a hard architectural boundary, enforced in tests. |
| **Untrusted by default** | Any model file may be adversarial; any extracted code may be malware. Safetensors-first loading, and all code execution is sandboxed. |
| **Honest reporting** | Every score carries a confidence and its supporting evidence. Heuristic signals are labeled as heuristic. We never claim proof we don't have. |
| **Config is data, not code** | Hydra composes all runtime configuration; nothing hyperparameter-like is hardcoded. |
| **Small, testable units** | Each signal, scanner, and engine step is independently unit-testable behind a narrow interface. |

---

## 3. Component architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Part 4)                                                          │
│  React + Vite + TS · TanStack Query · WebSocket client                       │
│  screens: Pack · Detect · Extract+Scan · Jobs · Reports                      │
└───────────────┬──────────────────────────────────────────────┬─────────────┘
                │ REST (OpenAPI)                                 │ WS (progress)
┌───────────────▼──────────────────────────────────────────────▼─────────────┐
│  API SERVICE                                                                 │
│  FastAPI · Pydantic v2 schemas · WebSocket hub · Hydra-loaded settings       │
│  routers: /pack /detect /extract /scan /jobs /models /artifacts /reports     │
│                                                                              │
│      enqueue ▼ (Celery)                 ▲ progress events (Redis pub/sub)     │
├──────────────┼──────────────────────────┼───────────────────────────────────┤
│  WORKERS (Celery)                                                            │
│  tasks: pack.run · detect.run · extract.run · scan.run                       │
│  each task imports and calls the engine directly, emits progress to Redis    │
└──────────────┬───────────────────────────────────────────────┬──────────────┘
               │ imports                                         │ drives
┌──────────────▼──────────────────────────┐      ┌──────────────▼──────────────┐
│  ENGINE  (packer.engine)                 │      │  SANDBOX (Docker)            │
│  ┌────────────┐ ┌────────────┐           │      │  rootless · --network=none   │
│  │ pack/      │ │ detect/    │  Part 1&2 │      │  read-only · mem/cpu/pids    │
│  │ extract/   │ │ sandbox/   │  Part 3   │      │  capped · non-root · seccomp │
│  └────────────┘ └────────────┘           │      │  runs extracted code,        │
│  shared: models/ artifacts/ report/      │◄─────┤  captures syscalls + fs diff │
│          common/ (config,log,errors,types)│      └──────────────────────────────┘
└──────────────┬───────────────────────────┘
               │ reads/writes
┌──────────────▼───────────────────────────────────────────────────────────────┐
│  STATE                                                                        │
│  PostgreSQL (jobs, models, artifacts, reports metadata)                       │
│  Redis (Celery broker/result backend + progress pub/sub)                      │
│  Object store (filesystem volume in dev): .pak artifacts, uploaded models     │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 The engine package (`packer.engine`)

The engine is where all four parts' logic lives. It has **no knowledge of HTTP, Celery, or the database** — it takes inputs, does work, calls a progress callback, and returns typed results. This keeps it unit-testable and reusable.

```
packer/engine/
├── common/         # config schemas, logging, error taxonomy, shared types, progress callback protocol
├── models/         # safetensors-first loading of local + HF models; tensor iteration; metadata read
├── artifacts/      # the .pak container: writer, reader, manifest schema, residual codec
├── pack/           # Part 1: tokenizer, corpus serialization, tiny decoder, overfit trainer, residual capture
├── detect/         # Part 2: inference-free weight signals + ensemble scorer + calibration
├── extract/        # Part 3a: exact (manifest) + blind (heuristic) code reconstruction
├── sandbox/        # Part 3b: docker runner, static scanners, dynamic capture, risk scorer
└── report/         # unified report model (JSON + rendered) shared by detect + scan
```

**Progress protocol.** Long-running engine functions accept a `progress: ProgressCallback` (a `Protocol` in `common/`). In tests it's a no-op or list-recorder; in workers it publishes to Redis. The engine never imports Redis.

### 3.2 The API service (`packer.api`)

Thin. Responsibilities only: validate requests (Pydantic), persist job rows, enqueue Celery tasks, stream progress over WebSockets, and serve reports/artifacts. Route handlers contain **no** ML or analysis logic.

```
packer/api/
├── main.py            # app factory, Hydra settings load, lifespan (db/redis pools)
├── routers/           # pack, detect, extract, scan, jobs, models, artifacts, reports, ws
├── schemas/           # Pydantic request/response models (the wire contract)
├── jobs/              # job service: create/query, status transitions, dedup
├── ws/                # WebSocket hub; subscribes to Redis progress channels, fans out to clients
├── db/                # SQLAlchemy models, session, Alembic migrations
└── deps.py            # FastAPI dependencies (db session, settings, auth stub)
```

### 3.3 Workers (`packer.workers`)

Celery tasks — one per engine entrypoint. A task loads the job's inputs, constructs a Redis-publishing progress callback, calls the engine, writes results/artifacts, and updates the job row. Training (`pack.run`) runs in a worker queue that may be pinned to a GPU host; light tasks (`detect.run`, `scan.run`) run on a default queue. See [DEVELOPMENT](DEVELOPMENT.md) for queue routing.

---

## 4. End-to-end data flow

**Pack (Part 1):**
```
upload repo (zip/dir) ─▶ POST /pack ─▶ job row (queued) ─▶ Celery pack.run
   ─▶ serialize repo → token stream ─▶ train tiny decoder (overfit)
   ─▶ teacher-forced pass → capture residuals ─▶ verify byte-exact round-trip
   ─▶ write .pak (weights + tokenizer + manifest + residuals) to object store
   ─▶ job=done, artifact registered ─▶ WS pushes progress throughout
```

**Detect (Part 2):**
```
model (HF id | uploaded | .pak) ─▶ POST /detect ─▶ Celery detect.run
   ─▶ load weights ONLY (safetensors) ─▶ run each signal (no forward pass)
   ─▶ ensemble + calibrate ─▶ report (verdict, score, per-signal evidence, confidence)
   ─▶ persist report ─▶ WS progress
```

**Extract + Scan (Part 3):**
```
model + (optional .pak manifest) ─▶ POST /extract ─▶ Celery extract.run
   ─▶ reconstruct code:  exact (manifest present) | blind best-effort (foreign model)
   ─▶ POST /scan (or chained) ─▶ Celery scan.run
        ─▶ static pass (AST/Bandit/Semgrep/YARA/secrets) over extracted files
        ─▶ dynamic pass: run each unit in Docker sandbox, capture syscalls + fs diff + net attempts
   ─▶ combined risk report (score + evidence + per-file findings) ─▶ WS progress
```

**The chain that proves the system works** (Phase 6 E2E): pack a known repo → detect flags it → extract returns byte-exact repo → scan classifies a planted malicious sample as malicious and a benign one as benign — all visible in the UI.

---

## 5. Key internal designs

### 5.1 The `.pak` artifact (shared contract)

A `.pak` is a directory (dev) / tar (transport) written by Part 1, read by Part 3, and whose weights are read by Part 2. It is the seam between all parts, so its schema is defined in Phase 0 before anything consumes it.

```
example.pak/
├── model.safetensors      # tiny decoder weights (fp32/fp16; optional quantized variant)
├── tokenizer.json         # byte-level BPE trained on / fitted to the corpus
├── residuals.bin          # compact codec: positions where argmax(model) != true token
└── manifest.json          # everything needed to reconstruct + provenance
```

`manifest.json` (schema versioned):
```jsonc
{
  "pak_version": "1.0",
  "created_utc": "2026-07-07T00:00:00Z",
  "model": { "arch": "tiny-decoder", "n_layers": 6, "d_model": 256, "n_heads": 4,
             "vocab_size": 8192, "context_len": 1024, "param_count": 3_500_000 },
  "corpus": { "n_files": 42, "n_bytes": 180_000, "n_tokens": 61_000,
              "file_map": [ { "path": "src/app.py", "token_start": 0, "token_end": 1200 } ],
              "boundary_scheme": "special-token-v1", "sha256": "…" },
  "decode": { "strategy": "teacher-forced-greedy", "bos_token_id": 1, "length_tokens": 61_000 },
  "residuals": { "count": 87, "ratio": 0.0014, "codec": "delta-varint-v1" },
  "metrics": { "model_bytes": 7_000_000, "artifact_bytes": 7_050_000,
               "original_bytes": 180_000, "gzip_bytes": 48_000,
               "compression_ratio_vs_original": 39.2, "lossless": true }
}
```

Note the metrics block deliberately records `original_bytes` and `gzip_bytes` next to `artifact_bytes` — the artifact is honest about not being a competitive compressor.

### 5.2 Lossless reconstruction via residuals (Part 1)

The model is trained to overfit, but we never *depend* on it reaching 100%. Instead:

- **Pack time:** after training, do one teacher-forced pass over the corpus token stream. At every position `i`, compute `argmax(logits_i)`. Wherever `argmax != true_token_i`, record `(i, true_token_i)` as a residual. Encode residuals compactly (delta-encoded positions + token ids, varint, then entropy-coded).
- **Unpack time (deterministic, self-correcting):** start from BOS. At each step, take the model's `argmax`; if a residual exists for this position, **override** with the residual token. Feed the (now guaranteed-correct) token forward and continue. Because every fed token equals the true token, error never compounds and the output is **exactly** the corpus. Length comes from the manifest.

Result: round-trip is byte-exact regardless of training quality. Fewer residuals = better model = smaller artifact, but correctness is invariant. This is the crux of the "lossless, guaranteed" decision (see [DECISIONS](DECISIONS.md), ADR-006).

### 5.3 Inference-free memorization signals (Part 2)

The Detector runs an **ensemble of weight-only signals**, each returning `{score∈[0,1], confidence∈[0,1], evidence}`. No signal calls the model.

| Signal | Idea | Weight-only? |
|---|---|---|
| **Spectral / RMT** | SVD of attention + MLP matrices; compare empirical singular-value density to Marchenko–Pastur for a random matrix of the same shape; measure heavy-tail exponent (HT-SR "alpha") and count of outlier singular values. Memorization leaves a characteristic spectrum. | ✅ |
| **Weight-norm profile** | Layerwise Frobenius / spectral norms and their growth; memorize-to-fit models inflate norms in specific layers. | ✅ |
| **Embedding / unembedding structure** | Per-token norm distribution of the embedding and LM-head; a corpus-tuned model shows a small set of anomalously weighted tokens and large dead regions. Entropy of that distribution is the signal. | ✅ |
| **Effective / stable rank** | Stable rank (‖W‖_F²/‖W‖₂²) and effective rank per layer vs. typical ranges. | ✅ |
| **Config / metadata heuristics** | Tiny param count, vocab tuned to a small corpus, param-to-vocab ratios, presence of a `.pak`-shaped manifest or tokenizer fitted to few files. | ✅ (metadata) |

The ensemble combines signals with **calibrated** weights (fit on Phase-1 fixtures: memorized positives vs. random-init and normal-trained negatives) and outputs a verdict `MEMORIZED-CODE-LIKELY | INCONCLUSIVE | UNLIKELY` with an overall confidence.

**Scope honesty (critical):** from weights alone, Part 2 detects a *memorization/overfitting signature*, not literally "this is code." It cannot recover the code (that needs inference — Part 3) and cannot, in general, distinguish memorized *code* from memorized *anything*. The report says so explicitly. Part 3 is what confirms and extracts. See [DECISIONS](DECISIONS.md), ADR-007.

### 5.4 Extraction modes (Part 3a)

- **Exact mode** (a `.pak` manifest is available): deterministic reconstruction per §5.2 → byte-exact repo. High confidence.
- **Blind mode** (foreign HF model flagged by Part 2, no manifest): we don't know the decode scheme or file markers. Attempt greedy/low-temperature decode from BOS and from candidate seeds; look for repeated file-boundary patterns; reconstruct candidate files. Reported as **best-effort, low/medium confidence, possibly partial.** We never claim byte-exactness here.

### 5.5 Sandbox and malware scoring (Part 3b)

- **Static pass** (no execution): per extracted file — language detect; AST-level dangerous-construct detection (exec/eval, dynamic import, subprocess, network, obfuscation, encoded blobs); Bandit (Python), Semgrep (multi-language rules), YARA rules, and a secrets/regex sweep. Produces findings with severities.
- **Dynamic pass** (execution in Docker): each runnable unit executes in an ephemeral container — `--network=none`, `--read-only` root with a small `tmpfs` scratch, `--memory`, `--cpus`, `--pids-limit`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root UID, wall-clock timeout. Capture: stdout/stderr, syscall trace (e.g., `strace -f`), filesystem diff of the tmpfs, and blocked network attempts. The container image and run policy are defined in Phase 3.
- **Risk score:** combine static severities + dynamic behaviors into a calibrated `benign | suspicious | malicious` verdict with per-file evidence. Static and dynamic disagreements are surfaced, not hidden.

---

## 6. Technology stack and why

| Layer | Choice | Rationale |
|---|---|---|
| Project/env manager | **uv** (root-level uv project, `uv.lock`) | Single tool for the venv, dependency resolution, locking, and running (`uv sync` / `uv run`); provisions the pinned Python. |
| Language (engine/API) | Python 3.10.x (pinned via `.python-version`) | ML ecosystem; matches PyTorch/transformers; 3.10 chosen for maximum wheel availability across the whole stack. |
| DL framework | PyTorch | From-scratch decoder + full control of training loop; CPU/CUDA/cloud all supported. |
| Model I/O | `safetensors`, `huggingface_hub`, `transformers`, `tokenizers` | Safe (no pickle code-exec) weight loading; byte-level BPE; foreign-model support. |
| Numerics | NumPy, SciPy | SVD / RMT / spectral signals in Part 2. |
| API | FastAPI + Uvicorn + Pydantic v2 | Async, typed, OpenAPI out of the box. |
| Jobs | **Celery + Redis (broker) + Postgres** | Chosen orchestration option **B** — real multi-user async scale, GPU-pinned queues, retries. |
| Realtime | WebSockets + Redis pub/sub | Workers publish progress to Redis; API fans out to WS clients. |
| DB / migrations | PostgreSQL + SQLAlchemy 2.0 + Alembic | Durable job/report/artifact metadata. |
| **Config** | **Hydra (`hydra-core`) + OmegaConf, structured configs** | Single hierarchical config system across engine, training, services, sandbox; CLI/env overrides; typed via dataclasses in `common/`. |
| Sandbox | Docker + `docker` SDK for Python | Portable on Windows (Docker Desktop) / cloud; per-run reset; strong-enough isolation. |
| Static scan | Python `ast`, Bandit, Semgrep, YARA, secrets regex | Multi-language, layered. |
| Frontend | React 18 + Vite + TypeScript, TanStack Query, Tailwind + shadcn/ui | Modern, typed, fast dev; clean job-driven UI. |
| Quality | ruff (lint+format), mypy, pytest, pre-commit, GitHub Actions | Enforced on commit and in CI (see [DEVELOPMENT](DEVELOPMENT.md)). |

Config boundary worth stating once: **Hydra owns configuration** (hyperparameters, paths, service settings, feature flags, sandbox policy). **Pydantic owns the wire contract** (API request/response validation). They don't overlap.

---

## 7. Cross-cutting concerns

- **Configuration (Hydra).** A root-level `conf/` tree with config groups (`engine/pack`, `engine/detect`, `engine/sandbox`, `api`, `db`, `broker`, `logging`). Structured configs (dataclasses registered in a `ConfigStore`) give type-checked composition and IDE support. Services load a composed config at startup; training/CLI-style entrypoints accept Hydra overrides. Full layout in [DEVELOPMENT](DEVELOPMENT.md).
- **Errors.** A small exception taxonomy in `engine/common/errors.py` (`PackerError` base → `LoadError`, `UnsafeModelError`, `PackError`, `ReconstructionError`, `SandboxError`, `ConfigError`). The API maps these to HTTP problem responses; workers record them on the job row.
- **Logging & observability.** Structured logging (JSON in prod) with a per-job correlation id threaded from API → Celery → engine. Job rows capture timing and phase-level progress.
- **Safety posture.** Safetensors-only by default; loading pickle/`.bin` requires an explicit opt-in flag and a warning. All extracted code is treated as hostile and only ever runs in the sandbox — never in a worker or the API process.
- **Auth.** Out of scope for MVP (single-tenant/local), but the API carries an auth dependency stub so it can be added without refactoring routes.

---

## 8. Assumptions, risks, and non-goals

**Assumptions**
- The target repos are "small" (order kilobytes–low megabytes of text) so a tiny decoder can memorize them in feasible time on the available hardware (Windows GPU / CPU / cloud GPU).
- Users have Docker available for Part 3's sandbox and Part 4's full stack (compose).

**Risks (and mitigations)**
- **R1 — Part 1 isn't a real compressor.** Accepted and documented; value is fixtures + demonstration. Mitigation: report sizes honestly; offer quantization/entropy-coding as a stretch; keep LoRA-delta as a future escape hatch.
- **R2 — Inference-free memorization detection is an open research problem.** Part 2 signals are heuristic. Mitigation: ensemble + calibration against Part-1 fixtures; ship confidence + evidence, never bare verdicts; treat accuracy targets as goals to *measure*, not guarantees.
- **R3 — Blind extraction may fail on foreign models.** Mitigation: clearly labeled best-effort; exact mode is the supported path.
- **R4 — Sandbox escape.** Mitigation: defense-in-depth Docker policy (no-net, read-only, caps dropped, non-root, resource + pid + time limits); documented threat model in Phase 3; never execute outside the sandbox.
- **R5 — Training cost / non-convergence on CPU.** Mitigation: size-gated defaults, GPU/cloud queues, and the residual mechanism means a poorly-converged model is still lossless (just a bigger artifact).

**Non-goals (MVP)**
- Beating `gzip`/`zstd` on compression ratio.
- A polished public CLI or pip-installable library (the API + UI is the supported surface; the engine stays importable for tests only).
- Multi-tenant auth/RBAC, billing, horizontal autoscaling.
- Exact recovery of code from arbitrary foreign models with certainty.
- Semantic malware *classification* beyond benign/suspicious/malicious with evidence.

---

## 9. Repository layout

The repo root **is** the uv-managed Python project (ADR-013); `frontend/` is a subdirectory with its own Node toolchain.

```
packer/                          # repo root == the uv Python project
├── pyproject.toml               # uv project: deps + dependency-groups + ruff/mypy/pytest config
├── uv.lock                      # committed lockfile (reproducible installs)
├── .python-version              # pinned Python 3.10
├── .venv/                       # uv-managed (gitignored)
├── .gitignore · .pre-commit-config.yaml
├── .github/workflows/           # ci.yml (per-PR quality+integration) · e2e-nightly.yml (scheduled E2E)
├── README.md
├── docs/
│   ├── ARCHITECTURE.md · ROADMAP.md · DEVELOPMENT.md · DECISIONS.md
│   ├── OPERATIONS.md · RELEASE-CHECKLIST.md · THREAT-MODEL.md · PERFORMANCE.md
│   ├── implementation/          # CHANGELOG.md · STATUS.md (per-commit log)
│   └── specs/ phase-0…6.md · plans/ phase-0…6.md
├── conf/                        # Hydra config tree (engine/*, api, db, broker, store, logging)
├── src/packer/
│   ├── engine/{common,models,artifacts,pack,detect,extract,sandbox,report}/
│   ├── api/{routers,schemas,jobs,ws,db,…}
│   └── workers/
├── tests/{unit,integration,e2e}/   # e2e/ = §6.4 chain + clean-checkout; integration/sandbox = containment gate
├── scripts/perf/                # pack/detect/scan + concurrency/WS-fanout benches → docs/PERFORMANCE.md
├── alembic/                     # migrations (run on api startup, ADR-014)
├── docker/                      # sandbox image, compose.yml (full stack) + compose.dev.yml, api/worker/frontend Dockerfiles, nginx.conf
└── frontend/                    # React + Vite + TS (own package.json)
    └── src/{pages,components,api,hooks,lib}/ · e2e/ (Playwright chain)
```

Per-directory responsibilities and the exact interfaces each module exposes are specified phase-by-phase in [docs/specs/](specs/).

---

## 10. Testing strategy (overview)

Detail lives in each phase spec; the shape is constant:

- **Unit** — every signal, scanner, codec, and engine step in isolation. The residual codec gets property-based round-trip tests (`pack(x)` then `unpack` equals `x` for arbitrary byte inputs).
- **Integration** — engine + real Postgres/Redis (via testcontainers) for the job path; the Docker sandbox against known-benign and known-malicious fixtures.
- **E2E** — the full chain in §4 through the API (httpx) and, in Phase 5/6, through the UI (Playwright).
- **Determinism gates** — Part 1 round-trip must be byte-exact; the no-inference boundary in Part 2 is asserted (the Detector is run with the model's forward path monkeypatched to raise, proving it's never called).
- **Calibration harnesses** — Parts 2 and 3 ship scripts that report accuracy/precision/recall on the fixture set, so detection quality is a tracked metric rather than a claim.

CI runs lint → type-check → unit → integration on every PR; E2E on a nightly / pre-release job. See [DEVELOPMENT](DEVELOPMENT.md).
