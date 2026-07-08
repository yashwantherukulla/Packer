# Changelog

Reverse-chronological log of implementation commits. One entry per commit: what
changed / was added, and how it was verified. Newest at the top.

---

## Phase 1 — Packer

### `feat(pack): add byte-level BPE tokenizer (byte-bpe) with lossless coverage`
- **Task 4.** Added `tokenizer.py`: `ByteBPETokenizer` `@TOKENIZER_REGISTRY.register("byte-bpe")` — HF `tokenizers` BPE over a latin-1 byte↔char bijection with the full 256-symbol initial alphabet, so `decode(encode(x)) == x` for *any* bytes. Implements the enriched `Tokenizer` port + `from_bytes`/`_require`. Registered via `pack/__init__.py`.
- Deviations from plan snippet: concretized return values (`list(...)`, `int(...)`, typed `text: str`) to satisfy mypy-strict `warn_return_any`; `# type: ignore[no-untyped-call]` on `BpeTrainer` (untyped in the `tokenizers` stubs); tightened the pre-train test to `pytest.raises(PackError)` (ruff B017).
- **Verified:** `pytest tests/unit/pack/test_tokenizer.py` → 6 passed (lossless on training text + arbitrary 256-byte binary, serialization round-trip); mypy clean; ruff clean.

### `refactor(common): preserve concrete type in Registry.register; enrich Tokenizer port`
- Prep for the Phase-1 plugins (kernel change discovered when first using the decorator):
  - `Registry.register` is now generic in the **decorated** class (`_C`), not the registry's `T`. Before, `@REG.register(...) class Foo` collapsed `Foo`'s type to `type[T]`, erasing its concrete API — which would have broken `decode.py`/`unpacker.py` calling `ByteBPETokenizer`'s non-port methods (`bos_id`, `from_bytes`) in mypy-strict `src`. Now the decorated symbol keeps its concrete type; `create` still returns `T`.
  - `Tokenizer` port gained `vocab_size()`, `bos_id()`, `to_bytes()` — the methods `Packer` needs from any tokenizer plugin, so it stays plugin-agnostic (uses `TOKENIZER_REGISTRY.create(...)` without casting to the concrete class).
- **Verified:** `pytest tests/unit/common` green; mypy clean; import-linter kept.

### `feat(pack): add reversible MarkerCorpusSerializer + SerializedCorpus`
- **Task 3.** Added `corpus.py`: `SerializedCorpus` frozen value object (`bytes`, `file_map` of `(posix_relpath, start, end)`, `.n_files`/`.original_bytes`) and `MarkerCorpusSerializer` — deterministic (sorted posix paths), self-delimiting magic-framed serialize + fully reversible deserialize; corrupt framing raises `PackError`.
- **Verified:** `pytest tests/unit/pack/test_corpus.py` → 4 passed (nested/binary/empty/unicode-path files, determinism, span integrity, corruption); mypy clean.

### `feat(pack): extend TinyDecoderCfg with plugin-name + training fields`
- **Task 2.** Extended `TinyDecoderCfg` with backward-compatible defaulted fields: plugin selectors (`arch`, `tokenizer`, `decode`, `codec`) + training/persistence knobs (`weight_decay`, `seed`, `bos_token_id`, `out_dir`). Compose + override verified under `cfg.engine.pack`.
- Deviation from plan: the `conf/engine/pack/tiny_decoder.yaml` group file is omitted (as in Phase 0 Task 10, the ConfigStore-registered structured config supplies defaults); test uses the corrected dotted override `engine.pack.seed=7`.
- **Verified:** `pytest tests/unit/common/test_config_pack.py` → 2 passed; mypy clean.

### `feat(pack): scaffold pack package, add torch+tokenizers, add varint util`
- **Task 1.** Added runtime deps `torch>=2.13.0` (CPU build) and `tokenizers>=0.23.1` via `uv add`. Created the `packer.engine.pack` package (empty `__init__.py`; plugin-registration imports appended per task) and `varint.py` (`_write_uvarint`/`_read_uvarint` — unsigned LEB128, shared by corpus + residual codec).
- **Verified:** `pytest tests/unit/pack/test_varint.py` → 3 passed; mypy clean; import-linter kept (pack imports only stdlib so far).

## Phase 0 — Foundations

### `docs: mark Phase 0 complete`
- **Phase 0 done.** All 12 plan tasks landed across 14 commits on `phase-0-foundations`. Definition of Done fully met: 27 unit tests, mypy-strict clean (19 files), 2 import-linter contracts kept, all engine subpackages import with no side effects. (CI job is valid but unexercised — no remote yet.)
- Branch merged into `main` with `--no-ff`.
- **Next:** Phase 1 (Packer) — from-scratch tiny decoder, byte-BPE tokenizer, overfit trainer, residual capture, lossless `Packer.pack`.

