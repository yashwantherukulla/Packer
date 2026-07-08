# Phase 3 — Extractor + Sandbox (Part 3)

> **Goal:** reconstruct stored code (exact from `.pak`, best-effort blind for foreign models), then execute it in a hardened Docker sandbox and score it for maliciousness via static + dynamic analysis.
> **Depends on:** Phase 0; Phase 1 (`.pak` format + `unpack`). Sandbox sub-track can start alongside Phase 1/2. **Blocks:** Phase 4 (API surface).
> **Part mapping:** Part 3.

---

## 1. Scope

**In scope**
- **Exact extraction** (manifest-driven) — reuses Phase-1 `unpack`.
- **Blind extraction** (foreign model, no manifest) — heuristic, confidence-labeled, possibly partial.
- **Docker sandbox**: image + hardened run policy (ADR-008).
- **Static scanners**: AST dangerous-construct heuristics, Bandit (Python), Semgrep (multi-language), YARA rules, secrets sweep.
- **Dynamic capture**: syscalls, filesystem diff, blocked network attempts, stdout/stderr, exit/timeout.
- **Combined risk scorer**: `benign | suspicious | malicious` + evidence, surfacing static/dynamic disagreement.

**Out of scope**
- Guaranteed exact recovery from arbitrary foreign models. Malware *family* classification. Sandbox for languages beyond the image's installed runtimes (documented).

---

## 2. Modules & interfaces

`engine/extract/exact.py`
```python
def extract_exact(pak_path: Path) -> dict[str, bytes]:
    """Deterministic reconstruction via Phase-1 unpack. Byte-exact. High confidence."""
```

`engine/extract/blind.py`
```python
@dataclass
class BlindExtraction:
    files: dict[str, bytes]     # candidate reconstructed files
    confidence: float           # low/medium
    notes: list[str]            # what was inferred/guessed

def extract_blind(model_ref, cfg, progress) -> BlindExtraction:
    """No manifest. Greedy/low-temp decode from BOS + candidate seeds; detect repeated
    file-boundary patterns; reconstruct candidates. Never claims byte-exactness."""
```

`engine/sandbox/runner.py`
```python
@dataclass
class SandboxResult:
    stdout: str; stderr: str; exit_code: int | None; timed_out: bool
    syscalls: list[str]         # from strace -f
    fs_writes: list[str]        # tmpfs diff
    net_attempts: list[str]     # blocked connection attempts
    duration_s: float

def run_in_sandbox(file_bytes: bytes, lang: str, cfg: "SandboxCfg") -> SandboxResult:
    """Run one unit in an ephemeral container with the hardened policy. Never runs
    anything on the host. Always applies: --network=none --read-only (+tmpfs)
    --memory --cpus --pids-limit --cap-drop=ALL --security-opt=no-new-privileges,
    non-root UID, wall-clock timeout."""
```

`engine/sandbox/static/` — `ast_rules.py`, `bandit_scan.py`, `semgrep_scan.py`, `yara_scan.py`, `secrets.py`, each returning `list[Finding]` (`{severity, rule, file, line, note}`).

`engine/sandbox/scorer.py`
```python
def score_maliciousness(static: list[Finding], dynamic: SandboxResult, cfg) -> "RiskReport":
    """Calibrated combine → verdict + evidence; flags static/dynamic disagreement."""
```

`engine/sandbox/pipeline.py`
```python
def extract_and_scan(model_ref, cfg, progress) -> "ScanReport":
    """exact|blind extract → per-file static + dynamic → combined report."""
```

---

## 3. Integration points

- **Exact extractor imports Phase-1 `unpack`** directly (no duplicate decode logic).
- **Sandbox image + policy come from Hydra `engine/sandbox/docker.yaml`** (ADR-008 flags). Runner uses the Docker SDK.
- **Risk + extraction results use the shared `engine/report/` model** (same as Part 2) for uniform API/UI rendering.
- The Docker image is built from `docker/sandbox/` and versioned; CI builds it for integration tests.

---

## 4. Testing plan

- **Exact extraction (correctness gate):** extracting a Phase-1 `.pak` equals the original repo byte-for-byte.
- **Sandbox containment (security gate):** a fixture that attempts a network connection has it **blocked** and *recorded*; a fixture that tries to write outside tmpfs fails; a fork-bomb hits `pids-limit`; an infinite loop hits the timeout. Escape attempts fail.
- **Static scanners:** planted patterns (e.g., `eval`, `subprocess` with network, base64-decoded exec, hardcoded secret) are flagged with correct severity; a benign file yields no high-severity findings.
- **Dynamic capture:** syscall trace + fs diff populated for a known behavior fixture.
- **Scorer calibration:** on a labeled fixture set (benign vs. malicious samples), report precision/recall; a planted malicious sample scores `malicious`, a benign one `benign`.
- **Blind extraction:** on a Phase-1 model *without* its manifest, extraction is labeled low/medium confidence and doesn't crash (partial output acceptable).

---

## 5. Development steps (ordered)

1. Sandbox image (`docker/sandbox/Dockerfile`) with pinned runtimes + `strace`, non-root user.
2. `run_in_sandbox` with the full hardened flag set; containment tests first (security before features).
3. Dynamic capture (syscalls via `strace -f`, tmpfs fs-diff, net-attempt log).
4. Static scanners (ast_rules → bandit → semgrep → yara → secrets), each with fixtures.
5. `extract_exact` (wrap Phase-1 unpack).
6. Risk scorer + calibration on benign/malicious fixtures.
7. `extract_and_scan` pipeline → `ScanReport`.
8. `extract_blind` (best-effort) last, clearly labeled.

---

## 6. Acceptance criteria (milestone gate)

- [ ] Exact extraction of a Phase-1 `.pak` is byte-identical.
- [ ] Sandbox enforces no-net, read-only, pid/mem/time limits — all verified by containment tests; escape attempts fail.
- [ ] Static + dynamic passes both run and merge into one `RiskReport` with evidence.
- [ ] A planted malicious fixture scores `malicious`; a benign fixture scores `benign`.
- [ ] Blind extraction runs on a foreign/manifest-less model, clearly labeled best-effort.

---

## 7. Risks

- **Sandbox escape** (R4) → defense-in-depth flags; containment tests are a hard gate; never execute on host; keep image minimal.
- **strace/eBPF availability in the container** → strace baked into the image; if a syscall trace is unavailable, degrade to fs-diff + net-log and note reduced fidelity.
- **Blind extraction low yield** (R3) → labeled best-effort; exact mode is the supported path.
- **Windows/Docker Desktop specifics** → runner tested against Docker Desktop; document required settings.
