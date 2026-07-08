# Packer — Development Guide

> How to set up, configure, lint, test, and run everything. The config-file contents below are the **canonical source** — Phase 0 creates these files verbatim (or close to it). Until Phase 0 runs, treat this as the spec for the toolchain.

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| **uv** | 0.9+ | **The** project + environment manager. Owns the venv, dependencies, and lockfile — used for *everything* Python. Install per astral docs. |
| Python | **3.10.x** (pinned via `.python-version`) | Managed by uv (`uv python install 3.10`); you don't install it yourself. 3.10 chosen so every wheel (torch, semgrep, yara-python, …) is available. Windows-native is the primary dev target (ADR-004). |
| Node.js | 20 LTS+ | Frontend (Phase 5). |
| Docker Desktop | current | Required for the Part 3 sandbox and full-stack compose. WSL2 backend is fine but not assumed by host code. |
| Git | current | Repo is git-managed; pre-commit hooks run on commit. |
| CUDA (optional) | matching your PyTorch build | For GPU training in Part 1. CPU-only works for small corpora. |

Postgres and Redis are **not** installed on the host — they run via `docker-compose` in dev (Phase 4+).

---

## 2. One-time setup

The project is a **root-level uv project** (`pyproject.toml`, `.venv/`, `.python-version`, and `uv.lock` all live at the repo root). uv creates and manages the virtual environment for you — never `pip install` or `python -m venv` by hand.

```powershell
# from repo root — uv reads pyproject.toml + uv.lock and materializes .venv
uv sync                          # installs runtime + dev deps into .venv (creates it if needed)
uv run pre-commit install        # enable lint/format on every commit
```

`uv run <cmd>` executes inside the managed environment without an explicit activate step. (You *may* `.\.venv\Scripts\Activate.ps1` for an interactive shell, but `uv run` is the canonical path and what CI uses.)

Frontend (Phase 5+):
```powershell
cd frontend
npm install
```

Verify the toolchain:
```powershell
uv run pre-commit run --all-files   # ruff lint + format + mypy + hygiene hooks
uv run pytest tests/unit            # fast unit suite
```

---

## 3. Toolchain configuration (canonical)

### 3.1 `pyproject.toml` (repo root, uv-managed)

Extends the uv-generated file. Runtime deps go in `[project.dependencies]` (managed with `uv add`); dev tools in the uv-native `[dependency-groups]` (managed with `uv add --dev`) and installed by default on `uv sync`. `uv.lock` is committed for reproducible installs.