> **Task order note:** remaining Phase-0 tasks are executed **11 → 12 → 10 → 9** (models, artifacts, config/assembler, import-linter). The import-linter layering contract references `packer.engine.models`/`artifacts`, so it must land *after* those packages exist; models & artifacts are independent of config/assembler.

### `chore: enforce Dependency Rule with import-linter contracts`
- **Task 9** (Phase-0 finale). Appended `[tool.importlinter]` to `pyproject.toml` with the Phase-0 contract subset:
  - **"engine is framework-agnostic"** (forbidden): `packer.engine` must not import `packer.api`, `packer.workers`, `redis`, `sqlalchemy`, `fastapi`, or `celery`.
  - **"clean layering"** (layers): `packer.engine.models | packer.engine.artifacts` sit above `packer.engine.common`; `common` imports nothing higher, and `models`/`artifacts` don't import each other.
- Added `include_external_packages = true` (required because the forbidden lists name external frameworks) — this was the one non-obvious knob; without it import-linter errors out.
- Added a local `import-linter` pre-commit hook (`uv run lint-imports`); synced `DEVELOPMENT.md` §3.1/§3.2.
- Later phases extend these toward the canonical end-state (detect no-inference, the docker adapter carve-out, and the extract/sandbox/api layers) as those modules land.
- **Verified:** `uv run lint-imports` → **2 contracts kept, 0 broken** (33 files, 60 dependencies analyzed).

### `feat(common): add Hydra config tree, structured configs, assembler skeleton`
- **Task 10.** Added:
  - `conf/config.yaml` — root Hydra config; `defaults` select `engine/pack: tiny_decoder` + `engine/sandbox: docker` (resolved from the ConfigStore); `run_dir` via `${oc.env:...}` interpolation.
  - `config_schema.py` — structured `@dataclass` configs `TinyDecoderCfg`, `SandboxCfg`; `register_configs()` stores them in the ConfigStore; `compose_config(overrides=...)` composes the root config via `initialize_config_dir`.
  - `assembler.py` — `EnginePorts` frozen dataclass (`store`/`sandbox`/`loader`) + `assemble_ports(cfg)` DI root (registry-driven; returns null ports until adapters register in later phases).
- Deviations from plan snippet: (a) `_CONF_DIR` uses `parents[4]` not `parents[3]` — `conf/` is at the repo root under the root src-layout; (b) test override syntax is `engine.pack.epochs=999` (dotted value override), not the plan's `engine/pack.epochs=999`; (c) the group option YAMLs (`tiny_decoder.yaml`/`docker.yaml`) are omitted — the ConfigStore-registered structured configs supply the defaults (files added when a phase needs file-level overrides); (d) dropped the unused `field` import.
- **Verified:** `pytest tests/unit/common/test_config.py` → 4 passed; ruff clean; `mypy src` clean.

### `chore: run ruff/mypy as local uv hooks to eliminate version drift`
- Converted ruff, ruff-format, and mypy pre-commit hooks from pinned mirror repos (`ruff-pre-commit@v0.5.0`, `mirrors-mypy@v1.10.0`) to **local `uv run` hooks**, so the hook uses the exact `uv.lock` versions (ruff 0.15.20, mypy 2.2.0) — identical to CI.
- **Root cause:** the pinned ruff v0.5.0 didn't enforce `RUF022` (`__all__` sort) the way the uv-locked ruff 0.15.20 does, so `artifacts/codec.py` passed the hook in Task 12 but failed `uv run ruff check` afterward. Fixed `codec.py`'s `__all__` order (`["ResidualCodec", "Residuals"]`).
- Bumped `pre-commit/pre-commit-hooks` v4.6.0 → v5.0.0 (silences the deprecated-stage-name warning). Updated the canonical config in `DEVELOPMENT.md` §3.2.
- **Verified:** `pre-commit run --all-files` → all hooks pass.

### `feat(artifacts): add versioned Manifest, residual codec interface, PakReader/Writer`
- **Task 12.** Added the `.pak` artifact contract:
  - `common/types.py` — `Residuals = list[tuple[int, int]]` (kernel home per SYSTEM-DESIGN §3.1).
  - `common/ports.py` — `ResidualCodec` port (references the kernel `Residuals`); `CODEC_REGISTRY` tightened to `Registry[ResidualCodec]`.
  - `artifacts/manifest.py` — versioned pydantic `Manifest` (+ `ModelInfo`, `FileSpan`, `CorpusInfo`, `DecodeInfo`, `ResidualInfo`, `Metrics`); `to_json`/`from_json`; unknown `pak_version` raises `ConfigError` (propagates out of the validator, not wrapped by pydantic).
  - `artifacts/codec.py` — thin re-export site (`Residuals`, `ResidualCodec`) for artifact-oriented callers; concrete `DeltaVarintCodec` arrives in Phase 1.
  - `artifacts/pak.py` — `PakBundle` value object + `PakWriter`/`PakReader`, the only code that knows the on-disk layout (a directory: `model.safetensors`, `tokenizer.json`, `residuals.bin`, `manifest.json`).
