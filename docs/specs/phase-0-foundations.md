# Phase 0 — Foundations

> **Goal:** an empty but *correct* monorepo — toolchain enforced on commit, Hydra wired, safe model loading, and the `.pak` format defined — so every later phase builds on a stable base.
> **Depends on:** nothing. **Blocks:** all phases.
> **Part mapping:** cross-cutting foundation for Parts 1–4.

---

## 1. Scope

**In scope**
- **uv project** at the repo root (already `uv init`-ed): expand `pyproject.toml`, adopt a `src/packer/` package layout, `uv sync`, commit `uv.lock`. `frontend/` shell; `docs/` (present).
- Toolchain: **uv** (env/deps), **ruff (lint + format)**, **pre-commit**, **mypy (strict)**, **pytest**, **import-linter** — all configured and green. Enabling lint/format-on-commit is the *first* task.
- CI: GitHub Actions `quality` job (lint → format-check → type → **import-linter** → unit).
- **Hydra** config tree + structured-config registry.
- **The shared kernel** (`engine/common/`, per [SYSTEM-DESIGN](../SYSTEM-DESIGN.md) §3): error taxonomy, structured logging, value-object types, `ProgressCallback` + the **ports** protocols (`ArtifactStore`, `ModelLoader`, `SandboxRunner`, `Signal`, `Scanner`, `DecodeStrategy`, …), and the generic **`Registry[T]`** + canonical registry instances. These are the stable contracts everything else builds on — frozen here.
- **`import-linter` contracts** encoding the Dependency Rule (SYSTEM-DESIGN §1/§4/§10).
- `engine/models/`: safetensors-first loader, tensor iterator, metadata reader.
- **`.pak` artifact format**: `manifest.json` schema, reader/writer, residual codec *interface* (implementation stubs OK; the codec's concrete impl lands in Phase 1).

**Out of scope**
- Any Part-1/2/3 algorithm. Services, DB, Celery (Phase 4). Frontend app code (Phase 5).

---

## 2. Modules & interfaces

`engine/common/errors.py`
```python
class PackerError(Exception): ...
class ConfigError(PackerError): ...
class LoadError(PackerError): ...
class UnsafeModelError(LoadError): ...      # pickle/.bin without opt-in
class PackError(PackerError): ...
class ReconstructionError(PackerError): ...
class SandboxError(PackerError): ...
```

`engine/common/progress.py`
```python
from typing import Protocol

class ProgressCallback(Protocol):
    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None: ...

def null_progress(*, step: str, pct: float, detail: str | None = None) -> None: ...
```

`engine/models/loader.py`
```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LoadedModel:
    tensors: dict[str, "Tensor"]      # name -> tensor (lazy where possible)
    config: dict                      # architecture/config metadata
    source: str                       # hf-id | path | pak
    format: str                       # "safetensors" | "pickle"

def load_model(ref: str | Path, *, allow_pickle: bool = False) -> LoadedModel:
    """Load local path, HF id, or .pak. Safetensors-only unless allow_pickle.
    Raises UnsafeModelError on pickle/.bin without opt-in."""

def iter_weight_matrices(m: LoadedModel) -> "Iterator[tuple[str, Tensor]]":
    """Yield 2-D weight matrices (attention/MLP/embeddings) for weight-only analysis."""
```

`engine/artifacts/` — the `.pak` seam (schema in ARCHITECTURE §5.1):
```python
# manifest.py — pydantic (or dataclass) model of manifest.json, versioned
class Manifest(BaseModel): ...

# residual_codec.py — interface now, impl in Phase 1
class ResidualCodec(Protocol):
    def encode(self, residuals: "list[tuple[int,int]]") -> bytes: ...
    def decode(self, blob: bytes) -> "list[tuple[int,int]]": ...

# writer.py / reader.py
def write_pak(path: Path, *, tensors, tokenizer, manifest: Manifest, residuals: bytes) -> None: ...
def read_pak(path: Path) -> "PakBundle": ...   # tensors, tokenizer, manifest, residuals
```

---

## 3. Integration points

- **Every downstream phase imports `engine/common` and `engine/models`.** Their interfaces are frozen here; changes after Phase 0 require an ADR.
- **`.pak` format is the contract** between Phase 1 (writer), Phase 2 (weight reader), Phase 3 (reader). Defining it now prevents rework.
- CI + pre-commit are the quality gate all later PRs pass through.

---

## 4. Testing plan

- **Unit:** `load_model` accepts a safetensors fixture; raises `UnsafeModelError` on a `.bin`/pickle path without `allow_pickle`. `iter_weight_matrices` yields only 2-D tensors. Manifest (de)serialization round-trips; schema-version mismatch raises `ConfigError`.
- **`.pak` round-trip:** a hand-authored fixture bundle writes and reads back identically (tensors, tokenizer bytes, manifest, residual blob).
- **Toolchain self-test:** `pre-commit run --all-files` green; CI `quality` job green on the scaffold.

---

## 5. Development steps (ordered)

1. `git` repo hygiene: confirm `.gitignore`; convert the uv starter to a `src/packer/` package (remove the starter `main.py`); create the `frontend/` shell.
2. Expand the root `pyproject.toml` with deps + `[dependency-groups]` + ruff/mypy/pytest config (see DEVELOPMENT §3.1); `uv sync`; commit `uv.lock`.
3. **`.pre-commit-config.yaml`; `uv run pre-commit install`; make `uv run pre-commit run --all-files` pass.** *(satisfies the lint/format-on-commit requirement first)*
4. `.github/workflows/ci.yml` `quality` job.
5. `engine/common/` kernel: errors, progress, logging, value-object types, the **ports** protocols, and the generic **`Registry[T]`** + canonical instances (SYSTEM-DESIGN §3.1–3.4).
6. `import-linter` `[tool.importlinter]` contracts + wire `lint-imports` into pre-commit/CI (SYSTEM-DESIGN §10).
7. Hydra `conf/` tree + `config_schema.py` `ConfigStore` registrations + the `Assembler` skeleton (SYSTEM-DESIGN §3.5); a smoke test that composes the root config.
8. `engine/models/` loader + `WeightAccessor` + metadata reader (+ tests, + a small safetensors fixture).
9. `engine/artifacts/` manifest schema + reader/writer + residual-codec interface (+ round-trip test).

---

## 6. Acceptance criteria (milestone gate)

- [ ] `uv sync` provisions the env from `uv.lock`; `uv run pre-commit run --all-files` passes; CI `quality` green.
- [ ] `import packer.engine` and submodules succeed with no side effects.
- [ ] `uv run lint-imports` passes — the Dependency Rule holds on the scaffold.
- [ ] A trivial plugin registered in a `Registry` is retrievable by name via `create()`; an unknown name raises `ConfigError`.
- [ ] Hydra composes the root config; overriding a value via CLI works in the smoke test.
- [ ] `load_model` loads a safetensors fixture and refuses pickle by default.
- [ ] A `.pak` fixture round-trips through `write_pak`/`read_pak` byte-for-byte.

---

## 7. Risks

- **Windows path / CRLF quirks** in tooling → set `core.autocrlf=false`, use `pathlib` everywhere (ruff `PTH` enforces).
- **Over-freezing interfaces too early** → keep `engine/common` minimal; only freeze what Phase 1–3 truly share.