```toml
[project]
name = "packer"
version = "0.1.0"
description = "Store code in overfit transformer weights; detect and sandbox it."
readme = "README.md"
requires-python = ">=3.10,<3.11"
dependencies = [
  "torch>=2.2",
  "safetensors>=0.4",
  "huggingface-hub>=0.23",
  "transformers>=4.41",
  "tokenizers>=0.19",
  "numpy>=1.26",
  "scipy>=1.12",
  "hydra-core>=1.3",
  "omegaconf>=2.3",
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7",
  "celery>=5.4",
  "redis>=5.0",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "psycopg[binary]>=3.1",
  "docker>=7.1",           # drives the sandbox
  "bandit>=1.7",
  "semgrep>=1.75",
  "yara-python>=4.5",
]

# uv-native dev dependency group (installed by default with `uv sync`)
[dependency-groups]
dev = [
  "ruff>=0.5",
  "mypy>=1.10",
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5.0",
  "hypothesis>=6.100",     # property-based round-trip tests (residual codec)
  "httpx>=0.27",           # API tests
  "testcontainers>=4.5",   # Postgres/Redis in integration tests
  "import-linter>=2.0",    # enforces the Dependency Rule (SYSTEM-DESIGN §10)
  "pre-commit>=3.7",
]

# Packaged src layout so `import packer` works; hatchling is uv's default build backend.
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/packer"]

# ---------------- ruff (lint + format) ----------------
[tool.ruff]
line-length = 100
target-version = "py310"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "C4", "PTH", "RUF"]
# E/F pycodestyle+pyflakes, I isort, N naming, UP pyupgrade,
# B bugbear, SIM simplify, C4 comprehensions, PTH pathlib, RUF ruff-specific
ignore = ["E501"]          # line length handled by the formatter

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]      # asserts allowed in tests

[tool.ruff.format]
quote-style = "double"
docstring-code-format = true

# ---------------- mypy ----------------
[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true
disallow_untyped_defs = true
plugins = []
# Third-party libs without stubs are ignored per-module in tool.mypy.overrides.

# ---------------- pytest ----------------
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"
markers = [
  "unit: fast, no external services",
  "integration: needs Postgres/Redis/Docker (testcontainers)",
  "e2e: full stack",
  "gpu: requires CUDA",
]

# ---------------- import-linter (Dependency Rule, SYSTEM-DESIGN §10) ----------------
# This is the FINAL, all-phases end-state. import-linter requires every referenced
# module to exist, so the contracts are introduced INCREMENTALLY as modules land —
# always preserving the relative order shown here:
#   Phase 0 : "engine is framework-agnostic" (without `docker`) + a minimal
#             layering of the modules that exist (models|artifacts > common).
#   Phase 2 : add "detect runs no inference"; extend layering with detect + report.
#   Phase 3 : add `docker` to the forbidden list + the adapter `ignore_imports`
#             carve-out; add extract (above pack) and sandbox (above extract).
#   Phase 4 : add `packer.api` on top of the engine layering.
# NEVER make pack/extract/sandbox mutually independent — extract imports pack and
# sandbox imports extract (the DRY reuse edges, SYSTEM-DESIGN §4).
[tool.importlinter]
root_package = "packer"

[[tool.importlinter.contracts]]
name = "engine is framework-agnostic"
type = "forbidden"
source_modules = ["packer.engine"]
forbidden_modules = ["packer.api", "packer.workers", "docker", "redis", "sqlalchemy", "fastapi", "celery"]
# the ONE sanctioned adapter edge: the Docker sandbox runner may import docker
ignore_imports = ["packer.engine.sandbox.adapters.docker -> docker"]

[[tool.importlinter.contracts]]
name = "detect runs no inference"
type = "forbidden"
source_modules = ["packer.engine.detect"]
forbidden_modules = ["torch.nn.functional"]   # + a behavioral test asserts forward/generate is never called

[[tool.importlinter.contracts]]
name = "clean layering"          # high -> low; higher layers may import lower ones
type = "layers"
layers = [
  "packer.api",
  "packer.engine.sandbox",
  "packer.engine.extract",
  "packer.engine.pack | packer.engine.detect",
  "packer.engine.models | packer.engine.artifacts | packer.engine.report",
  "packer.engine.common",
]
# NB: `packer.workers` is intentionally omitted from the layered contract. It is a
# peer of `api` that imports `api.jobs`/`api.db` (repositories); its engine-purity is
# still enforced by the "engine is framework-agnostic" forbidden contract above.
```

### 3.2 `.pre-commit-config.yaml` (repo root)

Runs on every commit; also runnable manually with `pre-commit run --all-files`.

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff            # lint, autofix
        args: [--fix]
      - id: ruff-format     # format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: ["pydantic>=2.7"]
        files: ^src/
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=1024]   # keep weights/artifacts out of git
      - id: check-merge-conflict
      - id: detect-private-key
```

> **Requirement satisfied:** ruff lint **and** format run on commit via the two `ruff-pre-commit` hooks; this is the first thing enabled in Phase 0.

### 3.3 CI — `.github/workflows/ci.yml` (shape)

```yaml
name: ci
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { enable-cache: true }
      - run: uv sync                       # installs from uv.lock; provisions Python 3.10
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src
      - run: uv run lint-imports          # Dependency Rule (SYSTEM-DESIGN §10)
      - run: uv run pytest tests/unit --cov=packer
  integration:
    runs-on: ubuntu-latest   # Docker available on the runner; testcontainers spins Postgres/Redis
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { enable-cache: true }
      - run: uv sync
      - run: uv run pytest tests/integration -m integration
  # e2e runs on a nightly schedule / pre-release, not every PR (Phase 6).
```

> uv provisions the pinned Python itself from `.python-version`, so no separate `setup-python` step is needed. `--frozen` can be added to `uv sync` in CI to fail if the lockfile is stale.

---

## 4. Configuration system — Hydra (ADR-012)

Hydra owns **all** configuration. Pydantic is only for API request/response validation.

### 4.1 Config tree

```
conf/                           # repo root
├── config.yaml                 # root; declares defaults list
├── engine/
│   ├── pack/tiny_decoder.yaml  # arch (n_layers,d_model,...), training (epochs,lr,batch), tokenizer
│   ├── detect/ensemble.yaml    # signal weights, calibration params, thresholds
│   ├── extract/default.yaml    # decode strategy, blind-mode heuristics
│   └── sandbox/docker.yaml     # image, run flags, resource caps, timeout
├── api/service.yaml            # host, port, CORS, ws settings
├── db/postgres.yaml            # dsn (env-interpolated), pool sizes
├── broker/redis.yaml           # broker/result urls, progress channel prefix
└── logging/default.yaml        # level, json vs. console, correlation-id fields
```

`config.yaml` composes them:
```yaml
defaults:
  - engine/pack: tiny_decoder
  - engine/detect: ensemble
  - engine/extract: default
  - engine/sandbox: docker
  - api: service
  - db: postgres
  - broker: redis
  - logging: default
  - _self_

