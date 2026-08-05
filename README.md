# Packer

**Packer** is a research platform exploring one idea end-to-end: **source code can be stored inside the weights of an overfit transformer decoder** — and the security consequences of that fact.

It has four parts:

| Part | Name | What it does |
|------|------|--------------|
| **1** | **Packer** | Overfits a *from-scratch* tiny transformer decoder so it memorizes a code repository, then writes a self-contained, **losslessly reconstructable** `.pak` artifact. |
| **2** | **Detector** | Given any HuggingFace-compatible model, decides — **using weight analysis only, no inference** — whether the model shows the statistical signature of having memorized a code corpus. Produces a report. |
| **3** | **Extractor + Sandbox** | Runs inference to reconstruct the stored code, then executes it inside a locked-down Docker sandbox and scans it (static + dynamic) for malicious behavior. |
| **4** | **Web UI** | A FastAPI + React console that drives all three engines as asynchronous jobs. |

> **Honest framing:** as a literal *compression* scheme, a from-scratch model that memorizes a repo is usually **larger** than the repo (and larger than `gzip`). Packer's value is (a) a rigorous demonstration of memorization-as-storage and (b) a threat model + fixture generator for the detection and sandboxing work in Parts 2–3. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#8-assumptions-risks-and-non-goals).

> **Research carrier profile:** use Hydra group `engine/pack=research_fixed` for
> memorization experiments. It uses a deterministic one-token-per-byte vocabulary
> and rejects sequences below 256 tokens, preventing learned BPE from collapsing a
> tiny repository into a single token. The legacy service default remains
> `byte-bpe` for compatibility and is not, by itself, a valid research protocol.

## Documentation

Start here, in order:

1. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — the system: components, data flow, the `.pak` format, tech stack, security model, testing strategy, and the assumptions/risks/non-goals that bound the project.
2. **[docs/SYSTEM-DESIGN.md](docs/SYSTEM-DESIGN.md)** — *a step above code:* how modules, classes, and functions interact; the shared kernel, ports/registries, dependency rules, and the extensibility recipes that keep logic from needing rewrites.
3. **[docs/ROADMAP.md](docs/ROADMAP.md)** — the seven phases (0–6), their dependencies, deliverables, and milestone gates.
4. **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — how to set up, lint, test, configure (Hydra), and run every service locally.
5. **[docs/DECISIONS.md](docs/DECISIONS.md)** — the architectural decision record (ADR) log.
6. **[docs/specs/](docs/specs/)** — one detailed spec per phase (scope, interfaces, integration, testing, dev steps, acceptance criteria).
7. **[docs/plans/](docs/plans/)** — the seven task-by-task, test-driven implementation plans (one per phase), ready to execute.

## Quick start

Bring the whole platform up from a clean checkout with Docker:

```bash
docker compose -f docker/compose.yml up --build      # postgres, redis, api, worker, frontend
# add --profile gpu for the CUDA worker
```

- API + OpenAPI docs: http://localhost:8000/docs
- Frontend console: http://localhost:5173

**No GPU? (CPU-only machines).** `pack.run` is routed to a `gpu` queue drained only by
the profiled `worker-gpu`, so on a GPU-less host a submitted pack job would hang. Layer
the CPU overlay so the default worker drains both queues (and don't pass `--profile gpu`):

```bash
docker compose -f docker/compose.yml -f docker/compose.cpu.yml up --build
```

The engine auto-selects CPU (`device: auto` → `cpu` when no CUDA is present). This overlay
also builds CUDA-free `api`/`worker` images (`docker/api.cpu.Dockerfile`,
`docker/worker.cpu.Dockerfile`): PyTorch is installed from the CPU index, so no
`nvidia-*`/`cuda-*`/`triton` wheels are downloaded or shipped — a few GB smaller than the
default images. `pyproject.toml`/`uv.lock` are untouched, so the default build and the
`gpu` profile still ship the CUDA stack.

Dev overlay (live source reload + vite dev server):

```bash
docker compose -f docker/compose.yml -f docker/compose.dev.yml up --build
```

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for configuration, migrations, backups, and log tracing, and [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the local toolchain (uv, ruff, mypy, pytest).

## Status

**All six phases (0–6) are implemented and merged.** Phase 0 (foundations + shared kernel + `.pak` format), Phase 1 (Packer), Phase 2 (Detector), Phase 3 (Extractor + Sandbox), Phase 4 (API), Phase 5 (Web UI), and Phase 6 (integration & release) are complete — see [docs/implementation/STATUS.md](docs/implementation/STATUS.md) and [docs/implementation/CHANGELOG.md](docs/implementation/CHANGELOG.md). The §6.4 pack → detect → extract → scan chain is proven end-to-end through the API and the browser; sandbox containment is a hard adversarial gate; `docker compose up --build` brings the full stack online from a clean checkout; a nightly [`e2e-nightly.yml`](.github/workflows/e2e-nightly.yml) job runs the E2E/containment/Playwright suites against a live stack, separate from the per-PR [`ci.yml`](.github/workflows/ci.yml). Performance-baseline scaffolding lives in [docs/PERFORMANCE.md](docs/PERFORMANCE.md); the sandbox threat model is in [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md); the release gate is [docs/RELEASE-CHECKLIST.md](docs/RELEASE-CHECKLIST.md).

## Tech stack (at a glance)

- **Tooling:** [uv](https://docs.astral.sh/uv/) manages the Python project, virtualenv, and lockfile (root-level uv project, Python **3.10.x** pinned via `.python-version` for maximum wheel availability).
- **Engine:** Python 3.10, PyTorch, `safetensors`, HuggingFace `tokenizers`/`transformers`, NumPy/SciPy.
- **Services:** FastAPI, Celery, Redis (broker + pub/sub), PostgreSQL, SQLAlchemy + Alembic, WebSockets.
- **Config:** Hydra (`hydra-core` + OmegaConf, structured configs) — the single config system across engine, training, services, and sandbox.
- **Sandbox:** Docker (rootless, `--network=none`, read-only, resource-capped) driven via the Docker SDK; static scanners (AST, Bandit, Semgrep, YARA) + dynamic syscall/filesystem capture.
- **Frontend:** React 18 + Vite + TypeScript, TanStack Query, Tailwind + shadcn/ui.
- **Quality:** ruff (lint + format), mypy, pytest, pre-commit, GitHub Actions CI.
