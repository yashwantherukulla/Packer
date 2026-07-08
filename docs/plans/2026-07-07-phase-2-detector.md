# Phase 2 — Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide, **from weights and metadata only (no inference)**, whether a model carries a memorized-corpus signature — emitting a calibrated ensemble `Verdict{label, score, confidence}` with per-signal evidence, and a unified `Report` that states the "signature, not proof; cannot recover code" limitation. This phase also stands up the **shared reporting kernel** (`engine/report/`) that Phase 3 reuses.

**Architecture:** Hexagonal/clean layering (see [SYSTEM-DESIGN.md](../SYSTEM-DESIGN.md) §5.4, §5.6). `detect/` sits in the core ring above `models`/`artifacts`/`report`; it consumes the Phase-0 kernel (`WeightAccessor`, `SIGNAL_REGISTRY`, ports, errors) and produces five self-registering signals + an ensemble + calibration + a runner. The no-inference wall (ADR-007) is enforced three ways: structurally (signals only ever see a `WeightAccessor`, which exposes tensors — never `forward`/`generate`), by import-linter (`torch.nn.functional` forbidden in `detect`), and by a behavioral gate test. Everything is TDD; the value objects produced here (`SignalResult`, `Verdict`, `Report`) are consumed by Phase 3 (scan) and Phase 4 (API).

**Tech Stack:** Python 3.10.x, uv, numpy + scipy (already Phase-0 runtime deps — no `uv add`), pydantic v2 (report model + schema versioning), Hydra + OmegaConf (detect config group), pytest. Consumes Phase-0: `WeightAccessor`, `HFModelLoader`/`LoadedModel`, `SIGNAL_REGISTRY`, `Registry`, `Signal` port, `PackerError`/`ConfigError`, `ModelRef`, `EnginePorts`, `compose_config`.

## Global Constraints

*Every task's requirements implicitly include this section. Values copied verbatim from the specs/ADRs.*

- **Python 3.10.x only.** `requires-python = ">=3.10,<3.11"`; `.python-version` = `3.10`. No 3.11+ syntax (`tomllib`, `except*`, `Self`, `type` statement). `match`, `X | Y` unions, PEP 585 generics are fine.
- **uv for everything.** Add deps with `uv add` / `uv add --dev`; never `pip install`; commit `uv.lock`. Run via `uv run`. (Phase 2 adds **no** new deps — numpy/scipy/pydantic are already present.)
- **Quality on commit.** ruff (lint + format), mypy strict, import-linter run via pre-commit and CI.
- **Hydra owns all configuration.** Pydantic is for API wire schemas / manifest / report validation only.
- **safetensors-first.** Loading pickle/`.bin` requires an explicit `allow_pickle=True` opt-in and raises `UnsafeModelError` otherwise.
- **Value objects cross module boundaries; bare `dict`s do not** (except opaque `evidence`/`context`/`config` payloads). New code uses parameterized generics (`dict[str, object]`) to stay mypy-strict clean under `disallow_any_generics`.
- **The Dependency Rule** (SYSTEM-DESIGN §1/§4): `engine.detect` imports only `engine.common`, `engine.models`, `engine.artifacts`, `engine.report` (+ numpy/scipy/pydantic); never `api`/`workers`/adapters/`torch` inference. `engine.report` imports only `engine.common`. Enforced by import-linter.
- **Conventional Commits**, one logical change per commit.
- **Windows-native is the primary dev target;** use `pathlib`, never hardcode POSIX paths.

**Phase-2 specifics:**

- **NO inference.** `detect` reads weights + metadata only. Every `Signal.analyze` receives a `WeightAccessor` (tensors + config, no forward/generate). The import-linter "detect runs no inference" contract (`torch.nn.functional` forbidden) plus the **behavioral no-inference gate test** (Task 12) are the enforcement; neither may be weakened.
- **Calibrated, honest outputs.** Each signal returns `SignalResult{score∈[0,1], confidence∈[0,1], evidence}`. The ensemble outputs `Verdict{label∈{MEMORIZED-CODE-LIKELY, INCONCLUSIVE, UNLIKELY}, score, confidence}`. Accuracy is a **measured** number on fixtures, never a guarantee.
- **The report states its limits.** `DetectReportBuilder` always populates `Report.limitations` with the ADR-007 note: this is a memorization/overfitting *signature*, not proof; detection cannot recover the code; it cannot in general distinguish memorized code from memorized other data (Part 3 confirms via extraction).
- **Open/closed.** New signals self-register in `SIGNAL_REGISTRY`; the runner instantiates them via `SIGNAL_REGISTRY.create(n) for n in cfg.enabled_signals` — **no orchestration code names a concrete signal class.**
- **Signals are independently unit-tested against synthetic numpy matrices** (rank-1-perturbed → spectral flags an outlier singular value; random Gaussian ~ Marchenko–Pastur → low anomaly; low-rank → rank signal fires; concentrated embedding → embedding signal fires).

**Cross-phase assumption (calibration fixtures):** Phase 1's fixture task produces **≥3 memorized `.pak`s + ≥2 control models** (random-init, normal-trained) under `tests/**/fixtures/` (phase-1 spec §1, §3). Phase 2's `Calibrator.calibrate` / `evaluate` consume these. The **unit** tests in this plan do **not** depend on those fixtures existing (they use synthetic in-memory `SignalResult` rows); a single **integration-marked** calibration test (Task 10) exercises the real fixtures and **skips** if the fixture directory is empty, so Phase 2 can be implemented and merged before/independently of Phase 1's fixtures landing.

## File Structure

```
conf/
  config.yaml                              # MODIFY: add `engine/detect: ensemble` to defaults
  engine/detect/ensemble.yaml              # NEW: enabled_signals + calibration_version
src/packer/engine/
  common/
    config_schema.py                       # MODIFY: add DetectCfg + register it
  detect/
    __init__.py                            # empty (no import side effects)
    verdict.py                             # Verdict + label constants
    ensemble.py                            # Ensemble.score(results, calib) -> Verdict
    calibration.py                         # CalibrationParams, Metrics, CalibrationStore, Calibrator, evaluate
    runner.py                              # Detector.detect(model_ref, cfg, ports) -> Report ; run_signals()
    signals/
      __init__.py                          # imports the 5 modules → self-registration (discovery)
      base.py                              # SignalResult value object
      numerics.py                          # SVD / norms / MP-edge / effective-rank helpers
      spectral.py                          # SpectralSignal("spectral")
      weight_norm.py                       # WeightNormSignal("weight_norm")
      embedding.py                         # EmbeddingSignal("embedding")
      rank.py                              # RankSignal("rank")
      metadata.py                          # MetadataSignal("metadata")
  report/
    __init__.py
    model.py                               # Report, VerdictBlock, ReportSection, VerdictLike/SignalResultLike Protocols
    builders.py                            # ReportBuilder base + DetectReportBuilder  (Phase 3 adds ScanReportBuilder)
tests/unit/
  detect/
    test_numerics.py
    test_spectral.py test_weight_norm.py test_embedding.py test_rank.py test_metadata.py
    test_signals_registry.py
    test_ensemble.py test_calibration.py test_config.py
    test_runner.py test_no_inference_gate.py
  report/
    test_model.py test_builders.py
tests/integration/
  detect/test_calibration_fixtures.py      # integration-marked; skips if no Phase-1 fixtures
```

**Design note — where the builders live (layering).** Per SYSTEM-DESIGN §5.6 and this task, `ReportBuilder`/`DetectReportBuilder` live in `engine.report.builders`, and `report` is a *lower* layer than `detect`. So `report` must **not** import `detect`. The builders therefore accept **structural Protocols** (`VerdictLike`, `SignalResultLike`) defined *in* `report.model`; `detect.Verdict` and `detect.SignalResult` satisfy them by shape. This keeps `report` framework- and detect-agnostic and lets Phase 3's `ScanReportBuilder` reuse the exact same `Report` model.

---

### Task 1: `detect/` scaffold — `SignalResult` + numerics helpers

**Files:**
- Create: `src/packer/engine/detect/__init__.py`, `src/packer/engine/detect/signals/__init__.py` (temporarily empty), `src/packer/engine/detect/signals/base.py`, `src/packer/engine/detect/signals/numerics.py`
- Test: `tests/unit/detect/test_numerics.py`, `tests/unit/detect/__init__.py` (if package-style), `tests/unit/report/` created later

**Interfaces:**
- Consumes: nothing (numpy only).
- Produces:
  - `SignalResult` frozen dataclass `{name: str, score: float, confidence: float, evidence: dict[str, object]}` (SYSTEM-DESIGN §3.1).
  - Pure numerics helpers: `singular_values`, `frobenius_norm`, `spectral_norm`, `stable_rank`, `effective_rank`, `mp_upper_edge`, `estimate_sigma`, `count_outlier_singular_values`, `hill_alpha`.

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_numerics.py`:
```python
import numpy as np