- Deviation from plan snippet: `Residuals`/`ResidualCodec` live in the kernel (not `artifacts/codec.py`) so the port never inverts the Dependency Rule; `codec.py` re-exports them. Tensor maps typed `dict[str, NDArray[Any]]`.
- **Fix:** anchored the `.gitignore` ML-output ignores (`/data/`, `/artifacts/`, `/models_store/`) to the repo root — the unanchored `artifacts/` was shadowing the new source package `src/packer/engine/artifacts/` and `tests/unit/artifacts/`.
- **Verified:** `pytest tests/unit/artifacts` → 3 passed; **full `tests/unit` → 23 passed**; ruff clean; `mypy src` clean.
- **Task 11.** Added `src/packer/engine/models/`:
  - `loader.py` — `LoadedModel` frozen value object (`tensors`, `config`, `source`, `format`) + `HFModelLoader` (safetensors-first; `.bin`/`.pkl`/`.pt`/`.pth`/`.ckpt` without `allow_pickle=True` raises `UnsafeModelError`; missing safetensors raises `LoadError`). HF-hub download deferred to Phase 2.
  - `accessor.py` — `WeightAccessor`: role-based, tensor-only view (`attention_matrices`, `mlp_matrices`, `embedding`, `unembedding` with tied-weight fallback, `config`). No `forward`/`generate` — the structural half of the no-inference guarantee.
- Deviation from plan snippet: typed tensor maps as `dict[str, NDArray[Any]]` and configs as `dict[str, Any]` (mypy-strict rejects bare `np.ndarray`/`dict`). No new port added — `ModelLoader` port is deferred to Phase 2 (first consumer) to keep the Dependency Rule strict (a `common` port referencing the `models`-owned `LoadedModel` would invert the layering).
- **Verified:** `pytest tests/unit/models` → 4 passed; ruff clean; `mypy src` clean.

### `feat(common): add structured logging with correlation-id context`
- **Task 8.** Added `src/packer/engine/common/logging.py`: `get_logger(name)` (attaches a correlation-id filter once), `bind_correlation_id(cid)` / `current_correlation_id()` backed by a `ContextVar`, and `_CorrelationFilter` which stamps every record with the current id (or `-`).
- **Verified:** `pytest tests/unit/common/test_logging.py` → 2 passed; ruff clean; `mypy src` clean.

### `feat(common): add value-object types, port protocols, registry instances`
- **Task 7.** Added:
  - `types.py` — `ModelRef` frozen value object (`kind` = `hf`/`path`/`pak`) + `ModelRef.parse` heuristic (`.pak` → paths → HF id).
  - `ports.py` — port Protocols (SYSTEM-DESIGN §3.2): `ProgressCallback` (re-exported), `Clock`, `Rng`, `Tokenizer`.
  - `registries.py` — all nine canonical `Registry` instances (`TOKENIZER`, `CODEC`, `STORE`, `ARCH`, `DECODE`, `SIGNAL`, `SCANNER`, `SANDBOX`, `EXTRACTOR`).
- **Deviation — incremental ports (important, affects later phases):** mypy-strict errors on any forward reference to a type that doesn't exist yet (verified empirically). The plugin ports reference subsystem types that legitimately live in later phases (e.g. `Signal`→`SignalResult`, `Scanner`→`FileSet`/`Finding`, `SandboxRunner`→`ExecUnit`, `DecodeStrategy`→`InferenceModel` [torch]). So the port **catalog is introduced incrementally**, mirroring the project's existing incremental import-linter policy. Growth map is documented in `ports.py`:
  - Phase 0 T11 (models) adds `ModelLoader`; T12 (artifacts) adds `ArtifactStore`, `ResidualCodec`.
  - Phase 1 adds `ModelArchitecture`, `DecodeStrategy`; Phase 2 adds `Signal`; Phase 3 adds `Scanner`, `SandboxRunner`, `Extractor`.
  - Each registry is typed `Registry[object]` until its port lands, then the annotation is tightened (runtime object is unchanged, so callers are unaffected). `TOKENIZER_REGISTRY` is already typed `Registry[Tokenizer]`.
  - **Downstream note:** when I reach Phases 1–3 I will add each port to `ports.py` + tighten its registry annotation, rather than assume the full catalog exists from Phase 0.
- **Verified:** `pytest tests/unit/common/test_types.py` → 4 passed; ruff clean (auto-sorted `__all__`); `mypy src` clean.

