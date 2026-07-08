# Phase 0 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a correct, enforced monorepo foundation — uv project, full toolchain on commit, the shared kernel (ports, registry, errors, types), safe model loading, and the `.pak` artifact format — so every later phase builds on stable, tested contracts.

**Architecture:** Hexagonal/clean layering (see [SYSTEM-DESIGN.md](../SYSTEM-DESIGN.md)). This phase builds the innermost ring (`engine/common` kernel + `engine/models` + `engine/artifacts`) plus the toolchain and Dependency-Rule enforcement. Everything is TDD; value objects and ports are frozen here because all later phases depend on them.

**Tech Stack:** Python 3.10.x, uv, ruff, mypy (strict), pytest, Hypothesis, import-linter, Hydra + OmegaConf, pydantic v2, safetensors, numpy, huggingface_hub.

## Global Constraints

*Every task's requirements implicitly include this section. Values copied verbatim from the specs/ADRs.*

- **Python 3.10.x only.** `requires-python = ">=3.10,<3.11"`; `.python-version` = `3.10`. No 3.11+ syntax (`tomllib`, `except*`, `Self`, `type` statement). `match`, `X | Y` unions, PEP 585 generics are fine.
- **uv for everything.** Add deps with `uv add` / `uv add --dev`; never `pip install`; commit `uv.lock`. Run via `uv run`.
- **Quality on commit.** ruff (lint + format), mypy strict, import-linter run via pre-commit and CI.
- **Hydra owns all configuration.** Pydantic is for API wire schemas / manifest validation only.
- **safetensors-first.** Loading pickle/`.bin` requires an explicit `allow_pickle=True` opt-in and raises `UnsafeModelError` otherwise.
- **Value objects cross module boundaries; bare `dict`s do not** (except opaque `evidence`/`context`/`config` payloads).
- **The Dependency Rule** (SYSTEM-DESIGN §1/§4): `engine.common` imports nothing else in `packer`; `engine.*` never imports `api`/`workers`/adapters; enforced by import-linter.
- **Conventional Commits**, one logical change per commit.
- **Windows-native is the primary dev target;** use `pathlib`, never hardcode POSIX paths.

## File Structure

```
pyproject.toml                          # expand uv starter: deps, groups, ruff/mypy/pytest/importlinter
.pre-commit-config.yaml                 # ruff, mypy, import-linter, hygiene hooks
.github/workflows/ci.yml                # quality + integration jobs (setup-uv)
conf/                                   # Hydra config tree
  config.yaml
  engine/pack/tiny_decoder.yaml · engine/detect/ensemble.yaml
  engine/extract/default.yaml · engine/sandbox/docker.yaml
  api/service.yaml · db/postgres.yaml · broker/redis.yaml · logging/default.yaml
src/packer/
  __init__.py
  engine/
    __init__.py
    common/
      __init__.py
      errors.py          # PackerError taxonomy
      types.py           # ModelRef + shared value objects
      progress.py        # ProgressCallback protocol + Null/Recording impls + ProgressEvent
      ports.py           # port Protocols (ArtifactStore, ModelLoader, Signal, Scanner, ...)
      registry.py        # generic Registry[T]
      registries.py      # canonical registry instances
      logging.py         # structured logging + correlation id
      config_schema.py   # @dataclass structured configs + ConfigStore registration
      assembler.py       # EnginePorts + assemble_ports() skeleton
    models/
      __init__.py
      loader.py          # HFModelLoader + LoadedModel
      accessor.py        # WeightAccessor
    artifacts/
      __init__.py
      manifest.py        # Manifest (pydantic, versioned)
      codec.py           # ResidualCodec Protocol + Residuals type
      pak.py             # PakBundle + PakWriter + PakReader
tests/
  unit/
    common/{test_errors.py,test_progress.py,test_registry.py,test_types.py,test_config.py}
    models/{test_loader.py,test_accessor.py}
    artifacts/{test_manifest.py,test_pak.py}
    fixtures/  (generated safetensors + hand-authored pak)
  conftest.py
```

---

### Task 1: uv project → src layout + toolchain config

**Files:**
- Modify: `pyproject.toml`
- Create: `src/packer/__init__.py`, `src/packer/engine/__init__.py`, `src/packer/engine/common/__init__.py`
- Delete: `main.py` (uv starter)
- Test: `tests/unit/test_smoke.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable `packer` package; `uv run pytest`, `uv run ruff check`, `uv run mypy src` all runnable.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_smoke.py`:
```python
def test_package_imports():
    import packer
    import packer.engine
    import packer.engine.common
    assert packer.__name__ == "packer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packer'`

- [ ] **Step 3: Create the package + expand pyproject**

Create the three `__init__.py` files (empty). Delete `main.py`. Replace `pyproject.toml` with (see [DEVELOPMENT.md](../DEVELOPMENT.md) §3.1 for the canonical full version — reproduce it here):
```toml
[project]
name = "packer"
version = "0.1.0"
description = "Store code in overfit transformer weights; detect and sandbox it."
readme = "README.md"
requires-python = ">=3.10,<3.11"
dependencies = [
  "numpy>=1.26", "scipy>=1.12", "safetensors>=0.4", "huggingface-hub>=0.23",
  "hydra-core>=1.3", "omegaconf>=2.3", "pydantic>=2.7",
]

[dependency-groups]
dev = ["ruff>=0.5", "mypy>=1.10", "pytest>=8.2", "pytest-cov>=5.0",
       "hypothesis>=6.100", "import-linter>=2.0", "pre-commit>=3.7"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/packer"]

[tool.ruff]
line-length = 100
target-version = "py310"
src = ["src", "tests"]
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "C4", "PTH", "RUF"]
ignore = ["E501"]
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.10"
strict = true
warn_unused_ignores = true

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"
markers = ["unit: fast, no external services", "integration: needs services",
           "e2e: full stack", "gpu: requires CUDA"]
```
Add remaining runtime deps (torch, fastapi, celery, etc.) in the phases that first need them — YAGNI for Phase 0.