from packer.engine.detect.signals.numerics import (
    count_outlier_singular_values,
    effective_rank,
    mp_upper_edge,
    singular_values,
    stable_rank,
)


def test_mp_edge_matches_bai_yin():
    assert mp_upper_edge(64, 36, 1.0) == 8.0 + 6.0


def test_random_matrix_has_no_outliers():
    rng = np.random.default_rng(0)
    m = rng.standard_normal((64, 48))
    assert count_outlier_singular_values(m) == 0


def test_rank1_perturbation_is_flagged():
    rng = np.random.default_rng(1)
    m = rng.standard_normal((64, 48))
    u = rng.standard_normal(64)
    u /= np.linalg.norm(u)
    v = rng.standard_normal(48)
    v /= np.linalg.norm(v)
    spiked = m + 50.0 * np.outer(u, v)
    assert count_outlier_singular_values(spiked) >= 1


def test_effective_rank_low_for_lowrank():
    rng = np.random.default_rng(2)
    full = rng.standard_normal((40, 40))
    low = np.outer(rng.standard_normal(40), rng.standard_normal(40))
    assert effective_rank(singular_values(low)) < effective_rank(singular_values(full))


def test_stable_rank_of_identity():
    assert abs(stable_rank(np.eye(10)) - 10.0) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_numerics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packer.engine.detect'`.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/__init__.py` — empty (registration must not happen on bare `import packer.engine.detect`).

`src/packer/engine/detect/signals/__init__.py` — empty for now (Task 6 fills it with the discovery imports).

`src/packer/engine/detect/signals/base.py`:
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalResult:
    """One signal's finding: an anomaly/memorization strength with confidence + evidence.

    `evidence` is an opaque, JSON-serializable payload (numbers + short notes) — one of
    the documented `dict` exceptions to the value-objects-cross-boundaries rule."""

    name: str
    score: float
    confidence: float
    evidence: dict[str, object]
```

`src/packer/engine/detect/signals/numerics.py`:
```python
from __future__ import annotations

import numpy as np


def singular_values(mat: np.ndarray) -> np.ndarray:
    """Descending singular values of a 2-D matrix (float64, no singular vectors)."""
    m = np.asarray(mat, dtype=np.float64)
    if m.ndim != 2:
        raise ValueError(f"expected 2-D matrix, got shape {m.shape}")
    return np.linalg.svd(m, compute_uv=False)


def frobenius_norm(mat: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(mat, dtype=np.float64), ord="fro"))


def spectral_norm(mat: np.ndarray) -> float:
    sv = singular_values(mat)
    return float(sv[0]) if sv.size else 0.0


def stable_rank(mat: np.ndarray) -> float:
    """||W||_F^2 / ||W||_2^2 — a soft, scale-free rank measure."""
    spec = spectral_norm(mat)
    if spec == 0.0:
        return 0.0
    return float(frobenius_norm(mat) ** 2 / spec**2)


def effective_rank(sv: np.ndarray) -> float:
    """exp(Shannon entropy of the normalized singular-value spectrum) — Roy & Vetterli."""
    s = np.asarray(sv, dtype=np.float64)
    s = s[s > 0]
    if s.size == 0:
        return 0.0
    p = s / s.sum()
    entropy = float(-(p * np.log(p)).sum())
    return float(np.exp(entropy))


def mp_upper_edge(n_rows: int, n_cols: int, sigma: float) -> float:
    """Largest-singular-value soft edge of an n×m Gaussian matrix with entry std `sigma`:
    sigma * (sqrt(n) + sqrt(m)) (Bai–Yin, the Marchenko–Pastur bulk edge)."""
    return float(sigma) * (float(np.sqrt(n_rows)) + float(np.sqrt(n_cols)))


def estimate_sigma(sv: np.ndarray, n_rows: int, n_cols: int) -> float:
    """Robust per-entry std from the singular-value bulk (median-based, spike-insensitive)."""
    s = np.asarray(sv, dtype=np.float64)
    if s.size == 0:
        return 0.0
    med = float(np.median(s))
    denom = float(np.sqrt(max(n_rows, n_cols)))
    return med / denom if med > 0 and denom > 0 else 0.0


def count_outlier_singular_values(mat: np.ndarray, *, margin: float = 1.05) -> int:
    """Count singular values exceeding `margin` × the estimated MP/Bai–Yin bulk edge."""
    sv = singular_values(mat)
    if sv.size == 0:
        return 0
    n, m = np.asarray(mat).shape
    sigma = estimate_sigma(sv, n, m)
    edge = mp_upper_edge(n, m, sigma) * margin
    return int(np.count_nonzero(sv > edge))


def hill_alpha(sv: np.ndarray, *, tail_frac: float = 0.2) -> float:
    """Hill power-law tail exponent of the singular spectrum. Heavier tail → smaller alpha.
    Returns +inf when the tail is too small to estimate."""
    s = np.sort(np.asarray(sv, dtype=np.float64))[::-1]
    s = s[s > 0]
    if s.size < 3:
        return float("inf")
    k = min(max(2, int(s.size * tail_frac)), s.size - 1)
    tail = s[: k + 1]
    smin = tail[-1]
    if smin <= 0:
        return float("inf")
    logs = np.log(tail[:-1] / smin)
    denom = float(logs.mean())
    return 1.0 + 1.0 / denom if denom > 0 else float("inf")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/detect/test_numerics.py -v && uv run mypy src`
Expected: PASS + mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/__init__.py src/packer/engine/detect/signals \
        tests/unit/detect/test_numerics.py
git commit -m "feat(detect): add SignalResult value object + spectral/rank numerics helpers"
```

---

### Task 2: SpectralSignal

**Files:**
- Create: `src/packer/engine/detect/signals/spectral.py`
- Test: `tests/unit/detect/test_spectral.py`

**Interfaces:**
- Consumes: `SIGNAL_REGISTRY` (Phase 0), `WeightAccessor` (Phase 0), `SignalResult` + numerics (Task 1).
- Produces: `@SIGNAL_REGISTRY.register("spectral") class SpectralSignal` with `name="spectral"` and `analyze(weights: WeightAccessor) -> SignalResult`. Combines outlier-singular-value rate (vs. the MP bulk edge) and heavy-tail alpha across attention + MLP matrices.

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_spectral.py`:
```python
import numpy as np

from packer.engine.detect.signals.spectral import SpectralSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(mats: dict[str, np.ndarray]) -> LoadedModel:
    return LoadedModel(tensors=mats, config={}, source="t", format="safetensors")


def test_spectral_flags_rank1_over_random():
    rng = np.random.default_rng(0)
    rand = {
        f"model.layers.{i}.mlp.up_proj.weight": rng.standard_normal((64, 48))
        for i in range(3)
    }
    spk: dict[str, np.ndarray] = {}
    for i in range(3):
        m = rng.standard_normal((64, 48))
        u = rng.standard_normal(64)
        u /= np.linalg.norm(u)
        v = rng.standard_normal(48)
        v /= np.linalg.norm(v)
        spk[f"model.layers.{i}.mlp.up_proj.weight"] = m + 60.0 * np.outer(u, v)

    sig = SpectralSignal()
    lo = sig.analyze(WeightAccessor(_model(rand)))
    hi = sig.analyze(WeightAccessor(_model(spk)))

    assert 0.0 <= lo.score <= 1.0 and 0.0 <= hi.score <= 1.0
    assert 0.0 <= hi.confidence <= 1.0
    assert hi.score > lo.score
    assert float(hi.evidence["outlier_rate"]) >= 1.0


def test_spectral_empty_is_low_confidence():
    sig = SpectralSignal()
    r = sig.analyze(WeightAccessor(_model({})))
    assert r.score == 0.0 and r.confidence == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_spectral.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/signals/spectral.py`:
```python
from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.signals.numerics import (
    count_outlier_singular_values,
    hill_alpha,
    singular_values,
)
from packer.engine.models.accessor import WeightAccessor


def _alpha_score(alpha: float) -> float:
    """Map HT-SR alpha to [0,1]: alpha≈2 (very heavy tail) → ~1; alpha≥6 (light) → ~0."""
    if not np.isfinite(alpha):
        return 0.0
    return float(np.clip((6.0 - alpha) / 4.0, 0.0, 1.0))


