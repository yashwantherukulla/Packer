# Packer — Detailed System Design

> **A step above code.** This document specifies *how the pieces fit together*: the architectural style, the shared contracts every module depends on, the dependency rules, and — module by module — which classes and functions exist, what they depend on, and how they collaborate. It exists so a developer can add a new detection signal, malware scanner, decode strategy, model architecture, or storage backend **without rewriting existing logic**.
>
> **Read after** [ARCHITECTURE.md](ARCHITECTURE.md) (the *what*) and the [phase specs](specs/) (per-phase scope). Where ARCHITECTURE gives the map, this gives the wiring diagram.
>
> **Guiding requirement (from the brief):** research project, many moving parts → maximize modularity, minimize rewrites. Every design choice below is justified against that.

## Table of contents

1. [Architectural style & the Dependency Rule](#1-architectural-style--the-dependency-rule)
2. [SWE principles, applied concretely](#2-swe-principles-applied-concretely)
3. [The shared kernel](#3-the-shared-kernel)
4. [Module map & dependency graph](#4-module-map--dependency-graph)
5. [Subsystem designs](#5-subsystem-designs)
6. [End-to-end interaction flows](#6-end-to-end-interaction-flows)
7. [Cross-cutting concerns in depth](#7-cross-cutting-concerns-in-depth)
8. [Extensibility playbook — "to add X"](#8-extensibility-playbook--to-add-x)
9. [Testing architecture](#9-testing-architecture)
10. [Enforcement & guardrails](#10-enforcement--guardrails)
11. [Conventions summary](#11-conventions-summary)

---

## 1. Architectural style & the Dependency Rule

Packer uses **hexagonal (ports & adapters) architecture** with a clean-architecture dependency direction. Four concentric layers; **dependencies only ever point inward.**

```
          ┌──────────────────────────────────────────────────────────┐
          │  DELIVERY            frontend/ (React)                     │  outermost
          │  ────────            depends only on the API's OpenAPI     │
          │   ┌──────────────────────────────────────────────────┐   │
          │   │  ORCHESTRATION   api/  ·  workers/                │   │
          │   │  ─────────────   transport, jobs, DI wiring       │   │
          │   │   ┌──────────────────────────────────────────┐   │   │
          │   │   │  ADAPTERS    concrete implementations of  │   │   │
          │   │   │  ────────    engine PORTS:                │   │   │
          │   │   │   Docker sandbox · Redis progress ·       │   │   │
          │   │   │   filesystem/S3 store · HF model loader   │   │   │
          │   │   │   ┌──────────────────────────────────┐   │   │   │
          │   │   │   │  CORE (engine domain)            │   │   │   │  innermost
          │   │   │   │  ────                            │   │   │   │
          │   │   │   │  pure logic + PORT protocols     │   │   │   │
          │   │   │   │  pack · detect · extract ·       │   │   │   │
          │   │   │   │  sandbox(logic) · report ·       │   │   │   │
          │   │   │   │  artifacts · common(kernel)      │   │   │   │
          │   │   │   └──────────────────────────────────┘   │   │   │
          │   │   └──────────────────────────────────────────┘   │   │
          │   └──────────────────────────────────────────────────┘   │
          └──────────────────────────────────────────────────────────┘
```

**The Dependency Rule (enforced by `import-linter`, see §10):**

| Layer | May import | May **not** import |
|---|---|---|
| `engine.common` (kernel) | stdlib, numpy, pydantic | anything else in `packer` |
| `engine.*` (core logic) | `engine.common`, its own submodules, the ports it declares | `api`, `workers`, `torch`-in-detect*, Docker/Redis/SQLAlchemy, concrete adapters |
| adapters (`*.adapters`, worker-side impls) | the engine ports they implement + their external lib (docker, redis, boto3, sqlalchemy) | other adapters, `api` routers |
| `api`, `workers` | `engine` (via ports), adapters, schemas | frontend |
| `frontend` | the generated OpenAPI client only | anything Python |

\* `detect` may import `numpy`/`scipy` but **must not** import `torch`'s forward/generate — the no-inference boundary (§5.4).

**Why this style for a research project:** the volatile, experiment-heavy parts (which signals, which scanners, which training tricks, which transport) live in outer rings and behind ports. The stable core — the `.pak` contract, the report shape, the value objects — sits at the center and rarely changes. You can throw away and rewrite a whole adapter (swap Docker→gVisor, Celery→Arq, filesystem→S3) **without touching engine logic**, and add new experiments as new plugins **without touching the core**.

---

## 2. SWE principles, applied concretely

Not abstractions — here's exactly where each shows up.

| Principle | Where it lives in Packer |
|---|---|
| **Single Responsibility** | One class per job: `ByteBPETokenizer` tokenizes, `OverfitTrainer` trains, `ResidualCapturer` captures residuals, `PakWriter` serializes. A "signal" computes one score; the `Ensemble` only combines. |
| **Open/Closed** | New signals/scanners/extractors/codecs/archs are **added**, never **edited in**. They self-register in a `Registry` (§3.4); the pipelines iterate the registry. Adding capability = new file + config line; zero edits to orchestration. |
| **Liskov Substitution** | Every plugin honors a `Protocol`; the pipeline treats `DockerSandboxRunner` and a future `GvisorSandboxRunner` identically. Contract tests (§9) assert substitutability. |
| **Interface Segregation** | Ports are narrow: a `Signal` only sees a `WeightAccessor` (never a forward-callable); a `Scanner` only sees files; the engine sees an `ArtifactStore` with `put/get/open`, not a full S3 client. |
| **Dependency Inversion** | Engine depends on **port protocols**, not concretions. Workers inject `RedisProgress`, `FilesystemArtifactStore`, `DockerSandboxRunner`. Tests inject fakes. Nothing in `engine` imports `redis`, `docker`, or `sqlalchemy`. |
| **DRY** | One generic `Registry[T]`. One generic `run_engine_job()` worker wrapper (job lifecycle written **once**). One `DecodeStrategy` shared by Part-1 verify and Part-3 exact extract. One `WeightAccessor` all signals reuse. One unified `Report` renderer for detect + scan. |
| **Separation of concerns** | Transport (HTTP/Celery) ⟂ logic (engine) ⟂ config (Hydra) ⟂ persistence (repositories). Each can change independently. |
| **Immutability / value objects** | Data contracts (`Manifest`, `SignalResult`, `Finding`, `ProgressEvent`) are frozen dataclasses / immutable pydantic models. Passed by value, never mutated across boundaries. |
| **Explicitness & fail-fast** | Ports are typed `Protocol`s; mypy-strict. Malformed inputs raise the typed error taxonomy (§3.3) at the boundary, not deep inside. |
| **Determinism as a seam** | `Clock` and `Rng` are injected (§3.7), so training/decoding/reporting are reproducible and testable — critical for the byte-exact and calibration guarantees. |
| **Versioned contracts** | `manifest.pak_version`, `report.schema_version`, `calibration.params_version`. Readers dispatch on version; old artifacts keep working. |

---

## 3. The shared kernel

Everything depends on `engine.common` (plus `engine.artifacts` and `engine.report` for the cross-part contracts). This is the *stable center*. Changing it is expensive by design — so it stays small and carefully chosen.

### 3.1 Value objects & data contracts

Frozen, transport-agnostic, defined once, produced by one subsystem and consumed by others.

| Type | Defined in | Produced by | Consumed by | Versioned |
|---|---|---|---|---|
| `ModelRef` | common.types | api/callers | models.loader | — |
| `LoadedModel` | models | models.loader | detect, extract, pack(verify) | — |
| `SerializedCorpus` (bytes + `FileMap`) | pack.corpus | pack.corpus | pack, extract(exact) | — |
| `Residuals` | common.types | pack.residuals | artifacts, extract | — |
| `Manifest` | artifacts | pack | artifacts, detect(meta), extract | ✅ `pak_version` |
| `PakBundle` | artifacts | artifacts.reader | detect, extract | — |
| `SignalResult{name,score,confidence,evidence}` | detect.signals.base | each `Signal` | detect.ensemble, report | — |
| `Verdict{label,score,confidence}` | detect | detect.ensemble | report | — |
| `Finding{severity,rule,file,line,note}` | sandbox.findings | scanners, dynamic | sandbox.scorer, report | — |
| `SandboxResult` | sandbox.runner | SandboxRunner impls | dynamic analyzer | — |
| `Report{kind,schema_version,...}` | report | detect, sandbox | api, frontend | ✅ `schema_version` |
| `ProgressEvent{job_id,step,pct,detail,ts}` | common.progress | engine (via callback) | workers→redis→ws→frontend | — |
| `JobSpec` / `JobRecord` | api.jobs | api | workers, api, frontend | — |

**Rule:** these cross module boundaries; **bare `dict`s do not.** A function returning "some results" returns a typed value object.

### 3.2 Ports (protocol) catalog

The seams. Declared in the engine, implemented by adapters, injected at composition time.

```python
# engine/common/ports.py  (Protocols — structural typing, no inheritance required)

class ProgressCallback(Protocol):
    def __call__(self, *, step: str, pct: float, detail: str | None = None) -> None: ...

class ArtifactStore(Protocol):
    def put_pak(self, bundle: "PakBundle") -> str: ...          # -> artifact_id
    def open_pak(self, artifact_id: str) -> "PakBundle": ...
    def put_blob(self, key: str, data: bytes) -> str: ...
    def open_blob(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...

class ModelLoader(Protocol):
    def load(self, ref: "ModelRef", *, allow_pickle: bool = False) -> "LoadedModel": ...

class SandboxRunner(Protocol):
    def run(self, unit: "ExecUnit", policy: "SandboxPolicy") -> "SandboxResult": ...

class Clock(Protocol):
    def now(self) -> datetime: ...

class Rng(Protocol):
    def seed(self) -> int: ...                                  # deterministic seed source
```

And the **plugin protocols** (each backs a registry, §3.4):

```python
class Signal(Protocol):                 # detect
    name: str
    def analyze(self, weights: "WeightAccessor") -> "SignalResult": ...

class Scanner(Protocol):                # sandbox static
    name: str
    def scan(self, files: "FileSet") -> list["Finding"]: ...

class DecodeStrategy(Protocol):         # pack verify + extract exact (SHARED)
    def reconstruct(self, model: "InferenceModel", residuals: "Residuals",
                    length: int) -> bytes: ...

class ResidualCodec(Protocol):          # pack + extract
    def encode(self, residuals: "Residuals") -> bytes: ...
    def decode(self, blob: bytes) -> "Residuals": ...

class ModelArchitecture(Protocol):      # pack
    def build(self, cfg: "ArchCfg") -> "TrainableModel": ...

class Tokenizer(Protocol):              # pack + extract
    def train(self, corpus: bytes, vocab_size: int) -> None: ...
    def encode(self, data: bytes) -> list[int]: ...
    def decode(self, tokens: list[int]) -> bytes: ...

class Extractor(Protocol):              # extract
    confidence_class: str               # "exact" | "blind"
    def extract(self, target: "ExtractTarget") -> "Extraction": ...
```

Every port is **small** (interface segregation) and **has at least two conceivable implementations** (that's the test for whether it should be a port at all).

### 3.3 Error taxonomy & handling strategy

```python
# engine/common/errors.py
class PackerError(Exception):
    """Base. Carries a stable `.code` (str) and safe `.context` (dict)."""
class ConfigError(PackerError): ...
class LoadError(PackerError): ...
class UnsafeModelError(LoadError): ...          # pickle/.bin without opt-in
class PackError(PackerError): ...               # incl. round-trip verification failure
class ReconstructionError(PackerError): ...
class ScanError(PackerError): ...
class SandboxError(PackerError): ...            # container failed to start, policy violation setup
```

- **Engine raises typed errors**; it never `print`s, never returns error dicts, never swallows.
- **Adapters** wrap third-party exceptions into the taxonomy at their boundary (`docker.errors.APIError` → `SandboxError`).
- **Workers** catch `PackerError`, mark the job `failed` with `error.code`/message, and re-raise unknowns after logging (so they surface, not silently pass).
- **API** maps `PackerError.code` → HTTP problem+json; `UnsafeModelError` → 422, `ConfigError` → 400, unknown → 500.
- One rule: **an exception crossing a layer boundary is either a `PackerError` or a bug.**

### 3.4 The generic `Registry` — the linchpin of extensibility

The single mechanism that makes the system open/closed. One generic class; one instance per plugin family.

```python
# engine/common/registry.py
T = TypeVar("T")

class Registry(Generic[T]):
    def __init__(self, kind: str) -> None: self._kind, self._factories = kind, {}
    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def deco(cls: type[T]) -> type[T]:
            if name in self._factories: raise ConfigError(f"dup {self._kind}: {name}")
            self._factories[name] = cls; return cls
        return deco
    def create(self, name: str, **kwargs) -> T:
        if name not in self._factories: raise ConfigError(f"unknown {self._kind}: {name}")
        return self._factories[name](**kwargs)
    def names(self) -> list[str]: return sorted(self._factories)

# engine/common/registries.py  — the canonical instances
SIGNAL_REGISTRY:   Registry["Signal"]         = Registry("signal")
SCANNER_REGISTRY:  Registry["Scanner"]        = Registry("scanner")
DECODE_REGISTRY:   Registry["DecodeStrategy"] = Registry("decode_strategy")
CODEC_REGISTRY:    Registry["ResidualCodec"]  = Registry("residual_codec")
ARCH_REGISTRY:     Registry["ModelArchitecture"] = Registry("architecture")
TOKENIZER_REGISTRY:Registry["Tokenizer"]      = Registry("tokenizer")
EXTRACTOR_REGISTRY:Registry["Extractor"]      = Registry("extractor")
STORE_REGISTRY:    Registry["ArtifactStore"]  = Registry("artifact_store")
SANDBOX_REGISTRY:  Registry["SandboxRunner"]  = Registry("sandbox_runner")
```

Registration is co-located with the plugin:

```python
# engine/detect/signals/spectral.py
@SIGNAL_REGISTRY.register("spectral")
class SpectralSignal:
    name = "spectral"
    def analyze(self, weights: WeightAccessor) -> SignalResult: ...
```

Pipelines never name concrete classes — they ask the registry for the **config-enabled** subset:

```python
signals = [SIGNAL_REGISTRY.create(n) for n in cfg.detect.enabled_signals]
```

Plugins are discovered by **importing the package** (a `signals/__init__.py` that imports each module, or an entry-point scan). Adding `enabled_signals: [..., "my_new_signal"]` in Hydra turns it on. **This is why "little need to rewrite logic" holds** — the extension points are registries, and the orchestration is written against the abstract registry, not the concretions.

### 3.5 Config-as-DI: Hydra composition + the Assembler

Hydra is the **dependency-injection container**. Config selects *which* adapters/plugins and *with what params*; a small `Assembler` turns composed config into wired objects. The engine receives already-constructed ports — it does no lookup itself.

```python
# api/composition.py (orchestration layer — the ONLY place adapters are chosen)
def assemble_ports(cfg: DictConfig) -> EnginePorts:
    store   = STORE_REGISTRY.create(cfg.store.name, **cfg.store.params)
    sandbox = SANDBOX_REGISTRY.create(cfg.sandbox.runner, **cfg.sandbox.params)
    loader  = HFModelLoader(allow_pickle=cfg.models.allow_pickle)
    return EnginePorts(store=store, sandbox=sandbox, loader=loader)
```

- `EnginePorts` is a frozen dataclass bundling the ports an engine call needs. Engine entrypoints take `(inputs, cfg_subset, ports, progress)`.
- Hydra `_target_` + `hydra.utils.instantiate` is used for structured object graphs where helpful; the `Registry` handles the plugin-name → class case.
- **Swapping an adapter is a one-line config change**, e.g. `store.name: s3` — no code edits.

### 3.6 Progress / eventing model

```
engine call ──progress(step=,pct=,detail=)──▶ ProgressCallback (injected)
                                               ├─ NullProgress          (default / pure tests)
                                               ├─ RecordingProgress      (asserts in tests)
                                               └─ RedisProgress(job_id)  (workers)
                                                     │ publishes ProgressEvent JSON
                                                     ▼  redis channel  progress:{job_id}
API WebSocket hub  ── subscribes ──▶ fans out to connected clients ──▶ frontend useJobProgress
```

The engine emits *semantic* progress (`step="train", pct=0.4, detail="epoch 80/200 loss=0.02"`) and knows nothing about Redis, job ids, or sockets. The worker binds a `RedisProgress(job_id)` before calling the engine. This is DIP + separation of concerns for observability.

### 3.7 Determinism seams

Byte-exact packing and reproducible calibration require controlled nondeterminism:

- `Rng` port supplies seeds; training, tokenizer init, and any sampling draw from it. Tests inject a fixed-seed `Rng`; production seeds from config and records the seed in the manifest.
- `Clock` port supplies timestamps (manifest `created_utc`, report times). Tests inject a frozen clock → stable fixtures.
- Torch determinism flags are set centrally in `pack.trainer` when `cfg.deterministic=true`.
- Consequence: `pack(x)` twice with the same seed yields **byte-identical artifacts**, which is what the CI round-trip/determinism gate asserts (Phase 1).

---

## 4. Module map & dependency graph

```
engine/
  common/            ← kernel: types, ports, errors, registry, registries, progress, config_schema, logging
    ▲ (everything imports this; it imports nothing else in packer)
  models/            → common                     (LoadedModel, HFModelLoader adapter*, WeightAccessor)
  artifacts/         → common                     (Manifest, PakWriter/Reader, PakBundle)
  report/            → common                     (Report model + renderers)
  pack/              → common, models, artifacts  (Part 1)
  detect/            → common, models, artifacts, report   (Part 2; NO torch-forward)
  extract/           → common, models, artifacts, pack(decode/unpack reuse)   (Part 3a)
  sandbox/           → common, report             (Part 3b; SandboxRunner is a PORT here)
  sandbox/adapters/  → sandbox(port), docker       (DockerSandboxRunner)   ← adapter ring
api/
  schemas/ routers/ jobs/ ws/ db/ composition.py  → engine (ports), adapters
workers/
  tasks.py  runner.py                              → engine (ports), adapters, api.jobs(repos)
frontend/                                          → OpenAPI client only
```

\* `HFModelLoader` is an adapter but lives near `models/` for cohesion; it depends on `transformers`/`safetensors`, which is allowed *only* in that adapter module, not across `detect`.

**Acyclic by construction.** `import-linter` contracts (§10) fail CI if any arrow reverses (e.g., if `engine.detect` ever imports `api`, or a signal imports `torch`).

Key reuse edges (DRY made visible):
- `extract` → `pack` : the exact extractor reuses `pack.unpacker.Unpacker` and the shared `DecodeStrategy`. No second decode implementation exists.
- `detect` & `sandbox` → `report` : both emit the same `Report` type; the frontend has one renderer.
- everyone → `common.registry` : one plugin mechanism.

---

## 5. Subsystem designs

Each subsection: the classes, their responsibilities, collaborators, and a mini interaction sketch.

### 5.1 `models/` — loading & weight access

| Class / fn | Responsibility | Collaborators |
|---|---|---|
| `HFModelLoader` (impl of `ModelLoader`) | Resolve `ModelRef` (hf-id \| path \| `.pak`) → `LoadedModel`; safetensors-first; raise `UnsafeModelError` on pickle w/o opt-in | safetensors, huggingface_hub |
| `LoadedModel` (frozen) | Holds `tensors`, `config`, `source`, `format`; lazy tensor access | — |
| `WeightAccessor` | **The abstraction all detection signals share.** Yields matrices *by semantic role* so signals don't re-parse tensor names | `LoadedModel` |

`WeightAccessor` is the ISP win for Part 2:

```python
class WeightAccessor:
    def __init__(self, model: LoadedModel): ...
    def attention_matrices(self) -> Iterator[tuple[str, np.ndarray]]: ...
    def mlp_matrices(self) -> Iterator[tuple[str, np.ndarray]]: ...
    def embedding(self) -> np.ndarray: ...
    def unembedding(self) -> np.ndarray: ...
    def config(self) -> dict: ...
    # NOTE: exposes tensors only — NO forward(), NO generate(). This is the
    # structural enforcement of the no-inference rule (§5.4).
```

Signals depend on `WeightAccessor`, not `LoadedModel` or raw tensors → new architectures need role-mapping in *one* place, not in every signal.

### 5.2 `artifacts/` — the `.pak` contract

| Class / fn | Responsibility |
|---|---|
| `Manifest` (pydantic, versioned) | Typed model of `manifest.json`; `pak_version` gate; validation on read |
| `PakWriter` | `write(path, tensors, tokenizer, manifest, residual_blob)` → directory/tar |
| `PakReader` | `read(path) -> PakBundle`; validates version; refuses unknown future versions with a clear error |
| `PakBundle` (frozen) | `tensors`, `tokenizer`, `manifest`, `residuals` |
| `metrics.build_metrics()` | Computes honest sizes (`original`, `gzip`, `model`, `artifact`) for the manifest |

`PakReader`/`PakWriter` are the **only** code that knows the on-disk layout — pack, detect, and extract go through them. Change the container format in one place.

### 5.3 `pack/` — Part 1

```
Packer (orchestrator)
  ├─ CorpusSerializer  (MarkerCorpusSerializer)   repo <-> bytes + FileMap
  ├─ Tokenizer         (ByteBPETokenizer)         bytes <-> tokens         [TOKENIZER_REGISTRY]
  ├─ ModelArchitecture (TinyDecoder)              build trainable model    [ARCH_REGISTRY]
  ├─ OverfitTrainer                               train_to_memorize(...)
  ├─ ResidualCapturer                             teacher-forced diff → Residuals
  ├─ ResidualCodec     (DeltaVarintCodec)         Residuals <-> bytes      [CODEC_REGISTRY]
  ├─ DecodeStrategy     (TeacherForcedGreedy)     reconstruct(...)         [DECODE_REGISTRY] (SHARED w/ extract)
  └─ PakWriter                                    persist artifact
```

**`Packer.pack(root, cfg, ports, progress)` collaboration:**

```
1  corpus  = CorpusSerializer.serialize(root)                       # bytes + FileMap
2  tok     = TOKENIZER_REGISTRY.create(cfg.tokenizer); tok.train(corpus.bytes, cfg.vocab)
3  tokens  = tok.encode(corpus.bytes)
4  model   = ARCH_REGISTRY.create(cfg.arch).build(cfg.arch)         # from-scratch, seeded via Rng
5  OverfitTrainer.train(model, tokens, cfg.train, progress)         # emits progress
6  resid   = ResidualCapturer.capture(model, tokens, DECODE_REGISTRY.create(cfg.decode))
7  # ── mandatory in-process verification (fail-fast) ──
   rebuilt = Unpacker(decode, codec).reconstruct(model, resid, len(tokens))
   assert rebuilt == corpus.bytes  else raise PackError            # byte-exact guarantee
8  manifest = Manifest(... metrics=build_metrics(corpus, model, blob) ...)
9  artifact_id = ports.store.put_pak(PakBundle(model.tensors, tok, manifest, codec.encode(resid)))
```

Step 7 is why losslessness is invariant to training quality (ADR-006): the same `DecodeStrategy` + `Unpacker` used by Part 3 is exercised *before* the artifact is accepted. `Unpacker` lives in `pack/` and is imported by `extract/` — **one decode path, two callers.**

### 5.4 `detect/` — Part 2 (inference-free)

```
Detector (orchestrator)
  ├─ WeightAccessor                     (from models/)
  ├─ Signal[]   from SIGNAL_REGISTRY    spectral · weight_norm · embedding · rank · metadata
  ├─ Ensemble                           combine SignalResult[] via CalibrationParams
  ├─ Calibrator                         fit params on labeled fixtures (offline)
  └─ DetectReportBuilder                → Report(kind="detect")
```

**`Detector.detect(model_ref, cfg, ports)` collaboration:**

```
1  model    = ports.loader.load(model_ref)          # tensors only
2  weights  = WeightAccessor(model)                  # NO forward-callable exposed
3  results  = [SIGNAL_REGISTRY.create(n).analyze(weights) for n in cfg.enabled_signals]
4  calib    = CalibrationStore.load(cfg.calibration_version)
5  verdict  = Ensemble.score(results, calib)
6  return DetectReportBuilder.build(verdict, results)  # per-signal evidence + confidence + limitation note
```

**No-inference enforcement is layered:**
1. *Structural*: `Signal.analyze` receives a `WeightAccessor` with no forward/generate method.
2. *Dependency*: `import-linter` forbids `engine.detect` from importing torch's inference API.
3. *Behavioral test* (CI gate): run `detect` with the model's `forward`/`generate` monkeypatched to raise; it must still complete (Phase 2).

Each `Signal` is independently unit-testable against synthetic matrices (e.g., feed a rank-1-perturbed matrix; assert `spectral` flags an outlier singular value). Adding a signal touches **only** a new file + `enabled_signals`.

### 5.5 `extract/` + `sandbox/` — Part 3

**Extract (3a):**

```
ExtractionService
  ├─ chooses Extractor via EXTRACTOR_REGISTRY + presence of manifest
  ├─ ExactExtractor (confidence_class="exact")  → reuses pack.Unpacker + DecodeStrategy + ResidualCodec
  └─ BlindExtractor (confidence_class="blind")  → heuristic decode; labels low/med confidence; may be partial
        └─ InferenceModel  (a thin forward-only wrapper; ONLY Part 3 may run inference)
```

`ExactExtractor.extract` is ~5 lines because it delegates to `pack.Unpacker` — **the payoff of sharing `DecodeStrategy`.** `BlindExtractor` is where new heuristics get added (its own small strategy set), isolated from exact logic.

**Sandbox (3b):**

```
ScanPipeline (orchestrator)
  ├─ StaticAnalyzer   runs Scanner[] from SCANNER_REGISTRY over FileSet → Finding[]
  │     ast_rules · bandit · semgrep · yara · secrets
  ├─ DynamicAnalyzer  for each ExecUnit: SandboxRunner.run(unit, policy) → SandboxResult → Finding[]
  │     └─ SandboxRunner PORT  ── DockerSandboxRunner (adapter)  [SANDBOX_REGISTRY]
  ├─ RiskScorer       combine static+dynamic Finding[] via RiskCalibration → RiskReport
  └─ ScanReportBuilder → Report(kind="scan")
```

`SandboxRunner` is a **port** so the substrate (Docker today; gVisor/e2b later) swaps via config with zero pipeline changes (ADR-008 keeps Docker, but the seam is there). `SandboxPolicy` is a frozen config object (`--network=none`, mem/cpu/pids/timeout, caps) sourced from Hydra `engine/sandbox/docker.yaml`. Each `Scanner` is a plugin; adding a new rule engine = new scanner + config, no orchestration edits.

**`ScanPipeline.run(target, cfg, ports)`:**

```
1  extraction = ExtractionService.extract(target)                 # exact | blind
2  fileset    = FileSet.from_extraction(extraction)
3  static     = StaticAnalyzer.scan(fileset, cfg.enabled_scanners)
4  dynamic    = [DynamicAnalyzer.analyze(u, ports.sandbox, cfg.policy) for u in fileset.exec_units()]
5  risk       = RiskScorer.score(static, flatten(dynamic), cfg.risk_calibration)
6  return ScanReportBuilder.build(extraction, static, dynamic, risk)  # surfaces static/dynamic disagreement
```

### 5.6 `report/` — unified reporting

One `Report` value object, two `kind`s, one set of renderers → the frontend has a single report view that branches on `kind`.

```python
class Report(BaseModel):            # frozen, versioned
    kind: Literal["detect", "scan"]
    schema_version: str
    verdict: VerdictBlock           # label + score + confidence
    sections: list[ReportSection]   # signal breakdowns | findings tables | behavior
    evidence: dict
    limitations: list[str]          # e.g. detect's "signature not proof" note
# renderers: to_json() (API), to_text() (CLI-style logs), + frontend consumes JSON
```

Detect and scan builders both emit `Report`; nothing downstream special-cases them beyond `kind`. Add a new analysis kind later → add a `kind` + a builder; renderer and API are generic.

### 5.7 `api/` + `workers/` — orchestration

**The generic job wrapper (DRY: job lifecycle written once):**

```python
# workers/runner.py
def run_engine_job(job_id: str, engine_call: Callable[[EnginePorts, ProgressCallback], Report | str]):
    job = JobRepository.get(job_id); JobRepository.mark_running(job_id)
    progress = RedisProgress(job_id)
    ports = assemble_ports(load_cfg())
    try:
        result = engine_call(ports, progress)              # <-- the ONLY per-task difference
        ref = persist_result(job, result)                  # artifact/report row
        JobRepository.mark_succeeded(job_id, ref)
    except PackerError as e:
        JobRepository.mark_failed(job_id, code=e.code, msg=str(e))
    except Exception as e:                                  # unknown → fail loudly + re-raise
        JobRepository.mark_failed(job_id, code="internal", msg=str(e)); log.exception(...); raise
```

The four Celery tasks are one-liners that supply `engine_call`:

```python
@app.task(queue="gpu")
def pack_task(job_id, spec):    run_engine_job(job_id, lambda p, pr: Packer().pack(spec.root, cfg.pack, p, pr))
@app.task(queue="default")
def detect_task(job_id, spec):  run_engine_job(job_id, lambda p, pr: Detector().detect(spec.model_ref, cfg.detect, p))
# extract_task, scan_task likewise
```

Adding a new engine operation = a new one-line task + route; **the lifecycle, error handling, progress wiring, and persistence are never rewritten.**

**API layer:**

| Component | Responsibility |
|---|---|
| routers | validate (Pydantic) → `JobService.create` → enqueue → return `JobRecord`. No logic. |
| `JobService` | create/query/transition; dedup by input hash (config-gated) |
| repositories | `JobRepository`, `ReportRepository`, `ArtifactRepository`, `ModelRepository` over SQLAlchemy — an interface so tests use in-memory fakes |
| `ws/hub` | subscribe `progress:{id}` on Redis → fan out to WS clients; reconcile via `/jobs/{id}` on reconnect |
| `composition.py` | the DI root — the one place adapters are chosen from config |

### 5.8 `frontend/` — delivery

Layered, feature-oriented, thin:

```
lib/         api base, ws client, formatters, verdict/risk color scale
api/         generated OpenAPI client + typed thin wrappers
hooks/       useJob(id) [Query] · useJobProgress(id) [WS] · useSubmit{Pack,Detect,Scan}
components/   presentational, dumb: Uploader · JobProgress · VerdictBadge · SignalBreakdown · FindingsTable · BehaviorPanel
pages/        composition only: Pack · Detect · ExtractScan · Jobs · Report
```

- **Server state** via TanStack Query (source of truth on reconnect); **live progress** via WebSocket. One `ReportView` renders both report kinds from JSON (`kind`-branch).
- **Types come from OpenAPI generation** → API and UI cannot silently drift (a CI check regenerates and diffs).
- Components are presentational; data-fetching lives in hooks → components are trivially testable with fixture props.

---

## 6. End-to-end interaction flows

### 6.1 Pack (sequence)

```
Browser ──POST /pack (zip)──▶ router ──▶ JobService.create(queued) ──▶ pack_task.delay(job_id)
router ◀── 202 {job_id} ── Browser opens WS /ws/jobs/{id}
worker: run_engine_job → RedisProgress(id) → Packer.pack(...)
   serialize→tokenize→build→train(progress 0..0.8)→capture→VERIFY(byte-exact)→write pak
   each progress() → redis progress:{id} → ws hub → Browser JobProgress bar
worker: ArtifactRepository.insert(pak) → JobRepository.mark_succeeded
Browser: Query /jobs/{id} → artifact card (honest sizes) + download
```

### 6.2 Detect (sequence)

```
Browser ──POST /detect {model_ref}──▶ router ──▶ JobService.create ──▶ detect_task.delay
worker: run_engine_job → Detector.detect
   loader.load (tensors only) → WeightAccessor → [signals].analyze → Ensemble.score(calib) → Report
worker: ReportRepository.insert(kind=detect) → mark_succeeded
Browser: ReportView renders verdict + per-signal evidence + "signature not proof" limitation
```

### 6.3 Extract + Scan (sequence)

```
Browser ──POST /scan {model_ref, artifact?}──▶ router ──▶ JobService.create ──▶ scan_task.delay
worker: ScanPipeline.run
   ExtractionService → Exact (reuse pack.Unpacker) | Blind
   StaticAnalyzer → [scanners].scan → Finding[]
   DynamicAnalyzer → DockerSandboxRunner.run(policy: no-net/read-only/capped) → SandboxResult → Finding[]
   RiskScorer → RiskReport → Report(kind=scan)
Browser: ReportView renders file tree (byte-exact✓ | best-effort) + FindingsTable + BehaviorPanel
```

### 6.4 The E2E chain (Phase 6 gate) — object-level

`Packer.pack(toy_repo)` → `Detector.detect(artifact)` = MEMORIZED-LIKELY → `ExactExtractor.extract(artifact)` byte-identical → `ScanPipeline.run` flags planted malicious unit, passes benign — all driven through the API/UI. Each arrow is an independent, separately-tested unit; the chain just composes them.

---

## 7. Cross-cutting concerns in depth

- **Config layering.** Hydra composes `conf/` groups → `DictConfig`. Structured `@dataclass` schemas (registered in `ConfigStore`) give type-checked composition. The `Assembler` (§3.5) is the *only* consumer that turns config into wired adapters; engine code receives typed cfg subsets + ports, never reads global config.
- **Logging & correlation.** A `correlation_id` (= job id) is generated at API ingress, stored on the job row, passed to the worker, bound into the logger, and included in every `ProgressEvent`. Structured JSON logs in prod. One request/job is traceable end-to-end.
- **Storage & transactions.** `ArtifactStore`/`ModelStore` ports abstract bytes; repositories abstract rows. Job state transitions are transactional; artifact write (object store) then row insert (DB) — on failure the job is `failed` and any orphan blob is GC-eligible (a documented cleanup task).
- **Idempotency & dedup.** Optional: hash `(operation, inputs, cfg)`; a matching succeeded job can be returned instead of recomputing (config-gated). Keeps expensive training from re-running.
- **Cancellation & timeouts.** Jobs carry a cancel flag checked at progress checkpoints in long loops (training epochs); sandbox runs have hard wall-clock timeouts in the policy. Celery task time limits backstop.
- **Retries.** Idempotent light tasks (`detect`, `scan`) may auto-retry on infra errors; `pack` does not auto-retry (expensive, side-effecting) — it fails and surfaces.
- **Security posture** (recap, enforced across layers): safetensors-first at the loader; extracted code only ever runs via `SandboxRunner`; the sandbox policy is defense-in-depth; no engine layer has network or host-exec authority except through the sandbox port.

---

## 8. Extensibility playbook — "to add X"

The concrete payoff of the design. Each recipe lists files you **add** and the core files you **do not touch**.

| To add… | Add | Config | Don't touch |
|---|---|---|---|
| **A detection signal** | `detect/signals/<name>.py` with `@SIGNAL_REGISTRY.register` | `enabled_signals`, calibration | ensemble, other signals, runner |
| **A malware scanner** | `sandbox/static/<name>.py` with `@SCANNER_REGISTRY.register` | `enabled_scanners` | pipeline, scorer, other scanners |
| **A decode strategy** | `pack/decode/<name>.py` `@DECODE_REGISTRY.register` | `pack.decode` / `extract.decode` | packer, unpacker, extractors |
| **A residual codec** | `pack/codecs/<name>.py` `@CODEC_REGISTRY.register` | `pack.codec` | writer/reader, capturer |
| **A model architecture** | `pack/arch/<name>.py` `@ARCH_REGISTRY.register` | `pack.arch` | trainer, packer, tokenizer |
| **A storage backend** (S3, …) | `common/stores/<name>.py` impl `ArtifactStore` `@STORE_REGISTRY.register` | `store.name` | all engine logic, workers |
| **A sandbox substrate** (gVisor, e2b) | `sandbox/adapters/<name>.py` impl `SandboxRunner` `@SANDBOX_REGISTRY.register` | `sandbox.runner` | pipeline, scanners, scorer |
| **A new report kind** | a `ReportBuilder` emitting `Report(kind=...)` | — | renderer, API, repositories |
| **A new engine operation** | engine entrypoint + one-line Celery task + one route | queue routing | job lifecycle wrapper, WS, progress |
| **A transport swap** (Celery→Arq) | new task adapters calling `run_engine_job` logic | — | engine, ports, reports |

If a proposed change *isn't* on this table and seems to need core edits, that's the signal to introduce a new port/registry rather than special-case it — a design review checkpoint.

---

## 9. Testing architecture

The modular seams exist partly *to make testing cheap*. Test types map to layers:

- **Pure unit** (no I/O, fastest): every `Signal`, `Scanner`, `ResidualCodec`, `CorpusSerializer`, `Ensemble`, `RiskScorer` in isolation. Enabled by narrow ports + value objects.
- **Property-based** (Hypothesis): `pack→unpack` byte-exact over arbitrary bytes and tiny synthetic repos, incl. `epochs=1` (proves residual-guaranteed losslessness independent of convergence); `codec.decode(encode(r))==r`.
- **Contract tests**: one shared test suite per port, run against **every** implementation (e.g., all `SandboxRunner`s must block network, honor timeout; all `ArtifactStore`s must round-trip). Guarantees LSP — new adapters must pass the same suite.
- **Fakes over mocks**: `RecordingProgress`, `InMemoryArtifactStore`, `InMemoryJobRepository`, `FakeSandboxRunner` — small, honest test doubles enabled by the ports.
- **No-inference gate**: `detect` runs with forward/generate patched to raise (Phase 2).
- **Containment gate**: adversarial fixtures against the real `DockerSandboxRunner` (Phase 3/6) — net/fs/pid/mem/time escapes must fail.
- **Integration** (testcontainers Postgres/Redis): the job path end-to-end via the API.
- **E2E** (httpx + Playwright): the §6.4 chain.

Because logic is injected with fakes, **most tests need no Docker/DB/GPU** and run in milliseconds; only the deliberately-integration tests spin infra.

---

## 10. Enforcement & guardrails

Modularity that isn't enforced rots. These make the rules mechanical, checked in CI:

- **`import-linter`** contracts encode the Dependency Rule (§1, §4). Three contracts (canonical config in [DEVELOPMENT](DEVELOPMENT.md) §3.1):
  - **"engine is framework-agnostic"** (forbidden): `engine.*` may not import `api`, `workers`, `fastapi`, `celery`, `redis`, `sqlalchemy`, or `docker` — with a single `ignore_imports` carve-out for the sanctioned adapter edge `engine.sandbox.adapters.docker -> docker`.
  - **"detect runs no inference"** (forbidden): `engine.detect` may not import `torch.nn.functional`/generate paths.
  - **"clean layering"** (layers, high→low): `api > sandbox > extract > {pack | detect} > {models | artifacts | report} > common`. This deliberately encodes the DRY reuse edges — `extract` imports `pack`, `sandbox` imports `extract` — so `pack`/`extract`/`sandbox` are **not** mutually independent. `engine.common` sits at the bottom (imports nothing else in `packer`). `packer.workers` is intentionally **omitted** from the layered contract (it is a peer of `api` that imports `api.jobs`/`api.db`; its engine-purity is covered by the forbidden contract). `frontend` has no Python imports.
  Because import-linter requires referenced modules to exist, the contracts are introduced incrementally as modules land (Phase 0 → 2 → 3 → 4), always preserving this order. A reversed arrow fails `lint-imports` in CI.
- **mypy strict** across `src/` — ports are `Protocol`s, so mismatched implementations fail type-check, not runtime.
- **Registry duplicate/unknown guards** raise `ConfigError` early (start-up validation lists registered vs. enabled plugin names and fails on mismatch).
- **Schema versioning** on `Manifest` and `Report`: readers validate `*_version` and refuse unknown-future versions with a clear migration message.
- **ruff** rule sets (`B`, `SIM`, `PTH`, `RUF`, …) catch structural smells; **pre-commit** runs everything on commit.
- **Conventional Commits + atomic commits** keep changes reviewable per-plugin.

## 11. Conventions summary

- Value objects cross boundaries; **`dict` does not** (except opaque `evidence`/`context` payloads).
- Engine functions: `(inputs, cfg_subset, ports, progress)` in; typed value object out; raise the taxonomy on failure.
- One class = one responsibility; a file that grows two responsibilities gets split.
- New capability ⇒ new plugin in a registry ⇒ config to enable it. Editing orchestration to add a capability is a code smell.
- Adapters wrap third-party errors into `PackerError` at their boundary.
- Everything reproducible: seeds and timestamps come from injected `Rng`/`Clock`.
- 3.10-compatible syntax only (see [DECISIONS](DECISIONS.md), ADR-013).

---

*This design is the contract for how modules interact. If an implementation needs to violate it, that's an ADR-worthy decision — update [DECISIONS.md](DECISIONS.md), don't quietly bypass the seam.*
