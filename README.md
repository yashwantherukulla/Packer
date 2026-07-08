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

## Documentation

Start here, in order:

1. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — the system: components, data flow, the `.pak` format, tech stack, security model, testing strategy, and the assumptions/risks/non-goals that bound the project.
2. **[docs/SYSTEM-DESIGN.md](docs/SYSTEM-DESIGN.md)** — *a step above code:* how modules, classes, and functions interact; the shared kernel, ports/registries, dependency rules, and the extensibility recipes that keep logic from needing rewrites.
3. **[docs/ROADMAP.md](docs/ROADMAP.md)** — the seven phases (0–6), their dependencies, deliverables, and milestone gates.
4. **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — how to set up, lint, test, configure (Hydra), and run every service locally.
5. **[docs/DECISIONS.md](docs/DECISIONS.md)** — the architectural decision record (ADR) log.
6. **[docs/specs/](docs/specs/)** — one detailed spec per phase (scope, interfaces, integration, testing, dev steps, acceptance criteria).
7. **[docs/plans/](docs/plans/)** — the seven task-by-task, test-driven implementation plans (one per phase), ready to execute.

## Status

Planning complete — architecture, per-phase specs, and **task-by-task implementation plans** (see [docs/plans/](docs/plans/)) are all written. Implementation not yet started. The next execution step is **Phase 0 — Foundations** (repo scaffold + toolchain), beginning with enabling `ruff` + `pre-commit`.

## Tech stack (at a glance)

- **Tooling:** [uv](https://docs.astral.sh/uv/) manages the Python project, virtualenv, and lockfile (root-level uv project, Python **3.10.x** pinned via `.python-version` for maximum wheel availability).
- **Engine:** Python 3.10, PyTorch, `safetensors`, HuggingFace `tokenizers`/`transformers`, NumPy/SciPy.
- **Services:** FastAPI, Celery, Redis (broker + pub/sub), PostgreSQL, SQLAlchemy + Alembic, WebSockets.
- **Config:** Hydra (`hydra-core` + OmegaConf, structured configs) — the single config system across engine, training, services, and sandbox.
- **Sandbox:** Docker (rootless, `--network=none`, read-only, resource-capped) driven via the Docker SDK; static scanners (AST, Bandit, Semgrep, YARA) + dynamic syscall/filesystem capture.
- **Frontend:** React 18 + Vite + TypeScript, TanStack Query, Tailwind + shadcn/ui.
- **Quality:** ruff (lint + format), mypy, pytest, pre-commit, GitHub Actions CI.