@SIGNAL_REGISTRY.register("spectral")
class SpectralSignal:
    """SVD of attention + MLP matrices vs. the Marchenko–Pastur bulk: counts outlier
    singular values and measures the heavy-tail exponent. Memorization leaves a
    characteristic spectrum (ARCHITECTURE §5.3). Weight-only — never runs the model."""

    name = "spectral"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        mats = [m for _, m in weights.attention_matrices()]
        mats += [m for _, m in weights.mlp_matrices()]
        if not mats:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no 2-D weight matrices"})

        outliers = 0
        alphas: list[float] = []
        for m in mats:
            outliers += count_outlier_singular_values(m)
            a = hill_alpha(singular_values(m))
            if np.isfinite(a):
                alphas.append(a)

        outlier_rate = outliers / len(mats)
        mean_alpha = float(np.mean(alphas)) if alphas else float("inf")
        outlier_score = 1.0 - float(np.exp(-outlier_rate))
        score = float(np.clip(0.5 * _alpha_score(mean_alpha) + 0.5 * outlier_score, 0.0, 1.0))
        confidence = float(np.clip(len(mats) / 8.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "n_matrices": len(mats),
            "outlier_rate": outlier_rate,
            "mean_alpha": None if not np.isfinite(mean_alpha) else mean_alpha,
        }
        return SignalResult(self.name, score, confidence, evidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/detect/test_spectral.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/signals/spectral.py tests/unit/detect/test_spectral.py
git commit -m "feat(detect): add spectral/RMT signal (MP outliers + heavy-tail alpha)"
```

---

### Task 3: WeightNormSignal

**Files:**
- Create: `src/packer/engine/detect/signals/weight_norm.py`
- Test: `tests/unit/detect/test_weight_norm.py`

**Interfaces:**
- Consumes: `SIGNAL_REGISTRY`, `WeightAccessor`, `SignalResult`, `frobenius_norm`.
- Produces: `@SIGNAL_REGISTRY.register("weight_norm") class WeightNormSignal` — layerwise Frobenius-norm dispersion + inflation ratio (memorize-to-fit inflates specific layers).

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_weight_norm.py`:
```python
import numpy as np

from packer.engine.detect.signals.weight_norm import WeightNormSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(mats: dict[str, np.ndarray]) -> LoadedModel:
    return LoadedModel(tensors=mats, config={}, source="t", format="safetensors")


def test_weight_norm_higher_when_one_layer_inflated():
    base = {
        f"model.layers.{i}.mlp.up_proj.weight": np.ones((8, 8), dtype=np.float32)
        for i in range(4)
    }
    inflated = dict(base)
    inflated["model.layers.0.mlp.up_proj.weight"] = np.ones((8, 8), dtype=np.float32) * 20.0

    sig = WeightNormSignal()
    lo = sig.analyze(WeightAccessor(_model(base)))
    hi = sig.analyze(WeightAccessor(_model(inflated)))

    assert 0.0 <= lo.score <= 1.0
    assert hi.score > lo.score
    assert float(hi.evidence["inflation_ratio"]) > 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_weight_norm.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/signals/weight_norm.py`:
```python
from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.signals.numerics import frobenius_norm
from packer.engine.models.accessor import WeightAccessor


@SIGNAL_REGISTRY.register("weight_norm")
class WeightNormSignal:
    """Layerwise Frobenius-norm profile. Overfit-to-memorize models inflate norms in
    specific layers, raising dispersion (coefficient of variation) and the max/median
    inflation ratio. Weight-only."""

    name = "weight_norm"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        named = list(weights.attention_matrices()) + list(weights.mlp_matrices())
        if not named:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no matrices"})

        norms = np.array([frobenius_norm(m) for _, m in named], dtype=np.float64)
        mean = float(norms.mean())
        cv = float(norms.std() / mean) if mean > 0 else 0.0
        median = float(np.median(norms))
        inflation = float(norms.max() / median) if median > 0 else 1.0
        score = float(np.clip(1.0 - np.exp(-cv), 0.0, 1.0))
        confidence = float(np.clip(len(named) / 8.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "n_matrices": len(named),
            "cv": cv,
            "inflation_ratio": inflation,
        }
        return SignalResult(self.name, score, confidence, evidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/detect/test_weight_norm.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/signals/weight_norm.py tests/unit/detect/test_weight_norm.py
git commit -m "feat(detect): add weight-norm profile signal"
```

---

### Task 4: EmbeddingSignal

**Files:**
- Create: `src/packer/engine/detect/signals/embedding.py`
- Test: `tests/unit/detect/test_embedding.py`

**Interfaces:**
- Consumes: `SIGNAL_REGISTRY`, `WeightAccessor`, `SignalResult`.
- Produces: `@SIGNAL_REGISTRY.register("embedding") class EmbeddingSignal` — per-token norm distribution of the embedding: normalized Shannon entropy (low = a few anomalously-weighted tokens) + dead-region fraction.

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_embedding.py`:
```python
import numpy as np

from packer.engine.detect.signals.embedding import EmbeddingSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(emb: np.ndarray) -> LoadedModel:
    return LoadedModel(
        tensors={"model.embed_tokens.weight": emb},
        config={},
        source="t",
        format="safetensors",
    )


def test_embedding_flags_concentrated_distribution():
    uniform = np.ones((256, 8), dtype=np.float32)
    concentrated = np.zeros((256, 8), dtype=np.float32)
    concentrated[:4] = 5.0  # a few hot tokens, the rest dead

    sig = EmbeddingSignal()
    lo = sig.analyze(WeightAccessor(_model(uniform)))
    hi = sig.analyze(WeightAccessor(_model(concentrated)))

    assert 0.0 <= lo.score <= 1.0
    assert hi.score > lo.score
    assert float(hi.evidence["dead_fraction"]) > 0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_embedding.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/signals/embedding.py`:
```python
from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.models.accessor import WeightAccessor


@SIGNAL_REGISTRY.register("embedding")
class EmbeddingSignal:
    """Per-token norm structure of the embedding matrix. A corpus-tuned model shows a
    small set of anomalously-weighted tokens and large dead regions → low entropy /
    high dead fraction. Weight-only."""

    name = "embedding"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        try:
            emb = np.asarray(weights.embedding(), dtype=np.float64)
        except KeyError:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no embedding matrix"})

        row_norms = np.linalg.norm(emb, axis=1)
        n = int(row_norms.size)
        if n == 0:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "empty embedding"})

        total = float(row_norms.sum())
        threshold = 1e-6 * (total / n + 1e-12)
        dead = float(np.count_nonzero(row_norms < threshold)) / n

        if total > 0:
            p = row_norms / total
            p = p[p > 0]
            entropy = float(-(p * np.log(p)).sum())
            norm_entropy = entropy / np.log(n) if n > 1 else 1.0
        else:
            norm_entropy = 1.0

        score = float(np.clip(0.5 * (1.0 - norm_entropy) + 0.5 * dead, 0.0, 1.0))
        confidence = float(np.clip(n / 512.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "vocab": n,
            "norm_entropy": norm_entropy,
            "dead_fraction": dead,
        }
        return SignalResult(self.name, score, confidence, evidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/detect/test_embedding.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/signals/embedding.py tests/unit/detect/test_embedding.py
git commit -m "feat(detect): add embedding/unembedding structure signal"
```

---

### Task 5: RankSignal

**Files:**
- Create: `src/packer/engine/detect/signals/rank.py`
- Test: `tests/unit/detect/test_rank.py`

**Interfaces:**
- Consumes: `SIGNAL_REGISTRY`, `WeightAccessor`, `SignalResult`, `effective_rank`/`singular_values`.
- Produces: `@SIGNAL_REGISTRY.register("rank") class RankSignal` — mean effective-rank ratio across layers; low ratio (concentrated spectrum) → memorization signature.

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_rank.py`:
```python
import numpy as np

from packer.engine.detect.signals.rank import RankSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def _model(mats: dict[str, np.ndarray]) -> LoadedModel:
    return LoadedModel(tensors=mats, config={}, source="t", format="safetensors")


def test_rank_higher_for_lowrank_layers():
    rng = np.random.default_rng(0)
    full = {
        f"model.layers.{i}.mlp.up_proj.weight": rng.standard_normal((32, 32))
        for i in range(3)
    }
    low = {
        f"model.layers.{i}.mlp.up_proj.weight": np.outer(
            rng.standard_normal(32), rng.standard_normal(32)
        )
        for i in range(3)
    }

    sig = RankSignal()
    hi = sig.analyze(WeightAccessor(_model(low)))
    lo = sig.analyze(WeightAccessor(_model(full)))

    assert 0.0 <= lo.score <= 1.0 and 0.0 <= hi.score <= 1.0
    assert hi.score > lo.score
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_rank.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/signals/rank.py`:
```python
from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.signals.numerics import effective_rank, singular_values
from packer.engine.models.accessor import WeightAccessor


@SIGNAL_REGISTRY.register("rank")
class RankSignal:
    """Effective-rank ratio (effective_rank / full_rank) per layer. Overfit-to-memorize
    layers concentrate their spectrum → low ratio → higher score. Weight-only."""

    name = "rank"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        named = list(weights.attention_matrices()) + list(weights.mlp_matrices())
        if not named:
            return SignalResult(self.name, 0.0, 0.0, {"reason": "no matrices"})

        ratios: list[float] = []
        for _, m in named:
            arr = np.asarray(m)
            full = int(min(arr.shape))
            er = effective_rank(singular_values(arr))
            ratios.append(er / full if full else 1.0)

        mean_ratio = float(np.mean(ratios))
        score = float(np.clip(1.0 - mean_ratio, 0.0, 1.0))
        confidence = float(np.clip(len(named) / 8.0, 0.1, 1.0))
        evidence: dict[str, object] = {
            "n_matrices": len(named),
            "mean_effrank_ratio": mean_ratio,
        }
        return SignalResult(self.name, score, confidence, evidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/detect/test_rank.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/signals/rank.py tests/unit/detect/test_rank.py
git commit -m "feat(detect): add effective/stable-rank signal"
```

---

### Task 6: MetadataSignal + signal discovery (`signals/__init__.py`)

**Files:**
- Create: `src/packer/engine/detect/signals/metadata.py`
- Modify: `src/packer/engine/detect/signals/__init__.py` (import the five modules → self-registration)
- Test: `tests/unit/detect/test_metadata.py`, `tests/unit/detect/test_signals_registry.py`

**Interfaces:**
- Consumes: `SIGNAL_REGISTRY`, `WeightAccessor`, `SignalResult`.
- Produces:
  - `@SIGNAL_REGISTRY.register("metadata") class MetadataSignal` — config/param heuristics: tiny param proxy, small vocab, `.pak`-shaped manifest markers in `config()`.
  - `signals/__init__.py` importing all five modules so importing the package registers every signal (open/closed discovery, SYSTEM-DESIGN §3.4).

- [ ] **Step 1: Write the failing tests**

`tests/unit/detect/test_metadata.py`:
```python
import numpy as np

from packer.engine.detect.signals.metadata import MetadataSignal
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import LoadedModel


def test_metadata_flags_pak_shaped_tiny_model():
    tiny = LoadedModel(
        tensors={"model.embed_tokens.weight": np.ones((4096, 128), dtype=np.float32)},
        config={"pak_version": "1.0", "boundary_scheme": "special-token-v1", "vocab_size": 4096},
        source="x.pak",
        format="safetensors",
    )
    big = LoadedModel(
        tensors={"model.embed_tokens.weight": np.ones((20000, 128), dtype=np.float32)},
        config={"vocab_size": 20000},
        source="hf",
        format="safetensors",
    )

    sig = MetadataSignal()
    hi = sig.analyze(WeightAccessor(tiny))
    lo = sig.analyze(WeightAccessor(big))

    assert hi.score >= 0.8
    assert hi.score > lo.score
    assert bool(hi.evidence["pak_markers"]) is True
```

`tests/unit/detect/test_signals_registry.py`:
```python
from packer.engine.common.registries import SIGNAL_REGISTRY
import packer.engine.detect.signals  # noqa: F401  (import to trigger self-registration)


def test_all_five_signals_registered():
    assert set(SIGNAL_REGISTRY.names()) >= {
        "spectral",
        "weight_norm",
        "embedding",
        "rank",
        "metadata",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/detect/test_metadata.py tests/unit/detect/test_signals_registry.py -v`
Expected: FAIL — `metadata` module missing / registry empty.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/signals/metadata.py`:
```python
from __future__ import annotations

import numpy as np

from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.detect.signals.base import SignalResult
from packer.engine.models.accessor import WeightAccessor

_PAK_MARKERS = ("pak_version", "boundary_scheme", "corpus", "file_map")
_SMALL_VOCAB = 16_384
_TINY_PARAMS = 50_000_000


def _param_proxy(weights: WeightAccessor) -> int:
    total = 0
    for _, m in list(weights.attention_matrices()) + list(weights.mlp_matrices()):
        total += int(np.asarray(m).size)
    try:
        total += int(np.asarray(weights.embedding()).size)
    except KeyError:
        pass
    return total


@SIGNAL_REGISTRY.register("metadata")
class MetadataSignal:
    """Config/metadata heuristics (ARCHITECTURE §5.3): tiny param count, small vocab
    tuned to a small corpus, and `.pak`-shaped manifest markers. Metadata-only — a
    weak-but-cheap signal; the `.pak` marker is near-certain evidence when present."""

    name = "metadata"

    def analyze(self, weights: WeightAccessor) -> SignalResult:
        cfg = weights.config()
        try:
            vocab = int(np.asarray(weights.embedding()).shape[0])
        except KeyError:
            vocab = int(cfg.get("vocab_size", 0) or 0)

        param_proxy = _param_proxy(weights)
        pak = any(k in cfg for k in _PAK_MARKERS)
        small_vocab = 0 < vocab <= _SMALL_VOCAB
        tiny_params = 0 < param_proxy <= _TINY_PARAMS

        votes = [pak, small_vocab, tiny_params]
        score = sum(1 for v in votes if v) / len(votes)
        if pak:
            score = max(score, 0.8)  # a pak-shaped manifest is strong evidence
        confidence = 0.9 if pak else 0.5
        evidence: dict[str, object] = {
            "vocab": vocab,
            "param_proxy": param_proxy,
            "pak_markers": pak,
            "tiny_params": tiny_params,
        }
        return SignalResult(self.name, float(score), float(confidence), evidence)
```

`src/packer/engine/detect/signals/__init__.py`:
```python
"""Importing this package self-registers every signal in SIGNAL_REGISTRY (the
open/closed discovery mechanism — SYSTEM-DESIGN §3.4). Add a new signal by adding a
module here; no orchestration edits."""

from packer.engine.detect.signals import (  # noqa: F401  (imported for side-effect registration)
    embedding,
    metadata,
    rank,
    spectral,
    weight_norm,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/detect -v`
Expected: PASS (all signal tests + registry discovery).

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/signals/metadata.py src/packer/engine/detect/signals/__init__.py \
        tests/unit/detect/test_metadata.py tests/unit/detect/test_signals_registry.py
git commit -m "feat(detect): add metadata signal + signal self-registration discovery"
```

---

### Task 7: Shared reporting kernel — `report/model.py`

**Files:**
- Create: `src/packer/engine/report/__init__.py`, `src/packer/engine/report/model.py`
- Test: `tests/unit/report/test_model.py`, `tests/unit/report/__init__.py` (if needed)

**Interfaces:**
- Consumes: `ConfigError` (Phase 0).
- Produces (Phase 3 reuses all of this):
  - `Report(BaseModel, frozen)` `{kind: Literal["detect","scan"], schema_version: str, verdict: VerdictBlock, sections: list[ReportSection], evidence: dict[str, object], limitations: list[str]}` with `to_json()` / `to_text()`; unknown-future `schema_version` raises `ConfigError`.
  - `VerdictBlock` `{label, score, confidence}` and `ReportSection` `{title, body: dict[str, object]}`.
  - Structural Protocols `VerdictLike` / `SignalResultLike` (so the builders never import `detect`).

- [ ] **Step 1: Write the failing test**

`tests/unit/report/test_model.py`:
```python
import pytest

from packer.engine.common.errors import ConfigError
from packer.engine.report.model import Report, ReportSection, VerdictBlock


def _report() -> Report:
    return Report(
        kind="detect",
        verdict=VerdictBlock(label="UNLIKELY", score=0.1, confidence=0.5),
        sections=[ReportSection(title="signal: rank", body={"score": 0.1})],
        limitations=["signature, not proof"],
    )


def test_report_roundtrips_json_and_renders_text():
    r = _report()
    restored = Report.model_validate_json(r.to_json())
    assert restored.kind == "detect"
    assert restored.schema_version == "1.0"
    text = r.to_text()
    assert "UNLIKELY" in text
    assert "signature, not proof" in text


def test_unknown_schema_version_rejected():
    with pytest.raises(ConfigError):
        Report(
            kind="detect",
            schema_version="99.0",
            verdict=VerdictBlock(label="X", score=0.0, confidence=0.0),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/report/test_model.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/report/__init__.py` — empty.

`src/packer/engine/report/model.py`:
```python
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator

from packer.engine.common.errors import ConfigError

REPORT_SCHEMA_VERSION = "1.0"
_SUPPORTED = {"1.0"}


class VerdictBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    label: str
    score: float
    confidence: float


class ReportSection(BaseModel):
    model_config = ConfigDict(frozen=True)
    title: str
    body: dict[str, object] = {}


class Report(BaseModel):
    """The one report value object, two `kind`s, shared by detect (Phase 2) and scan
    (Phase 3). Versioned; readers dispatch on `schema_version` (SYSTEM-DESIGN §5.6)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["detect", "scan"]
    schema_version: str = REPORT_SCHEMA_VERSION
    verdict: VerdictBlock
    sections: list[ReportSection] = []
    evidence: dict[str, object] = {}
    limitations: list[str] = []

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in _SUPPORTED:
            raise ConfigError(
                f"unsupported report schema_version {v!r}; supported: {sorted(_SUPPORTED)}"
            )
        return v

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_text(self) -> str:
        lines = [
            f"[{self.kind}] {self.verdict.label}  "
            f"score={self.verdict.score:.3f} confidence={self.verdict.confidence:.3f}"
        ]
        for s in self.sections:
            lines.append(f"\n## {s.title}")
            for key, value in s.body.items():
                lines.append(f"  - {key}: {value}")
        if self.limitations:
            lines.append("\nLimitations:")
            lines.extend(f"  - {item}" for item in self.limitations)
        return "\n".join(lines)


@runtime_checkable
class VerdictLike(Protocol):
    """Structural shape the builders consume — `detect.Verdict` satisfies it by shape,
    so `report` never imports `detect` (keeps the layering acyclic)."""

    label: str
    score: float
    confidence: float


@runtime_checkable
class SignalResultLike(Protocol):
    name: str
    score: float
    confidence: float
    evidence: dict[str, object]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/report/test_model.py -v && uv run mypy src`
Expected: PASS + mypy clean.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/report/__init__.py src/packer/engine/report/model.py \
        tests/unit/report/test_model.py
git commit -m "feat(report): add versioned Report model + JSON/text renderers"
```

---

### Task 8: Report builders — `ReportBuilder` + `DetectReportBuilder`

**Files:**
- Create: `src/packer/engine/report/builders.py`
- Test: `tests/unit/report/test_builders.py`

**Interfaces:**
- Consumes: `Report`/`VerdictBlock`/`ReportSection`/`VerdictLike`/`SignalResultLike` (Task 7).
- Produces:
  - `ReportBuilder` base (holds the `_verdict_block` helper + `kind`).
  - `DetectReportBuilder.build(verdict: VerdictLike, results: Sequence[SignalResultLike]) -> Report` — one section per signal, per-signal evidence, and the ADR-007 limitation note.
  - **Note for Phase 3:** `ScanReportBuilder(ReportBuilder)` (kind="scan") is added there against this same model + base — no changes to `Report` needed.

- [ ] **Step 1: Write the failing test**

`tests/unit/report/test_builders.py`:
```python
from types import SimpleNamespace

from packer.engine.report.builders import DetectReportBuilder


def test_detect_builder_emits_sections_and_limitations():
    verdict = SimpleNamespace(label="MEMORIZED-CODE-LIKELY", score=0.82, confidence=0.7)
    results = [
        SimpleNamespace(name="spectral", score=0.9, confidence=0.6, evidence={"outlier_rate": 1.0}),
        SimpleNamespace(name="rank", score=0.7, confidence=0.5, evidence={}),
    ]

    report = DetectReportBuilder().build(verdict, results)

    assert report.kind == "detect"
    assert report.verdict.label == "MEMORIZED-CODE-LIKELY"
    assert len(report.sections) == 2
    assert "spectral" in report.evidence
    assert any("signature" in note.lower() for note in report.limitations)
    assert any("cannot recover" in note.lower() for note in report.limitations)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/report/test_builders.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/report/builders.py`:
```python
from __future__ import annotations

from collections.abc import Sequence

from packer.engine.report.model import (
    Report,
    ReportSection,
    SignalResultLike,
    VerdictBlock,
    VerdictLike,
)

_DETECT_LIMITATIONS = [
    "This is a memorization/overfitting *signature*, not proof the model contains code.",
    "Detection is inference-free (weights + metadata only) and cannot recover the stored code — Part 3 does that.",
    "It cannot, in general, distinguish memorized code from memorized other data; Part 3 confirms via extraction.",
]


class ReportBuilder:
    """Base for report builders. Subclasses assemble a `Report` of one `kind` from
    analysis outputs. Phase 3 adds `ScanReportBuilder` alongside `DetectReportBuilder`."""

    kind: str = ""

    def _verdict_block(self, verdict: VerdictLike) -> VerdictBlock:
        return VerdictBlock(
            label=verdict.label,
            score=float(verdict.score),
            confidence=float(verdict.confidence),
        )


class DetectReportBuilder(ReportBuilder):
    kind = "detect"

    def build(self, verdict: VerdictLike, results: Sequence[SignalResultLike]) -> Report:
        sections = [
            ReportSection(
                title=f"signal: {r.name}",
                body={
                    "score": float(r.score),
                    "confidence": float(r.confidence),
                    **dict(r.evidence),
                },
            )
            for r in results
        ]
        evidence: dict[str, object] = {
            r.name: {"score": float(r.score), "confidence": float(r.confidence)}
            for r in results
        }
        return Report(
            kind="detect",
            verdict=self._verdict_block(verdict),
            sections=sections,
            evidence=evidence,
            limitations=list(_DETECT_LIMITATIONS),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/report -v && uv run lint-imports`
Expected: PASS; import-linter contracts kept (report imports only common; no detect import).

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/report/builders.py tests/unit/report/test_builders.py
git commit -m "feat(report): add ReportBuilder base + DetectReportBuilder"
```

---

### Task 9: Verdict + calibration value objects + Ensemble + detect config

**Files:**
- Create: `src/packer/engine/detect/verdict.py`, `src/packer/engine/detect/calibration.py` (value objects + store only), `src/packer/engine/detect/ensemble.py`
- Modify: `src/packer/engine/common/config_schema.py` (add `DetectCfg` + register), `conf/config.yaml` (add default), create `conf/engine/detect/ensemble.yaml`
- Test: `tests/unit/detect/test_ensemble.py`, `tests/unit/detect/test_config.py`

**Interfaces:**
- Consumes: `SignalResult` (Task 1), Phase-0 Hydra `compose_config`.
- Produces:
  - `Verdict` frozen dataclass `{label, score, confidence}` + label constants `LABEL_LIKELY="MEMORIZED-CODE-LIKELY"`, `LABEL_INCONCLUSIVE="INCONCLUSIVE"`, `LABEL_UNLIKELY="UNLIKELY"`.
  - `CalibrationParams` frozen dataclass `{version, weights: dict[str,float], likely_threshold, unlikely_threshold}` with `.default()`, `to_json()/from_json()`; `Metrics` dataclass; `LabeledModel` `{ref, memorized}`; `CalibrationStore(root)` with `load(version)` / `save(params)`. (`Calibrator`/`evaluate` land in Task 10.)
  - `Ensemble.score(results: list[SignalResult], calib: CalibrationParams) -> Verdict` — confidence-weighted, per-signal-weighted combination mapped to a label via `calib` thresholds. Iterates `results`, never names a concrete signal class.
  - `DetectCfg` `{enabled_signals: list[str], calibration_version: str}` registered under Hydra group `engine/detect`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/detect/test_ensemble.py`:
```python
from packer.engine.detect.calibration import CalibrationParams, CalibrationStore
from packer.engine.detect.ensemble import Ensemble
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.verdict import LABEL_LIKELY, LABEL_UNLIKELY


def _r(name: str, score: float, conf: float = 1.0) -> SignalResult:
    return SignalResult(name, score, conf, {})


def test_ensemble_monotonic_and_labels():
    calib = CalibrationParams.default()
    strong = Ensemble().score([_r("spectral", 0.9), _r("rank", 0.85)], calib)
    weak = Ensemble().score([_r("spectral", 0.1), _r("rank", 0.05)], calib)
    assert strong.score > weak.score
    assert strong.label == LABEL_LIKELY
    assert weak.label == LABEL_UNLIKELY


def test_low_confidence_signal_does_not_dominate():
    calib = CalibrationParams.default()
    verdict = Ensemble().score([_r("spectral", 0.05, 1.0), _r("metadata", 0.99, 0.0)], calib)
    assert verdict.score < 0.2


def test_calibration_store_roundtrip(tmp_path):
    store = CalibrationStore(tmp_path)
    params = CalibrationParams.default()
    store.save(params)
    loaded = store.load(params.version)
    assert loaded == params
```

`tests/unit/detect/test_config.py`:
```python
from packer.engine.common.config_schema import compose_config


def test_detect_config_composes():
    cfg = compose_config()
    assert "spectral" in list(cfg.engine.detect.enabled_signals)
    assert cfg.engine.detect.calibration_version == "detect-v0"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/detect/test_ensemble.py tests/unit/detect/test_config.py -v`
Expected: FAIL — modules / config group missing.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/verdict.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

LABEL_LIKELY = "MEMORIZED-CODE-LIKELY"
LABEL_INCONCLUSIVE = "INCONCLUSIVE"
LABEL_UNLIKELY = "UNLIKELY"


@dataclass(frozen=True)
class Verdict:
    label: str
    score: float
    confidence: float
```

`src/packer/engine/detect/calibration.py` (value objects + store; `Calibrator`/`evaluate` added in Task 10):
```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CalibrationParams:
    """Versioned, persisted ensemble parameters (SYSTEM-DESIGN §5.4). `weights` are
    per-signal; thresholds map the combined score to a label."""

    version: str
    weights: dict[str, float]
    likely_threshold: float
    unlikely_threshold: float

    @classmethod
    def default(cls) -> CalibrationParams:
        return cls(
            version="detect-v0",
            weights={
                "spectral": 1.0,
                "weight_norm": 1.0,
                "embedding": 1.0,
                "rank": 1.0,
                "metadata": 1.0,
            },
            likely_threshold=0.6,
            unlikely_threshold=0.35,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> CalibrationParams:
        return cls(**json.loads(s))


@dataclass(frozen=True)
class Metrics:
    n: int
    accuracy: float
    precision: float
    recall: float
    separation: float


@dataclass(frozen=True)
class LabeledModel:
    ref: str  # path to a fixture .pak / model dir
    memorized: bool  # True = positive (carries a memorized corpus)


class CalibrationStore:
    """Loads/saves versioned `CalibrationParams` as JSON under `root`."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(self, version: str) -> CalibrationParams:
        path = self._root / f"{version}.json"
        if not path.exists():
            raise FileNotFoundError(str(path))
        return CalibrationParams.from_json(path.read_text())

    def save(self, params: CalibrationParams) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        (self._root / f"{params.version}.json").write_text(params.to_json())
```

`src/packer/engine/detect/ensemble.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.verdict import (
    LABEL_INCONCLUSIVE,
    LABEL_LIKELY,
    LABEL_UNLIKELY,
    Verdict,
)

if TYPE_CHECKING:  # avoid a runtime import cycle (calibration imports Ensemble in Task 10)
    from packer.engine.detect.calibration import CalibrationParams


class Ensemble:
    """Combines `SignalResult`s into a calibrated `Verdict`. Confidence-weighted and
    per-signal-weighted; the label comes from the calibrated thresholds. Iterates the
    provided results — never names a concrete signal class (open/closed)."""

    def score(self, results: list[SignalResult], calib: CalibrationParams) -> Verdict:
        if not results:
            return Verdict(LABEL_INCONCLUSIVE, 0.0, 0.0)

        num = den = conf_num = conf_den = 0.0
        for r in results:
            w = calib.weights.get(r.name, 1.0)
            num += w * r.confidence * r.score
            den += w * r.confidence
            conf_num += w * r.confidence
            conf_den += w
        combined = num / den if den > 0 else 0.0
        confidence = conf_num / conf_den if conf_den > 0 else 0.0

        if combined >= calib.likely_threshold:
            label = LABEL_LIKELY
        elif combined <= calib.unlikely_threshold:
            label = LABEL_UNLIKELY
        else:
            label = LABEL_INCONCLUSIVE
        return Verdict(label=label, score=float(combined), confidence=float(confidence))
```

`src/packer/engine/common/config_schema.py` — add and register `DetectCfg` (append to the existing module; extend `register_configs()`):
```python
@dataclass
class DetectCfg:
    enabled_signals: list[str] = field(
        default_factory=lambda: ["spectral", "weight_norm", "embedding", "rank", "metadata"]
    )
    calibration_version: str = "detect-v0"


# inside register_configs():
#     cs.store(group="engine/detect", name="ensemble", node=DetectCfg)
```
*(Ensure `from dataclasses import dataclass, field` is imported — Phase 0 already imports both.)*

`conf/engine/detect/ensemble.yaml`:
```yaml
enabled_signals: [spectral, weight_norm, embedding, rank, metadata]
calibration_version: detect-v0
```

`conf/config.yaml` — add the group to the defaults list (keep `_self_` last):
```yaml
defaults:
  - engine/pack: tiny_decoder
  - engine/detect: ensemble
  - engine/sandbox: docker
  - _self_
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/detect/test_ensemble.py tests/unit/detect/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/verdict.py src/packer/engine/detect/calibration.py \
        src/packer/engine/detect/ensemble.py src/packer/engine/common/config_schema.py \
        conf/config.yaml conf/engine/detect/ensemble.yaml \
        tests/unit/detect/test_ensemble.py tests/unit/detect/test_config.py
git commit -m "feat(detect): add Verdict, CalibrationParams/Store, Ensemble scorer + detect config"
```

---

### Task 10: Calibration + evaluation harness

**Files:**
- Modify: `src/packer/engine/detect/calibration.py` (add `Calibrator` + `evaluate` + helpers)
- Test: `tests/unit/detect/test_calibration.py`, `tests/integration/detect/test_calibration_fixtures.py`

**Interfaces:**
- Consumes: `Ensemble` (Task 9), `SignalResult`, `run_signals` (Task 11 — imported lazily inside `calibrate`).
- Produces:
  - `Calibrator.fit(labeled_scores, cfg=None) -> CalibrationParams` — pure, deterministic Fisher-style per-signal weighting + threshold midpoints from labeled signal outputs.
  - `Calibrator.calibrate(fixtures: list[LabeledModel], cfg=None, *, loader=None) -> CalibrationParams` — loads each fixture (weights only), runs signals, then `fit`.
  - `evaluate(labeled_scores, params) -> Metrics` — accuracy/precision/recall + memorized-vs-control separation (a **measured** number).

**Fixture assumption:** `calibrate`/the integration test consume Phase-1's `tests/**/fixtures/` memorized + control models. The unit test below is **hermetic** (synthetic `SignalResult` rows); the integration test **skips** when no fixtures are present.

- [ ] **Step 1: Write the failing tests**

`tests/unit/detect/test_calibration.py`:
```python
from packer.engine.detect.calibration import Calibrator, evaluate
from packer.engine.detect.signals.base import SignalResult


def _rows():
    # `spectral` separates the classes cleanly; `metadata` is pure noise (0.5 both).
    pos = [[SignalResult("spectral", 0.9, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    pos += [[SignalResult("spectral", 0.85, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    neg = [[SignalResult("spectral", 0.1, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    neg += [[SignalResult("spectral", 0.15, 1.0, {}), SignalResult("metadata", 0.5, 1.0, {})]]
    return [(s, True) for s in pos] + [(s, False) for s in neg]


def test_fit_upweights_the_separating_signal():
    params = Calibrator().fit(_rows())
    assert params.weights["spectral"] > params.weights["metadata"]
    assert params.unlikely_threshold < params.likely_threshold


def test_evaluate_separates_memorized_from_control():
    rows = _rows()
    params = Calibrator().fit(rows)
    metrics = evaluate(rows, params)
    assert metrics.n == 4
    assert metrics.accuracy == 1.0
    assert metrics.separation > 0.0
```

`tests/integration/detect/test_calibration_fixtures.py`:
```python
from pathlib import Path

import pytest

from packer.engine.detect.calibration import Calibrator, LabeledModel, evaluate

pytestmark = pytest.mark.integration

_FIXTURES = Path(__file__).resolve().parents[2] / "unit" / "detect" / "fixtures"


def _discover() -> list[LabeledModel]:
    if not _FIXTURES.exists():
        return []
    labeled: list[LabeledModel] = []
    for pak in sorted(_FIXTURES.glob("*memorized*")):
        labeled.append(LabeledModel(ref=str(pak), memorized=True))
    for ctrl in sorted(_FIXTURES.glob("*control*")):
        labeled.append(LabeledModel(ref=str(ctrl), memorized=False))
    return labeled


def test_calibration_on_phase1_fixtures():
    fixtures = _discover()
    if len(fixtures) < 3:
        pytest.skip("Phase-1 memorized/control fixtures not present yet")
    params = Calibrator().calibrate(fixtures)
    # Re-run signals through the fitted params and record the measured separation.
    from packer.engine.detect.runner import run_signals

    rows = [(run_signals(f.ref), f.memorized) for f in fixtures]
    metrics = evaluate(rows, params)
    assert metrics.separation > 0.0  # the number itself is what the report records
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/detect/test_calibration.py -v`
Expected: FAIL — `Calibrator`/`evaluate` not yet defined.

- [ ] **Step 3: Implement** (append to `src/packer/engine/detect/calibration.py`)
```python
import numpy as np

from packer.engine.detect.ensemble import Ensemble
from packer.engine.detect.signals.base import SignalResult
from packer.engine.detect.verdict import LABEL_LIKELY

LabeledScores = list[tuple[list[SignalResult], bool]]


def _score_for(scores: list[SignalResult], name: str) -> float | None:
    for r in scores:
        if r.name == name:
            return r.score
    return None


def _fisher(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return 1.0
    p = np.asarray(pos, dtype=np.float64)
    n = np.asarray(neg, dtype=np.float64)
    var = float(p.var() + n.var() + 1e-6)
    return float((p.mean() - n.mean()) ** 2 / var)


def _combine(scores: list[SignalResult], weights: dict[str, float]) -> float:
    num = den = 0.0
    for r in scores:
        w = weights.get(r.name, 1.0)
        num += w * r.confidence * r.score
        den += w * r.confidence
    return num / den if den > 0 else 0.0


class Calibrator:
    def fit(self, labeled_scores: LabeledScores, cfg: object | None = None) -> CalibrationParams:
        """Deterministic per-signal Fisher weighting + threshold midpoints. Pure — no IO."""
        names = sorted({r.name for scores, _ in labeled_scores for r in scores})
        raw: dict[str, float] = {}
        for name in names:
            pos = [s for s in (_score_for(sc, name) for sc, y in labeled_scores if y) if s is not None]
            neg = [s for s in (_score_for(sc, name) for sc, y in labeled_scores if not y) if s is not None]
            raw[name] = _fisher(pos, neg)
        total = sum(raw.values()) or 1.0
        weights = {k: v / total * len(raw) for k, v in raw.items()}

        combos = [(_combine(sc, weights), y) for sc, y in labeled_scores]
        pos_c = [c for c, y in combos if y]
        neg_c = [c for c, y in combos if not y]
        mid = (float(np.mean(pos_c)) + float(np.mean(neg_c))) / 2 if pos_c and neg_c else 0.5
        likely = float(min(0.9, mid + 0.05))
        unlikely = float(max(0.1, mid - 0.05))
        return CalibrationParams("detect-v0", weights, likely, unlikely)

    def calibrate(
        self,
        fixtures: list[LabeledModel],
        cfg: object | None = None,
        *,
        loader: object | None = None,
    ) -> CalibrationParams:
        """Load each fixture (weights only), run signals, then `fit`. Assumes Phase-1
        fixtures exist under tests/**/fixtures/ (see plan assumptions)."""
        from packer.engine.detect.runner import run_signals

        rows: LabeledScores = [(run_signals(m.ref, loader=loader), m.memorized) for m in fixtures]
        return self.fit(rows, cfg)


def evaluate(labeled_scores: LabeledScores, params: CalibrationParams) -> Metrics:
    ens = Ensemble()
    tp = fp = tn = fn = 0
    pos_c: list[float] = []
    neg_c: list[float] = []
    for scores, y in labeled_scores:
        verdict = ens.score(scores, params)
        predicted = verdict.label == LABEL_LIKELY
        (pos_c if y else neg_c).append(verdict.score)
        if predicted and y:
            tp += 1
        elif predicted and not y:
            fp += 1
        elif not predicted and not y:
            tn += 1
        else:
            fn += 1
    n = tp + fp + tn + fn
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    separation = (
        float(np.mean(pos_c)) - float(np.mean(neg_c)) if pos_c and neg_c else 0.0
    )
    return Metrics(n, accuracy, precision, recall, separation)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/detect/test_calibration.py -v && uv run mypy src`
Expected: PASS + mypy clean. (Integration test is collected only under `-m integration` and skips without fixtures.)

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/calibration.py tests/unit/detect/test_calibration.py \
        tests/integration/detect/test_calibration_fixtures.py
git commit -m "feat(detect): add Calibrator fit/calibrate + evaluate harness"
```

---

### Task 11: `Detector.detect` runner

**Files:**
- Create: `src/packer/engine/detect/runner.py`
- Test: `tests/unit/detect/test_runner.py`

**Interfaces:**
- Consumes: `SIGNAL_REGISTRY`, `WeightAccessor`, `HFModelLoader`, `ModelRef`, `Ensemble`, `CalibrationParams`/`CalibrationStore`, `DetectReportBuilder`.
- Produces:
  - `Detector.detect(model_ref, cfg, ports) -> Report` — load weights only → run enabled signals via the registry → ensemble → `DetectReportBuilder`. Falls back to `CalibrationParams.default()` when the calibration version file is absent.
  - `run_signals(ref, *, loader=None, enabled=None) -> list[SignalResult]` — the load+analyze helper reused by the calibrator.
  - Imports `packer.engine.detect.signals` at module load so all five signals are registered before `detect` runs.

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_runner.py`:
```python
import numpy as np
from pathlib import Path
from safetensors.numpy import save_file

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.config_schema import DetectCfg
from packer.engine.common.types import ModelRef
from packer.engine.detect.calibration import CalibrationStore
from packer.engine.detect.runner import Detector
from packer.engine.models.loader import HFModelLoader


def _write_model(tmp_path: Path) -> Path:
    rng = np.random.default_rng(0)
    tensors = {
        "model.embed_tokens.weight": rng.standard_normal((256, 32)).astype(np.float32),
        "lm_head.weight": rng.standard_normal((256, 32)).astype(np.float32),
        "model.layers.0.mlp.up_proj.weight": rng.standard_normal((64, 32)).astype(np.float32),
        "model.layers.0.self_attn.q_proj.weight": rng.standard_normal((32, 32)).astype(np.float32),
    }
    p = tmp_path / "m.safetensors"
    save_file(tensors, str(p))
    return p


def test_detect_returns_detect_report(tmp_path: Path):
    model_path = _write_model(tmp_path)
    ports = EnginePorts(loader=HFModelLoader())
    cfg = DetectCfg()
    report = Detector(CalibrationStore(tmp_path)).detect(
        ModelRef(kind="path", value=str(model_path)), cfg, ports
    )

    assert report.kind == "detect"
    assert report.verdict.label in {"MEMORIZED-CODE-LIKELY", "INCONCLUSIVE", "UNLIKELY"}
    assert len(report.sections) == 5  # one per enabled signal
    assert any("signature" in note.lower() for note in report.limitations)


def test_detect_is_deterministic(tmp_path: Path):
    model_path = _write_model(tmp_path)
    ports = EnginePorts(loader=HFModelLoader())
    cfg = DetectCfg()
    det = Detector(CalibrationStore(tmp_path))
    a = det.detect(ModelRef(kind="path", value=str(model_path)), cfg, ports)
    b = det.detect(ModelRef(kind="path", value=str(model_path)), cfg, ports)
    assert a.to_json() == b.to_json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_runner.py -v`
Expected: FAIL — `runner` module missing.

- [ ] **Step 3: Implement**

`src/packer/engine/detect/runner.py`:
```python
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

import packer.engine.detect.signals  # noqa: F401  (import to self-register the five signals)
from packer.engine.common.registries import SIGNAL_REGISTRY
from packer.engine.common.types import ModelRef
from packer.engine.detect.calibration import CalibrationParams, CalibrationStore
from packer.engine.detect.ensemble import Ensemble
from packer.engine.detect.signals.base import SignalResult
from packer.engine.models.accessor import WeightAccessor
from packer.engine.models.loader import HFModelLoader
from packer.engine.report.builders import DetectReportBuilder
from packer.engine.report.model import Report

if TYPE_CHECKING:
    from packer.engine.models.loader import LoadedModel


class _Loader(Protocol):
    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> LoadedModel: ...


class _Ports(Protocol):
    loader: _Loader


class _DetectCfg(Protocol):
    enabled_signals: Sequence[str]
    calibration_version: str


class Detector:
    """Part-2 orchestrator. Loads weights ONLY, runs the config-enabled signals through
    the registry, combines them, and builds a detect `Report`. Never runs inference."""

    def __init__(self, calibration_store: CalibrationStore | None = None) -> None:
        self._store = calibration_store

    def detect(self, model_ref: ModelRef, cfg: _DetectCfg, ports: _Ports) -> Report:
        model = ports.loader.load(model_ref)  # tensors only
        weights = WeightAccessor(model)  # no forward-callable exposed
        results = [SIGNAL_REGISTRY.create(n).analyze(weights) for n in cfg.enabled_signals]
        calib = self._load_calibration(cfg.calibration_version)
        verdict = Ensemble().score(results, calib)
        return DetectReportBuilder().build(verdict, results)

    def _load_calibration(self, version: str) -> CalibrationParams:
        if self._store is None:
            return CalibrationParams.default()
        try:
            return self._store.load(version)
        except FileNotFoundError:
            return CalibrationParams.default()


def run_signals(
    ref: object,
    *,
    loader: _Loader | None = None,
    enabled: Sequence[str] | None = None,
) -> list[SignalResult]:
    """Load weights only and run each enabled signal. Reused by the calibrator."""
    active_loader: _Loader = loader if loader is not None else HFModelLoader()
    model = active_loader.load(ModelRef.parse(str(ref)))
    weights = WeightAccessor(model)
    names = list(enabled) if enabled is not None else SIGNAL_REGISTRY.names()
    return [SIGNAL_REGISTRY.create(n).analyze(weights) for n in names]
```
*(mypy-strict note: the `_Loader`/`_Ports`/`_DetectCfg` structural Protocols keep `detect` free of a hard dependency on the loosely-typed Phase-0 `EnginePorts.loader` and on Hydra's `DictConfig`; `EnginePorts`, `DetectCfg`, and a composed `cfg.engine.detect` all satisfy them at runtime.)*

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/detect/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/packer/engine/detect/runner.py tests/unit/detect/test_runner.py
git commit -m "feat(detect): add Detector.detect runner + run_signals helper"
```

---

### Task 12: No-inference gate test + Phase wrap-up

**Files:**
- Test: `tests/unit/detect/test_no_inference_gate.py`
- Verify only: `uv run lint-imports`, `uv run mypy src`, full unit suite.

**Interfaces:**
- Consumes: `Detector`, `run_signals`, `CalibrationStore`, `DetectCfg`.
- Produces: the **required** behavioral no-inference gate (ARCHITECTURE §5.4 / DEVELOPMENT §6 / ADR-007). A fake loader returns a model object whose `forward`/`generate` raise if ever called; `Detector.detect` must still complete and return a detect `Report`, proving detection never touches the forward path.

- [ ] **Step 1: Write the failing test**

`tests/unit/detect/test_no_inference_gate.py`:
```python
import numpy as np
import pytest

from packer.engine.common.config_schema import DetectCfg
from packer.engine.common.types import ModelRef
from packer.engine.detect.calibration import CalibrationStore
from packer.engine.detect.runner import Detector


class _LiveModel:
    """Stands in for a torch-backed model: exposes tensors (what signals may read) plus
    forward/generate that EXPLODE if inference is ever attempted."""

    def __init__(self) -> None:
        rng = np.random.default_rng(0)
        self.tensors = {
            "model.embed_tokens.weight": rng.standard_normal((128, 16)).astype(np.float32),
            "model.layers.0.mlp.up_proj.weight": rng.standard_normal((32, 16)).astype(np.float32),
            "model.layers.0.self_attn.q_proj.weight": rng.standard_normal((16, 16)).astype(np.float32),
        }
        self.config: dict[str, object] = {"vocab_size": 128}
        self.source = "fake"
        self.format = "safetensors"

    def forward(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("detect ran inference (forward) — no-inference wall breached!")

    def generate(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("detect ran inference (generate) — no-inference wall breached!")


class _FakeLoader:
    def load(self, ref: ModelRef, *, allow_pickle: bool = False) -> _LiveModel:
        return _LiveModel()


class _Ports:
    def __init__(self) -> None:
        self.loader = _FakeLoader()


def test_detect_completes_without_running_inference(tmp_path):
    report = Detector(CalibrationStore(tmp_path)).detect(
        ModelRef(kind="path", value="unused"), DetectCfg(), _Ports()
    )
    # Reaching here means forward/generate were never called (they would have raised).
    assert report.kind == "detect"
    assert report.verdict.label in {"MEMORIZED-CODE-LIKELY", "INCONCLUSIVE", "UNLIKELY"}
    assert len(report.sections) == 5


def test_calling_forward_would_raise():
    # Sanity: the trap is armed — a direct forward call blows up as designed.
    with pytest.raises(AssertionError):
        _LiveModel().forward()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/detect/test_no_inference_gate.py -v`
Expected: FAIL initially only if any signal path touched forward — it must PASS once the runner is correct. (If it fails because a signal reached for a forward-callable, that is a real bug to fix, not a test to weaken.)

- [ ] **Step 3: Implement**

No production code should be required — the architecture already forbids inference (`WeightAccessor` exposes tensors only; signals read matrices). If the gate fails, fix the offending signal/runner so it reads tensors only. This step exists to make the guarantee executable.

- [ ] **Step 4: Run the full Phase-2 verification**

Run:
```bash
uv run pytest tests/unit/detect tests/unit/report -v
uv run pytest tests/unit
uv run mypy src
uv run lint-imports          # "detect runs no inference" + clean-layering contracts KEPT
uv run ruff check . && uv run ruff format --check .
```
Expected: all PASS; import-linter reports all contracts kept (in particular `torch.nn.functional` absent from `detect`, and `report` importing only `common`).

- [ ] **Step 5: Commit**
```bash
git add tests/unit/detect/test_no_inference_gate.py
git commit -m "test(detect): add behavioral no-inference gate (forward/generate never called)"
```

---

## Phase 2 Definition of Done

- [ ] `uv run pytest tests/unit/detect tests/unit/report` green; `uv run mypy src` clean; `uv run lint-imports` reports all contracts kept (incl. "detect runs no inference").
- [ ] The **no-inference gate** passes: `Detector.detect` completes with the model's `forward`/`generate` rigged to raise.
- [ ] Each of the five signals (`spectral`, `weight_norm`, `embedding`, `rank`, `metadata`) has a unit test against synthetic numpy matrices, returns `SignalResult` with `score`/`confidence` in `[0,1]` and evidence, and self-registers in `SIGNAL_REGISTRY`.
- [ ] `Ensemble.score` is monotonic in stronger signals, discounts low-confidence signals, and maps to `MEMORIZED-CODE-LIKELY | INCONCLUSIVE | UNLIKELY` via calibrated thresholds.
- [ ] `Calibrator.fit`/`calibrate` produce versioned `CalibrationParams`; `evaluate` returns measured accuracy/precision/recall + memorized-vs-control separation; `CalibrationStore` round-trips params.
- [ ] `Detector.detect(model_ref, cfg, ports)` returns a unified `Report(kind="detect")` with per-signal sections, evidence, and the ADR-007 limitation note; detection is deterministic (same model ⇒ same report).
- [ ] The shared `engine/report/` kernel exists (`Report`/`VerdictBlock`/`ReportSection`, `to_json()`/`to_text()`, `ReportBuilder`/`DetectReportBuilder`) and imports only `engine.common` — ready for Phase 3's `ScanReportBuilder`.
- [ ] Detect config group (`engine/detect: ensemble`, `DetectCfg`) composes via `compose_config()`.

## Self-Review Notes

- **Spec coverage** (phase-2 spec): five inference-free signals ✓ (T2–T6); ensemble scorer ✓ (T9); calibration + evaluation harness ✓ (T10); shared report generator (JSON + rendered) ✓ (T7–T8); `detect` runner ✓ (T11); no-inference enforcement — structural (WeightAccessor, from Phase 0) + dependency (import-linter, verified T12) + behavioral gate (T12) ✓. Acceptance criteria in spec §6 map to the DoD above one-for-one.
- **Interfaces produced here, consumed downstream:** `detect.signals.base.SignalResult`; the five signals under their registered names; `detect.verdict.Verdict` + label constants; `detect.ensemble.Ensemble`; `detect.calibration.{CalibrationParams, Metrics, CalibrationStore, Calibrator, evaluate, LabeledModel}`; `detect.runner.{Detector, run_signals}`; and the reporting kernel `report.model.{Report, VerdictBlock, ReportSection, VerdictLike, SignalResultLike}` + `report.builders.{ReportBuilder, DetectReportBuilder}`. Phase 3 consumes the report kernel (adds `ScanReportBuilder`) and Phase 4 consumes `Detector.detect` + `Report`.
- **Interfaces consumed from Phase 0 (exact names):** `packer.engine.models.accessor.WeightAccessor` (tensors-only: `attention_matrices`, `mlp_matrices`, `embedding`, `unembedding`, `config`); `packer.engine.models.loader.HFModelLoader`/`LoadedModel`; `packer.engine.common.registries.SIGNAL_REGISTRY`; `packer.engine.common.ports.Signal`; `packer.engine.common.registry.Registry`; `packer.engine.common.errors.{PackerError, ConfigError}`; `packer.engine.common.types.ModelRef`; `packer.engine.common.assembler.EnginePorts`; `packer.engine.common.config_schema.compose_config`.
- **Cross-phase assumption (Phase 1 fixtures):** calibration/evaluation against real memorized `.pak`s + controls under `tests/**/fixtures/` is exercised by a single **integration-marked** test that **skips** when fixtures are absent, so Phase 2's unit suite (and CI `quality` job) is fully green independently of Phase 1. When Phase 1 lands its fixtures, the integration test records the measured separation number (spec §6, ADR-007 "measured, not guaranteed").
- **You also created `engine/report/`** (Task 7–8) — the unified, versioned reporting kernel shared by detect + scan. Builders use structural Protocols (`VerdictLike`/`SignalResultLike`) so `report` imports only `engine.common`, keeping the Dependency Rule acyclic; Phase 3 adds `ScanReportBuilder` against the identical `Report` model with no changes to it.
- **Open/closed honored:** adding a sixth signal = one new module in `detect/signals/` + one line in `signals/__init__.py` + its name in `enabled_signals`; the ensemble, runner, calibrator, and report builder are untouched. The runner instantiates signals only via `SIGNAL_REGISTRY.create(...)` — no concrete signal class is named in orchestration.
- **3.10 compliance:** `from __future__ import annotations` everywhere; `X | Y` unions and PEP 585 generics only; no `Self`/`tomllib`/`except*`/`type` statement. New generics are parameterized (`dict[str, object]`) for mypy-strict `disallow_any_generics`.
- **No new dependencies:** numpy/scipy/pydantic are Phase-0 deps; no `uv add` and no `uv.lock` change in this phase.