### `feat(common): add generic Registry[T] plugin mechanism`
- **Task 6.** Added `src/packer/engine/common/registry.py`: `Registry[T]` (the single plugin/extensibility mechanism) with `.register(name)` decorator, `.create(name, **kwargs) -> T`, `.names()`. Duplicate registration and unknown lookup both raise `ConfigError`.
- Deviation from plan snippet: imported `Callable` from `collections.abc` (ruff UP035; `typing.Callable` is deprecated).
- **Verified:** `pytest tests/unit/common/test_registry.py` → 3 passed; ruff clean; `mypy src` clean.

### `feat(common): add ProgressCallback protocol + recording/null impls`
- **Task 5.** Added `src/packer/engine/common/progress.py`: `ProgressEvent` (frozen dataclass `{step, pct, detail}`), `ProgressCallback` runtime-checkable Protocol (keyword-only `step`/`pct`/`detail`), `null_progress` no-op default, and `RecordingProgress` test double capturing `.events`.
- Deviation from plan snippet: dropped the unused `field` import (ruff F401).
- **Verified:** `pytest tests/unit/common/test_progress.py` → 3 passed; ruff clean; `mypy src` clean.

### `feat(common): add PackerError taxonomy`
- **Task 4.** Added `src/packer/engine/common/errors.py`: `PackerError(message, *, context)` base carrying a stable machine `code` and a safe `context` dict, plus `ConfigError`, `LoadError`, `UnsafeModelError(LoadError)`, `PackError`, `ReconstructionError`, `ScanError`, `SandboxError` — each with a default `code`.
- Deviation from plan snippet: typed `context` as `dict[str, object]` (bare `dict` fails mypy-strict `disallow_any_generics`). Same parametrization will be applied to other plan snippets that use bare `dict`.
- **Verified:** `pytest tests/unit/common/test_errors.py` → 3 passed; ruff clean; `mypy src` clean.

### `ci: add quality + integration workflow via setup-uv`
- **Task 3.** Added `.github/workflows/ci.yml` with two jobs, both on `astral-sh/setup-uv` (cached) + `uv sync`:
  - `quality`: ruff check → ruff format --check → mypy src → lint-imports → unit tests (with coverage).
  - `integration`: `pytest tests/integration -m integration`.
- The `lint-imports` step gains its config in Task 9; `tests/integration` is populated in later phases. No git remote yet, so CI is not exercised — the workflow is valid YAML and ready for when a remote is added.
- **Verified:** `check-yaml` pre-commit hook passes on the workflow file.

### `chore: add pre-commit with ruff lint+format and mypy`
- **Task 2.** Added `.pre-commit-config.yaml`: ruff (`--fix`), ruff-format, mypy (strict, `src/`, with pydantic dep), plus hygiene hooks (end-of-file-fixer, trailing-whitespace, check-yaml, check-added-large-files ≤1 MB, check-merge-conflict, detect-private-key).
- Installed the hook (`pre-commit install`) so lint/format/type-checks run on every commit from here on.
- **Exempted** `docs/plans/2026-07-07-phase-3-extractor-sandbox.md` from `detect-private-key`: that plan documents the secrets scanner (a truncated, non-real key header fixture + the scanner's own detection regex), which the hook flags as a false positive. Kept the canonical config in `DEVELOPMENT.md` §3.2 in sync.
- **Verified:** `uv run pre-commit run --all-files` → all hooks Passed (exit 0).

### `chore: convert uv starter to src/packer layout + toolchain config`
- **Task 1.** Turned the bare `uv init` starter into a real `src/` project.
- Added packages: `src/packer/__init__.py`, `src/packer/engine/__init__.py`, `src/packer/engine/common/__init__.py`.
- Removed the `main.py` starter.
- Expanded `pyproject.toml`: runtime deps (numpy, scipy, safetensors, huggingface-hub, hydra-core, omegaconf, pydantic); `dev` group (ruff, mypy, pytest, pytest-cov, hypothesis, import-linter, pre-commit); hatchling build targeting `src/packer`; ruff (py310, curated lint set), mypy (strict), and pytest config (markers, `testpaths`).
- Added `tests/unit/test_smoke.py` (package-import smoke test) and `tests/conftest.py`.
- **Verified:** `uv sync` OK; `uv run pytest tests/unit/test_smoke.py` → 1 passed; `uv run ruff check .` → clean; `uv run mypy src` → no issues.

### `docs: add implementation progress log + branching strategy`
- **Branch:** `phase-0-foundations`
- Added `docs/implementation/` — the living implementation record:
  - `README.md` — folder purpose + branching/commit strategy (per-phase branches, one commit per plan task, `--no-ff` merge to `main`, quality gate on every commit).
  - `STATUS.md` — progress board for all 7 phases and the 12 Phase-0 tasks.
  - `CHANGELOG.md` — this file.
- No code yet; establishes the workflow that every subsequent commit follows.