- [ ] **Step 4: Sync and run**

Run: `uv sync && uv run pytest tests/unit/test_smoke.py -v`
Expected: PASS. Then `uv run ruff check .` → passes; `uv run mypy src` → passes (no code yet).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: convert uv starter to src/packer layout + toolchain config"
```

---

### Task 2: pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: the ruff/mypy config from Task 1.
- Produces: `uv run pre-commit run --all-files` passes; lint/format run on every commit.

- [ ] **Step 1: Create the config**

`.pre-commit-config.yaml` (canonical version in [DEVELOPMENT.md](../DEVELOPMENT.md) §3.2):
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
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
        args: [--maxkb=1024]
      - id: check-merge-conflict
      - id: detect-private-key
```
*(The import-linter local hook is added in Task 9, once the contracts exist.)*

- [ ] **Step 2: Install and run**

Run: `uv run pre-commit install && uv run pre-commit run --all-files`
Expected: all hooks pass (may auto-fix formatting on first run; re-run to confirm green).

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit with ruff lint+format and mypy"
```

---

### Task 3: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: uv project from Task 1.
- Produces: a `quality` job (lint → format-check → mypy → import-linter → unit) and an `integration` job. import-linter/step is added now but the contracts land in Task 9; keep the step and ensure it passes on the skeleton (it will once Task 9 adds the config).

- [ ] **Step 1: Create the workflow** (canonical shape in [DEVELOPMENT.md](../DEVELOPMENT.md) §3.3)
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
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src
      - run: uv run lint-imports
      - run: uv run pytest tests/unit --cov=packer
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { enable-cache: true }
      - run: uv sync
      - run: uv run pytest tests/integration -m integration
```

- [ ] **Step 2: Commit** (CI validates on push; nothing to run locally)
```bash
git add .github/workflows/ci.yml
git commit -m "ci: add quality + integration workflow via setup-uv"
```

---

### Task 4: Error taxonomy

**Files:**
- Create: `src/packer/engine/common/errors.py`
- Test: `tests/unit/common/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `PackerError(code: str, message: str, context: dict | None)` base + subclasses `ConfigError, LoadError, UnsafeModelError(LoadError), PackError, ReconstructionError, ScanError, SandboxError`. Every subclass sets a default `code`.

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_errors.py`:
```python
import pytest
from packer.engine.common.errors import (
    PackerError, ConfigError, UnsafeModelError, LoadError,
)

def test_packer_error_carries_code_and_context():
    e = PackerError("boom", context={"k": "v"})
    assert e.code == "packer_error"
    assert e.context == {"k": "v"}
    assert str(e) == "boom"

def test_subclasses_have_stable_codes():
    assert ConfigError("x").code == "config_error"
    assert UnsafeModelError("x").code == "unsafe_model"

def test_unsafe_is_a_load_error():
    assert issubclass(UnsafeModelError, LoadError)
    with pytest.raises(LoadError):
        raise UnsafeModelError("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError` / attribute errors.

- [ ] **Step 3: Implement**

`src/packer/engine/common/errors.py`:
```python
from __future__ import annotations


class PackerError(Exception):
    """Base error. Carries a stable machine code and safe context."""

    code: str = "packer_error"

    def __init__(self, message: str, *, context: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class ConfigError(PackerError):
    code = "config_error"


class LoadError(PackerError):
    code = "load_error"


class UnsafeModelError(LoadError):
    code = "unsafe_model"


class PackError(PackerError):
    code = "pack_error"


class ReconstructionError(PackerError):
    code = "reconstruction_error"


class ScanError(PackerError):
    code = "scan_error"


class SandboxError(PackerError):
    code = "sandbox_error"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_errors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/common/errors.py tests/unit/common/test_errors.py
git commit -m "feat(common): add PackerError taxonomy"
```

---

### Task 5: Progress protocol + implementations

**Files:**
- Create: `src/packer/engine/common/progress.py`
- Test: `tests/unit/common/test_progress.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ProgressCallback` Protocol: `__call__(self, *, step: str, pct: float, detail: str | None = None) -> None`
  - `null_progress(*, step, pct, detail=None) -> None` (no-op default)
  - `RecordingProgress` with `.events: list[ProgressEvent]` for tests
  - `ProgressEvent` frozen dataclass `{step: str, pct: float, detail: str | None}`

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_progress.py`:
```python
from packer.engine.common.progress import (
    ProgressCallback, RecordingProgress, null_progress, ProgressEvent,
)

def test_null_progress_is_a_noop():
    null_progress(step="x", pct=0.5)  # must not raise

def test_recording_progress_captures_events():
    rec = RecordingProgress()
    rec(step="train", pct=0.25, detail="epoch 1")
    rec(step="train", pct=1.0)
    assert rec.events == [
        ProgressEvent(step="train", pct=0.25, detail="epoch 1"),
        ProgressEvent(step="train", pct=1.0, detail=None),
    ]