run_dir: ${oc.env:PACKER_RUN_DIR,./outputs}
```

### 4.2 Structured configs (type safety)

Dataclasses in `src/packer/engine/common/config_schema.py` mirror each group and are registered in a `ConfigStore`, so composition is type-checked and IDE-navigable:

```python
from dataclasses import dataclass, field
from hydra.core.config_store import ConfigStore

@dataclass
class TinyDecoderCfg:
    n_layers: int = 6
    d_model: int = 256
    n_heads: int = 4
    vocab_size: int = 8192
    context_len: int = 1024
    epochs: int = 200
    lr: float = 3e-4
    batch_size: int = 8
    device: str = "auto"          # auto | cpu | cuda

@dataclass
class SandboxCfg:
    image: str = "packer-sandbox:latest"
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    network: str = "none"

cs = ConfigStore.instance()
cs.store(group="engine/pack", name="tiny_decoder", node=TinyDecoderCfg)
cs.store(group="engine/sandbox", name="docker", node=SandboxCfg)
# ...one registration per group
```

### 4.3 Overrides

- Training run with overrides: `uv run python -m packer.engine.pack.train engine/pack.epochs=500 engine/pack.device=cuda`
- Services load a **composed** config at startup (via Hydra's Compose API) rather than reading scattered env vars; secrets (DB password, etc.) enter through env interpolation `${oc.env:...}`.

---

## 5. Running things locally

### 5.1 Full stack (Phase 4+)

```powershell
docker compose -f docker/compose.dev.yml up --build
# brings up: postgres, redis, api (uvicorn), worker-light, worker-gpu(optional), frontend(dev)
```

Then:
- API + OpenAPI docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

### 5.2 Engine directly (no services, for development)

```powershell
# Part 1: pack a repo
uv run python -m packer.engine.pack.train data=./samples/toy_repo engine/pack.epochs=300

# Part 2: detect on a model
uv run python -m packer.engine.detect.run model=./outputs/example.pak

# Part 3: extract + scan
uv run python -m packer.engine.extract.run model=./outputs/example.pak
```

*(These module entrypoints exist for development/testing convenience and take Hydra overrides; per ADR-010 they are **not** a supported public CLI.)*

### 5.3 The sandbox image

```powershell
docker build -t packer-sandbox:latest docker/sandbox
```
Never run extracted code outside this image. The runner (`engine/sandbox/runner.py`) always applies the hardened flags from `engine/sandbox/docker.yaml`.

---

## 6. Testing

| Suite | Command | Needs |
|---|---|---|
| Unit | `uv run pytest tests/unit` | nothing |
| Integration | `uv run pytest tests/integration -m integration` | Docker (testcontainers spins Postgres/Redis + sandbox) |
| E2E | `uv run pytest tests/e2e -m e2e` | full stack |
| Frontend unit | `npm run test` (Vitest) | Node |
| Frontend E2E | `npm run e2e` (Playwright) | running stack |

**Non-negotiable gates** (enforced in CI):
- Part 1 round-trip is byte-exact (property-based test over arbitrary byte inputs).
- Part 2 never runs inference (test monkeypatches the forward path to raise; the Detector must still complete).
- Part 3 sandbox containment (network attempt from inside must fail; escape attempts fail).

---

## 7. Conventions

- **Branching:** trunk-based; short-lived feature branches; PRs must pass `quality` + `integration` CI.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`). One logical change per commit.
- **Dependencies (uv only):** add runtime deps with `uv add <pkg>` and dev tools with `uv add --dev <pkg>`; never hand-edit `[project.dependencies]` or `pip install` into the env. **Commit `uv.lock`** with the change so installs are reproducible; CI runs `uv sync --frozen`.
- **Types:** mypy strict; public engine functions are fully typed. The engine takes a `ProgressCallback` and returns typed dataclasses/Pydantic models — no bare dicts across module boundaries.
- **No business logic in API routes.** Routes validate → enqueue → return. All ML/analysis lives in `packer.engine`.
- **Safety:** safetensors-only loading by default; `--allow-pickle` (or config `models.allow_pickle=true`) is required and warns. Extracted code only ever executes in the sandbox.
- **Secrets:** never committed; injected via env → Hydra interpolation. `detect-private-key` pre-commit hook guards against accidents.
- **File size:** the `check-added-large-files` hook (1 MB) keeps weights/`.pak`/datasets out of git; those live in the object-store volume and are gitignored.