def test_recording_progress_satisfies_protocol():
    cb: ProgressCallback = RecordingProgress()
    cb(step="s", pct=0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_progress.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/common/progress.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ProgressEvent:
    step: str
    pct: float
    detail: str | None = None


@runtime_checkable
class ProgressCallback(Protocol):
    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None: ...


def null_progress(*, step: str, pct: float, detail: str | None = None) -> None:
    return None


class RecordingProgress:
    """Test double: records every progress call."""

    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None:
        self.events.append(ProgressEvent(step=step, pct=pct, detail=detail))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_progress.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/common/progress.py tests/unit/common/test_progress.py
git commit -m "feat(common): add ProgressCallback protocol + recording/null impls"
```

---

### Task 6: Generic Registry

**Files:**
- Create: `src/packer/engine/common/registry.py`
- Test: `tests/unit/common/test_registry.py`

**Interfaces:**
- Consumes: `ConfigError` (Task 4).
- Produces: `Registry[T]` with `.register(name) -> decorator`, `.create(name, **kwargs) -> T`, `.names() -> list[str]`. Duplicate registration and unknown lookup both raise `ConfigError`. **This is the extensibility linchpin (SYSTEM-DESIGN §3.4).**

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_registry.py`:
```python
import pytest
from packer.engine.common.registry import Registry
from packer.engine.common.errors import ConfigError


def test_register_and_create():
    reg: Registry[object] = Registry("widget")

    @reg.register("alpha")
    class Alpha:
        def __init__(self, k: int = 0) -> None:
            self.k = k

    obj = reg.create("alpha", k=5)
    assert isinstance(obj, Alpha)
    assert obj.k == 5
    assert reg.names() == ["alpha"]


def test_duplicate_registration_raises():
    reg: Registry[object] = Registry("widget")

    @reg.register("a")
    class A: ...

    with pytest.raises(ConfigError):
        @reg.register("a")
        class B: ...


def test_unknown_create_raises():
    reg: Registry[object] = Registry("widget")
    with pytest.raises(ConfigError):
        reg.create("missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_registry.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/common/registry.py`:
```python
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from packer.engine.common.errors import ConfigError

T = TypeVar("T")


class Registry(Generic[T]):
    """Name -> factory registry. The single plugin mechanism (SYSTEM-DESIGN §3.4)."""

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def deco(cls: type[T]) -> type[T]:
            if name in self._factories:
                raise ConfigError(f"duplicate {self._kind}: {name!r}")
            self._factories[name] = cls
            return cls

        return deco

    def create(self, name: str, **kwargs: object) -> T:
        if name not in self._factories:
            raise ConfigError(
                f"unknown {self._kind}: {name!r}; known: {self.names()}"
            )
        return self._factories[name](**kwargs)

    def names(self) -> list[str]:
        return sorted(self._factories)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/common/registry.py tests/unit/common/test_registry.py
git commit -m "feat(common): add generic Registry[T] plugin mechanism"
```

---

### Task 7: Value-object types + ports + registry instances

**Files:**
- Create: `src/packer/engine/common/types.py`, `src/packer/engine/common/ports.py`, `src/packer/engine/common/registries.py`
- Test: `tests/unit/common/test_types.py`

**Interfaces:**
- Consumes: `Registry` (Task 6), `ProgressCallback` (Task 5).
- Produces:
  - `types.py`: `ModelRef` frozen dataclass `{kind: Literal["hf","path","pak"], value: str}` with `ModelRef.parse(s: str) -> ModelRef`.
  - `ports.py`: the port Protocols exactly as in SYSTEM-DESIGN §3.2 (`ArtifactStore`, `ModelLoader`, `SandboxRunner`, `Signal`, `Scanner`, `DecodeStrategy`, `ResidualCodec`, `ModelArchitecture`, `Tokenizer`, `Extractor`, `Clock`, `Rng`). These are `Protocol` declarations only.
  - `registries.py`: the canonical instances (`SIGNAL_REGISTRY`, `SCANNER_REGISTRY`, `DECODE_REGISTRY`, `CODEC_REGISTRY`, `ARCH_REGISTRY`, `TOKENIZER_REGISTRY`, `EXTRACTOR_REGISTRY`, `STORE_REGISTRY`, `SANDBOX_REGISTRY`).

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_types.py`:
```python
import pytest
from packer.engine.common.types import ModelRef
from packer.engine.common import registries


def test_modelref_parse_hf_id():
    assert ModelRef.parse("Qwen/Qwen2.5-0.5B") == ModelRef(kind="hf", value="Qwen/Qwen2.5-0.5B")

def test_modelref_parse_pak():
    assert ModelRef.parse("./x.pak").kind == "pak"

def test_modelref_parse_path():
    assert ModelRef.parse("./some/dir").kind == "path"

def test_registries_exist_and_are_named():
    assert registries.SIGNAL_REGISTRY.names() == []
    assert registries.SCANNER_REGISTRY.names() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_types.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

`src/packer/engine/common/types.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RefKind = Literal["hf", "path", "pak"]


@dataclass(frozen=True)
class ModelRef:
    kind: RefKind
    value: str

    @classmethod
    def parse(cls, s: str) -> ModelRef:
        if s.endswith(".pak"):
            return cls(kind="pak", value=s)
        if Path(s).exists() or s.startswith((".", "/")) or ":" in s and "\\" in s:
            return cls(kind="path", value=s)
        # HF ids look like "org/name" with no filesystem existence
        if "/" in s and not Path(s).exists():
            return cls(kind="hf", value=s)
        return cls(kind="path", value=s)
```
*(Note: `.parse` is a pragmatic heuristic; callers may also construct `ModelRef` directly. Keep the ordering: `.pak` first, then explicit paths, then hf ids.)*

`src/packer/engine/common/ports.py` — reproduce the Protocols from SYSTEM-DESIGN §3.2 verbatim (imports use `typing.Protocol`, `runtime_checkable` where a test needs it). Forward-referenced value types (`LoadedModel`, `PakBundle`, etc.) are imported under `TYPE_CHECKING` to keep `engine.common` dependency-free at runtime:
```python
from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO, Protocol

if TYPE_CHECKING:
    from packer.engine.artifacts.pak import PakBundle
    from packer.engine.common.types import ModelRef
    # ... other forward refs as needed


class ProgressCallback(Protocol):
    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None: ...


class ArtifactStore(Protocol):
    def put_pak(self, bundle: "PakBundle") -> str: ...
    def open_pak(self, artifact_id: str) -> "PakBundle": ...
    def put_blob(self, key: str, data: bytes) -> str: ...
    def open_blob(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...


class ModelLoader(Protocol):
    def load(self, ref: "ModelRef", *, allow_pickle: bool = False) -> "LoadedModel": ...  # type: ignore[name-defined]

# ...continue for SandboxRunner, Signal, Scanner, DecodeStrategy, ResidualCodec,
#    ModelArchitecture, Tokenizer, Extractor, Clock, Rng — exactly per SYSTEM-DESIGN §3.2.
```

`src/packer/engine/common/registries.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.common.registry import Registry

if TYPE_CHECKING:
    from packer.engine.common.ports import (
        ArtifactStore, DecodeStrategy, Extractor, ModelArchitecture,
        ResidualCodec, SandboxRunner, Scanner, Signal, Tokenizer,
    )

SIGNAL_REGISTRY: "Registry[Signal]" = Registry("signal")
SCANNER_REGISTRY: "Registry[Scanner]" = Registry("scanner")
DECODE_REGISTRY: "Registry[DecodeStrategy]" = Registry("decode_strategy")
CODEC_REGISTRY: "Registry[ResidualCodec]" = Registry("residual_codec")
ARCH_REGISTRY: "Registry[ModelArchitecture]" = Registry("architecture")
TOKENIZER_REGISTRY: "Registry[Tokenizer]" = Registry("tokenizer")
EXTRACTOR_REGISTRY: "Registry[Extractor]" = Registry("extractor")
STORE_REGISTRY: "Registry[ArtifactStore]" = Registry("artifact_store")
SANDBOX_REGISTRY: "Registry[SandboxRunner]" = Registry("sandbox_runner")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_types.py -v && uv run mypy src`
Expected: PASS + mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/common/types.py src/packer/engine/common/ports.py \
        src/packer/engine/common/registries.py tests/unit/common/test_types.py
git commit -m "feat(common): add value-object types, port protocols, registry instances"
```

---

### Task 8: Structured logging + correlation id

**Files:**
- Create: `src/packer/engine/common/logging.py`
- Test: `tests/unit/common/test_logging.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `get_logger(name: str) -> Logger` and `bind_correlation_id(cid: str) -> None` / `current_correlation_id() -> str | None` using a `ContextVar`. Log records include the correlation id when set.

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_logging.py`:
```python
from packer.engine.common.logging import (
    bind_correlation_id, current_correlation_id, get_logger,
)

def test_correlation_id_roundtrip():
    assert current_correlation_id() is None
    bind_correlation_id("job-123")
    assert current_correlation_id() == "job-123"

def test_get_logger_returns_named_logger():
    log = get_logger("packer.test")
    assert log.name == "packer.test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_logging.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/common/logging.py`:
```python
from __future__ import annotations

import logging
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def bind_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


class _CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_correlation_id() or "-"
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(f, _CorrelationFilter) for f in logger.filters):
        logger.addFilter(_CorrelationFilter())
    return logger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_logging.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/common/logging.py tests/unit/common/test_logging.py
git commit -m "feat(common): add structured logging with correlation-id context"
```

---

### Task 9: import-linter contracts (Dependency Rule enforcement)

**Files:**
- Modify: `pyproject.toml` (append `[tool.importlinter]` — see [DEVELOPMENT.md](../DEVELOPMENT.md) §3.1)
- Modify: `.pre-commit-config.yaml` (add local `lint-imports` hook)
- Test: manual — `uv run lint-imports`

**Interfaces:**
- Consumes: the `packer.engine.common` modules created so far.
- Produces: the two contracts that reference **only modules that exist in Phase 0** — "engine is framework-agnostic" (forbidden) and a minimal "clean layering". The other contracts/layers (detect no-inference, the `docker` carve-out, and the extract/sandbox/api layers) are added by later phases as their modules land — see the incremental map in [DEVELOPMENT.md](../DEVELOPMENT.md) §3.1. CI's `lint-imports` step (Task 3) now has config to run.

- [ ] **Step 1: Append the Phase-0 contracts to `pyproject.toml`**

import-linter errors on any referenced module that doesn't exist yet, so Phase 0 registers only what's present (`common`, `models`, `artifacts`). `docker` is added to the forbidden list in Phase 3 (with the adapter carve-out), `detect` no-inference in Phase 2, and the `api`/`extract`/`sandbox` layers as they land — all converging on the canonical end-state in DEVELOPMENT.md §3.1.
```toml
[tool.importlinter]
root_package = "packer"

[[tool.importlinter.contracts]]
name = "engine is framework-agnostic"
type = "forbidden"
source_modules = ["packer.engine"]
forbidden_modules = ["packer.api", "packer.workers", "redis", "sqlalchemy", "fastapi", "celery"]

[[tool.importlinter.contracts]]
name = "clean layering"          # high -> low; higher layers may import lower ones
type = "layers"
layers = [
  "packer.engine.models | packer.engine.artifacts",
  "packer.engine.common",
]
```

- [ ] **Step 2: Add the pre-commit hook** to `.pre-commit-config.yaml`:
```yaml
  - repo: local
    hooks:
      - id: import-linter
        name: import-linter
        entry: uv run lint-imports
        language: system
        pass_filenames: false
```

- [ ] **Step 3: Run**

Run: `uv run lint-imports`
Expected: `Contracts: N kept, 0 broken.`

- [ ] **Step 4: Commit**
```bash
git add pyproject.toml .pre-commit-config.yaml
git commit -m "chore: enforce Dependency Rule with import-linter contracts"
```

---

### Task 10: Hydra config tree + structured configs + Assembler skeleton

**Files:**
- Create: `conf/config.yaml` + group files (`conf/engine/pack/tiny_decoder.yaml`, `conf/engine/detect/ensemble.yaml`, `conf/engine/sandbox/docker.yaml`, `conf/api/service.yaml`, `conf/db/postgres.yaml`, `conf/broker/redis.yaml`, `conf/logging/default.yaml`)
- Create: `src/packer/engine/common/config_schema.py`, `src/packer/engine/common/assembler.py`
- Test: `tests/unit/common/test_config.py`

**Interfaces:**
- Consumes: registries (Task 7).
- Produces:
  - `config_schema.py`: `@dataclass` schemas (`TinyDecoderCfg`, `SandboxCfg`, `DetectCfg`, `RootCfg`, …) registered in a `ConfigStore` via `register_configs()`.
  - `assembler.py`: `EnginePorts` frozen dataclass `{store, loader, sandbox}` and `assemble_ports(cfg) -> EnginePorts` (skeleton returning `None`-typed placeholders is NOT allowed; return a real dataclass whose fields are filled by registry lookups once adapters exist — for Phase 0, wire only what's available and leave documented `NotImplementedError` factories for absent adapters, guarded by tests that assert the wiring path).
  - `compose_config() -> DictConfig` helper used by tests + services.

- [ ] **Step 1: Write the failing test**

`tests/unit/common/test_config.py`:
```python
from packer.engine.common.config_schema import TinyDecoderCfg, compose_config

def test_defaults_compose():
    cfg = compose_config()
    assert cfg.engine.pack.n_layers == 6
    assert cfg.engine.sandbox.network == "none"

def test_override_applies():
    cfg = compose_config(overrides=["engine/pack.epochs=999"])
    assert cfg.engine.pack.epochs == 999

def test_structured_defaults():
    c = TinyDecoderCfg()
    assert c.vocab_size == 8192 and c.device == "auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/common/test_config.py -v`
Expected: FAIL — module/config missing.

- [ ] **Step 3: Implement**

`src/packer/engine/common/config_schema.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

from hydra import compose, initialize_config_dir
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig
from pathlib import Path


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
    device: str = "auto"
    deterministic: bool = True


@dataclass
class SandboxCfg:
    image: str = "packer-sandbox:latest"
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    network: str = "none"


def register_configs() -> None:
    cs = ConfigStore.instance()
    cs.store(group="engine/pack", name="tiny_decoder", node=TinyDecoderCfg)
    cs.store(group="engine/sandbox", name="docker", node=SandboxCfg)
    # ...additional groups as phases add them.


_CONF_DIR = str((Path(__file__).resolve().parents[3] / "conf"))


def compose_config(overrides: list[str] | None = None) -> DictConfig:
    register_configs()
    with initialize_config_dir(version_base=None, config_dir=_CONF_DIR):
        return compose(config_name="config", overrides=overrides or [])
```

`conf/config.yaml`:
```yaml
defaults:
  - engine/pack: tiny_decoder
  - engine/sandbox: docker
  - _self_

run_dir: ${oc.env:PACKER_RUN_DIR,./outputs}
```
Create the referenced group files with the fields the schemas expect (e.g. `conf/engine/pack/tiny_decoder.yaml` may be empty `{}` if all defaults come from the structured config, or override specific values).

`src/packer/engine/common/assembler.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from omegaconf import DictConfig

from packer.engine.common.errors import ConfigError
from packer.engine.common.registries import SANDBOX_REGISTRY, STORE_REGISTRY


@dataclass(frozen=True)
class EnginePorts:
    store: object | None = None
    sandbox: object | None = None
    loader: object | None = None


def assemble_ports(cfg: DictConfig) -> EnginePorts:
    """DI root. Populated as adapters register in later phases; for now it
    proves the wiring path exists and raises clearly for absent adapters."""
    store = None
    if "store" in cfg and cfg.store.get("name"):
        store = STORE_REGISTRY.create(cfg.store.name, **cfg.store.get("params", {}))
    sandbox = None
    if "sandbox_runner" in cfg and cfg.get("sandbox_runner"):
        sandbox = SANDBOX_REGISTRY.create(cfg.sandbox_runner)
    return EnginePorts(store=store, sandbox=sandbox, loader=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/common/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add conf/ src/packer/engine/common/config_schema.py src/packer/engine/common/assembler.py \
        tests/unit/common/test_config.py
git commit -m "feat(common): add Hydra config tree, structured configs, assembler skeleton"
```

---

### Task 11: Safetensors model loader + WeightAccessor

**Files:**
- Create: `src/packer/engine/models/__init__.py`, `src/packer/engine/models/loader.py`, `src/packer/engine/models/accessor.py`
- Test: `tests/unit/models/test_loader.py`, `tests/unit/models/test_accessor.py`, `tests/unit/conftest.py` (safetensors fixture)

**Interfaces:**
- Consumes: `ModelRef` (Task 7), `LoadError`/`UnsafeModelError` (Task 4).
- Produces:
  - `LoadedModel` frozen dataclass `{tensors: dict[str, np.ndarray], config: dict, source: str, format: str}`.
  - `HFModelLoader` impl of `ModelLoader`: `.load(ref, *, allow_pickle=False) -> LoadedModel`. Local `.safetensors`/dir loads; `.bin`/`.pkl` without `allow_pickle` raises `UnsafeModelError`.
  - `WeightAccessor(model)` with `.attention_matrices()`, `.mlp_matrices()`, `.embedding()`, `.unembedding()`, `.config()` — **exposes tensors only, no forward** (SYSTEM-DESIGN §5.1/§5.4).

- [ ] **Step 1: Write the failing tests**

`tests/unit/models/test_loader.py`:
```python
import numpy as np
import pytest
from pathlib import Path
from safetensors.numpy import save_file

from packer.engine.models.loader import HFModelLoader, LoadedModel
from packer.engine.common.types import ModelRef
from packer.engine.common.errors import UnsafeModelError


def test_loads_local_safetensors(tmp_path: Path):
    p = tmp_path / "m.safetensors"
    save_file({"w": np.zeros((4, 4), dtype=np.float32)}, str(p))
    m = HFModelLoader().load(ModelRef(kind="path", value=str(p)))
    assert isinstance(m, LoadedModel)
    assert "w" in m.tensors and m.format == "safetensors"


def test_pickle_rejected_by_default(tmp_path: Path):
    p = tmp_path / "m.bin"
    p.write_bytes(b"\x80\x04.")  # pickle-ish
    with pytest.raises(UnsafeModelError):
        HFModelLoader().load(ModelRef(kind="path", value=str(p)))
```

`tests/unit/models/test_accessor.py`:
```python
import numpy as np
from packer.engine.models.loader import LoadedModel
from packer.engine.models.accessor import WeightAccessor


def _model() -> LoadedModel:
    return LoadedModel(
        tensors={
            "model.embed_tokens.weight": np.ones((8, 4), dtype=np.float32),
            "lm_head.weight": np.ones((8, 4), dtype=np.float32),
            "model.layers.0.mlp.up_proj.weight": np.ones((16, 4), dtype=np.float32),
            "model.layers.0.self_attn.q_proj.weight": np.ones((4, 4), dtype=np.float32),
        },
        config={"vocab_size": 8},
        source="test",
        format="safetensors",
    )


def test_accessor_yields_roles():
    acc = WeightAccessor(_model())
    assert acc.embedding().shape == (8, 4)
    assert any("mlp" in n for n, _ in acc.mlp_matrices())
    assert any("attn" in n for n, _ in acc.attention_matrices())

def test_accessor_exposes_no_forward():
    acc = WeightAccessor(_model())
    assert not hasattr(acc, "forward")
    assert not hasattr(acc, "generate")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/models -v`
Expected: FAIL — modules missing. *(Add `safetensors` and `numpy` are already runtime deps from Task 1.)*

- [ ] **Step 3: Implement**

`src/packer/engine/models/loader.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file

from packer.engine.common.errors import LoadError, UnsafeModelError
from packer.engine.common.types import ModelRef

_PICKLE_SUFFIXES = {".bin", ".pkl", ".pt", ".pth", ".ckpt"}


@dataclass(frozen=True)
class LoadedModel:
    tensors: dict[str, np.ndarray]
    config: dict
    source: str
    format: str


class HFModelLoader:
    """ModelLoader impl. Safetensors-first; pickle requires explicit opt-in."""

    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> LoadedModel:
        path = Path(ref.value)
        if path.suffix in _PICKLE_SUFFIXES and not allow_pickle:
            raise UnsafeModelError(
                f"refusing to load pickle file {path.name} without allow_pickle=True",
                context={"path": str(path)},
            )
        st = path if path.suffix == ".safetensors" else _find_safetensors(path)
        if st is None:
            raise LoadError(f"no safetensors found for {ref.value}", context={"ref": ref.value})
        return LoadedModel(
            tensors=dict(load_file(str(st))),
            config=_read_config(st.parent),
            source=ref.value,
            format="safetensors",
        )


def _find_safetensors(path: Path) -> Path | None:
    if path.is_dir():
        files = sorted(path.glob("*.safetensors"))
        return files[0] if files else None
    return path if path.suffix == ".safetensors" else None


def _read_config(directory: Path) -> dict:
    import json

    cfg = directory / "config.json"
    return json.loads(cfg.read_text()) if cfg.exists() else {}
```
*(HF-hub download for `kind="hf"` is added when Phase 2 first needs a remote model; local paths cover Phase 0/1 fixtures. Note this in a docstring.)*

`src/packer/engine/models/accessor.py`:
```python
from __future__ import annotations

from typing import Iterator

import numpy as np

from packer.engine.models.loader import LoadedModel


class WeightAccessor:
    """Role-based, tensor-only view over a LoadedModel. No forward/generate —
    this is the structural half of the no-inference guarantee (SYSTEM-DESIGN §5.4)."""

    def __init__(self, model: LoadedModel) -> None:
        self._m = model

    def _by(self, *needles: str) -> Iterator[tuple[str, np.ndarray]]:
        for name, t in self._m.tensors.items():
            if t.ndim == 2 and any(n in name for n in needles):
                yield name, t

    def attention_matrices(self) -> Iterator[tuple[str, np.ndarray]]:
        return self._by("attn", "attention")

    def mlp_matrices(self) -> Iterator[tuple[str, np.ndarray]]:
        return self._by("mlp", "feed_forward", "ffn")

    def embedding(self) -> np.ndarray:
        for name, t in self._m.tensors.items():
            if "embed" in name and t.ndim == 2:
                return t
        raise KeyError("no embedding matrix found")

    def unembedding(self) -> np.ndarray:
        for name, t in self._m.tensors.items():
            if ("lm_head" in name or "unembed" in name) and t.ndim == 2:
                return t
        return self.embedding()  # tied weights fallback

    def config(self) -> dict:
        return self._m.config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/models -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/models tests/unit/models
git commit -m "feat(models): safetensors-first loader + role-based WeightAccessor"
```

---

### Task 12: The `.pak` artifact format (manifest, codec interface, reader/writer)

**Files:**
- Create: `src/packer/engine/artifacts/__init__.py`, `manifest.py`, `codec.py`, `pak.py`
- Test: `tests/unit/artifacts/test_manifest.py`, `tests/unit/artifacts/test_pak.py`

**Interfaces:**
- Consumes: `ConfigError` (Task 4).
- Produces:
  - `Manifest` pydantic model (versioned `pak_version`), with nested `ModelInfo`, `CorpusInfo`, `DecodeInfo`, `ResidualInfo`, `Metrics`. `Manifest.from_json(str)` / `.to_json()`; unknown-future `pak_version` raises `ConfigError`.
  - `Residuals` = `list[tuple[int, int]]` type alias; `ResidualCodec` Protocol re-exported for Phase 1's concrete codec.
  - `PakBundle` frozen dataclass `{tensors: dict[str, np.ndarray], tokenizer_bytes: bytes, manifest: Manifest, residual_blob: bytes}`.
  - `PakWriter.write(path, bundle)` / `PakReader.read(path) -> PakBundle` — the only code that knows the on-disk layout.

- [ ] **Step 1: Write the failing tests**

`tests/unit/artifacts/test_manifest.py`:
```python
import pytest
from packer.engine.artifacts.manifest import Manifest
from packer.engine.common.errors import ConfigError


def _min_manifest() -> Manifest:
    return Manifest.model_validate({
        "pak_version": "1.0",
        "created_utc": "2026-07-07T00:00:00Z",
        "model": {"arch": "tiny-decoder", "param_count": 100},
        "corpus": {"n_files": 1, "n_bytes": 10, "n_tokens": 5, "sha256": "x",
                   "file_map": [], "boundary_scheme": "special-token-v1"},
        "decode": {"strategy": "teacher-forced-greedy", "length_tokens": 5},
        "residuals": {"count": 0, "ratio": 0.0, "codec": "delta-varint-v1"},
        "metrics": {"model_bytes": 1, "artifact_bytes": 1, "original_bytes": 10,
                    "gzip_bytes": 8, "lossless": True},
    })


def test_manifest_roundtrips_json():
    m = _min_manifest()
    assert Manifest.from_json(m.to_json()).pak_version == "1.0"


def test_unknown_future_version_rejected():
    data = _min_manifest().model_dump()
    data["pak_version"] = "99.0"
    with pytest.raises(ConfigError):
        Manifest.model_validate(data)
```

`tests/unit/artifacts/test_pak.py`:
```python
import numpy as np
from pathlib import Path
from packer.engine.artifacts.pak import PakBundle, PakWriter, PakReader
from packer.engine.artifacts.manifest import Manifest


def test_pak_roundtrip(tmp_path: Path):
    manifest = Manifest.model_validate({
        "pak_version": "1.0", "created_utc": "2026-07-07T00:00:00Z",
        "model": {"arch": "tiny-decoder", "param_count": 4},
        "corpus": {"n_files": 1, "n_bytes": 3, "n_tokens": 3, "sha256": "x",
                   "file_map": [], "boundary_scheme": "special-token-v1"},
        "decode": {"strategy": "teacher-forced-greedy", "length_tokens": 3},
        "residuals": {"count": 0, "ratio": 0.0, "codec": "delta-varint-v1"},
        "metrics": {"model_bytes": 1, "artifact_bytes": 1, "original_bytes": 3,
                    "gzip_bytes": 3, "lossless": True},
    })
    bundle = PakBundle(
        tensors={"w": np.arange(4, dtype=np.float32).reshape(2, 2)},
        tokenizer_bytes=b"tok", manifest=manifest, residual_blob=b"\x00",
    )
    out = tmp_path / "x.pak"
    PakWriter().write(out, bundle)
    got = PakReader().read(out)
    assert np.array_equal(got.tensors["w"], bundle.tensors["w"])
    assert got.tokenizer_bytes == b"tok"
    assert got.residual_blob == b"\x00"
    assert got.manifest.pak_version == "1.0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/artifacts -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

`src/packer/engine/artifacts/manifest.py`:
```python
from __future__ import annotations

from pydantic import BaseModel, field_validator

from packer.engine.common.errors import ConfigError

_SUPPORTED = {"1.0"}


class ModelInfo(BaseModel):
    arch: str
    param_count: int
    n_layers: int | None = None
    d_model: int | None = None
    n_heads: int | None = None
    vocab_size: int | None = None
    context_len: int | None = None


class FileSpan(BaseModel):
    path: str
    token_start: int
    token_end: int


class CorpusInfo(BaseModel):
    n_files: int
    n_bytes: int
    n_tokens: int
    sha256: str
    file_map: list[FileSpan]
    boundary_scheme: str


class DecodeInfo(BaseModel):
    strategy: str
    length_tokens: int
    bos_token_id: int = 1


class ResidualInfo(BaseModel):
    count: int
    ratio: float
    codec: str


class Metrics(BaseModel):
    model_bytes: int
    artifact_bytes: int
    original_bytes: int
    gzip_bytes: int
    lossless: bool
    compression_ratio_vs_original: float | None = None


class Manifest(BaseModel):
    pak_version: str
    created_utc: str
    model: ModelInfo
    corpus: CorpusInfo
    decode: DecodeInfo
    residuals: ResidualInfo
    metrics: Metrics
    seed: int | None = None

    @field_validator("pak_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in _SUPPORTED:
            raise ConfigError(f"unsupported pak_version {v!r}; supported: {sorted(_SUPPORTED)}")
        return v

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Manifest":
        return cls.model_validate_json(s)
```

`src/packer/engine/artifacts/codec.py`:
```python
from __future__ import annotations

from typing import Protocol

Residuals = list[tuple[int, int]]  # (position, true_token_id)


class ResidualCodec(Protocol):
    def encode(self, residuals: Residuals) -> bytes: ...
    def decode(self, blob: bytes) -> Residuals: ...
```

`src/packer/engine/artifacts/pak.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file, save_file

from packer.engine.artifacts.manifest import Manifest


@dataclass(frozen=True)
class PakBundle:
    tensors: dict[str, np.ndarray]
    tokenizer_bytes: bytes
    manifest: Manifest
    residual_blob: bytes


class PakWriter:
    def write(self, path: Path, bundle: PakBundle) -> None:
        path.mkdir(parents=True, exist_ok=True)
        save_file(bundle.tensors, str(path / "model.safetensors"))
        (path / "tokenizer.json").write_bytes(bundle.tokenizer_bytes)
        (path / "residuals.bin").write_bytes(bundle.residual_blob)
        (path / "manifest.json").write_text(bundle.manifest.to_json())


class PakReader:
    def read(self, path: Path) -> PakBundle:
        return PakBundle(
            tensors=dict(load_file(str(path / "model.safetensors"))),
            tokenizer_bytes=(path / "tokenizer.json").read_bytes(),
            manifest=Manifest.from_json((path / "manifest.json").read_text()),
            residual_blob=(path / "residuals.bin").read_bytes(),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/artifacts -v && uv run pytest tests/unit && uv run lint-imports && uv run mypy src`
Expected: all PASS; import-linter contracts kept; mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/artifacts tests/unit/artifacts
git commit -m "feat(artifacts): add versioned Manifest, residual codec interface, PakReader/Writer"
```

---

## Phase 0 Definition of Done

- [ ] `uv sync` provisions Python 3.10.x from `uv.lock`; `uv run pre-commit run --all-files` passes.
- [ ] `uv run pytest tests/unit` green; `uv run mypy src` clean; `uv run lint-imports` reports all contracts kept.
- [ ] `import packer.engine` (and `.common`, `.models`, `.artifacts`) succeed with no side effects.
- [ ] A plugin registered in a `Registry` is retrievable by name; unknown name raises `ConfigError`.
- [ ] `compose_config()` composes the root config; `overrides=[...]` applies.
- [ ] `HFModelLoader.load` loads a safetensors fixture and refuses `.bin` by default.
- [ ] A `PakBundle` round-trips through `PakWriter`/`PakReader` byte-for-byte, incl. the manifest.
- [ ] CI `quality` job green.

## Self-Review Notes

- **Spec coverage** (phase-0 spec): scaffold ✓ (T1), toolchain incl. import-linter ✓ (T1–3, T9), Hydra + structured configs + assembler ✓ (T10), kernel errors/progress/types/ports/registry/logging ✓ (T4–8), models loader + WeightAccessor ✓ (T11), `.pak` format ✓ (T12).
- **Interfaces produced here and consumed downstream:** `PackerError` family, `ProgressCallback`/`RecordingProgress`, `Registry` + canonical instances, `ModelRef`, port Protocols, `LoadedModel`/`HFModelLoader`/`WeightAccessor`, `Manifest`/`PakBundle`/`PakWriter`/`PakReader`, `Residuals`/`ResidualCodec`, `compose_config`/`EnginePorts`/`assemble_ports`. Phases 1–6 reference these exact names.
