# Phase 2 — Detector (Part 2)

> **Goal:** decide, **from weights and metadata only (no inference)**, whether a model carries a memorized-corpus signature — with calibrated confidence and per-signal evidence.
> **Depends on:** Phase 0; Phase 1 for calibration fixtures. **Blocks:** Phase 4 (API surface).
> **Part mapping:** Part 2.

---

## 1. Scope

**In scope**
- Five inference-free signals (ARCHITECTURE §5.3): spectral/RMT, weight-norm profile, embedding/unembedding structure, effective/stable rank, config/metadata heuristics.
- Ensemble scorer + calibration harness (fit on Phase-1 fixtures).
- Report generator: verdict `MEMORIZED-CODE-LIKELY | INCONCLUSIVE | UNLIKELY`, overall confidence, per-signal `{score, confidence, evidence}`.
- **No-inference enforcement** (architectural + tested).

**Out of scope**
- Recovering the code (that's Part 3, and requires inference). Distinguishing memorized *code* from memorized *other data* with certainty (documented limitation, ADR-007).

---

## 2. Modules & interfaces

`engine/detect/signals/base.py`
```python
from dataclasses import dataclass

@dataclass
class SignalResult:
    name: str
    score: float        # [0,1] anomaly/memorization strength
    confidence: float   # [0,1]
    evidence: dict      # numbers + short human-readable notes

class Signal(Protocol):
    name: str
    def analyze(self, model: "LoadedModel") -> SignalResult: ...
    # MUST NOT call model.forward / generate. Reads tensors + config only.
```

Signals (one module each): `spectral.py` (SVD vs. Marchenko–Pastur, heavy-tail alpha, outlier singular values), `weight_norm.py` (layerwise Frobenius/spectral norms + growth), `embedding.py` (per-token norm distribution + entropy of embedding & LM-head, dead-region fraction), `rank.py` (stable rank, effective rank per layer), `metadata.py` (param count, vocab/param ratios, tokenizer-fit heuristics, `.pak`-shaped manifest presence).

`engine/detect/ensemble.py`
```python
def score(results: list[SignalResult], cfg: "EnsembleCfg") -> "Verdict":
    """Weighted, calibrated combination → verdict + overall confidence."""
```

`engine/detect/calibration.py`
```python
def calibrate(fixtures: "list[LabeledModel]", cfg) -> "CalibrationParams":
    """Fit signal weights/thresholds on memorized vs. control fixtures.
    Persist params (versioned) so runtime detection is reproducible."""

def evaluate(fixtures, params) -> "Metrics":   # accuracy/precision/recall — a MEASURED number
```

`engine/detect/runner.py`
```python
def detect(model_ref, cfg, progress) -> "DetectReport":
    """load weights ONLY → run signals → ensemble → report."""
```

---

## 3. Integration points

- **Reads weights via Phase-0 `load_model` / `iter_weight_matrices`.** Accepts HF id, uploaded model, or `.pak` (reads its `model.safetensors`).
- **Calibration consumes Phase-1 fixtures** (memorized positives; random-init + normal-trained negatives).
- **Report model is shared with Part 3** via `engine/report/` (unified `Report` type) so the API/UI render both consistently.
- Signal weights + thresholds come from Hydra `engine/detect/ensemble.yaml`; calibrated params are loaded as a versioned artifact.

---

## 4. Testing plan

- **No-inference gate (correctness):** run `detect` with the model's `forward`/`generate` monkeypatched to raise; detection must still complete. This is a required CI test and the enforcement of ADR-007.
- **Per-signal unit tests:** each signal returns `[0,1]` scores; on a synthetic random matrix the spectral signal matches Marchenko–Pastur (low anomaly); on a rank-1-perturbed matrix it flags an outlier singular value.
- **Ensemble:** monotonic in stronger signals; graceful when a signal returns low confidence.
- **Calibration/evaluation harness:** on the fixture set, reports accuracy/precision/recall; separation between memorized and control above the agreed threshold (recorded in the report, not hard-guaranteed).
- **Determinism:** same model ⇒ same report.

---

## 5. Development steps (ordered)

1. `Signal` protocol + `SignalResult` + shared numerics helpers (SVD, norms) in `engine/detect/signals/`.
2. Implement signals in order of confidence: spectral → embedding → rank → weight-norm → metadata (+ unit tests each).
3. Ensemble scorer (uncalibrated first).
4. Calibration + evaluation harness against Phase-1 fixtures.
5. Report generator (JSON + rendered) via `engine/report/`.
6. `detect` runner + no-inference test.

---

## 6. Acceptance criteria (milestone gate)

- [ ] The no-inference test passes (forward path never called).
- [ ] Each of the five signals has unit tests and returns calibrated `[0,1]` output with evidence.
- [ ] On the fixture set, the ensemble separates memorized from control models above the agreed accuracy threshold, and the number is written into the evaluation report.
- [ ] `detect` produces a JSON + human-readable report with verdict, confidence, and per-signal evidence.
- [ ] Report explicitly states the "signature, not proof; cannot recover code" limitation.

---

## 7. Risks

- **Open research problem; signals may be weak** (R2) → ensemble + calibration; ship confidence + evidence; treat accuracy as measured. Add signals incrementally.
- **Foreign-architecture models** (unexpected tensor names) → `iter_weight_matrices` must be robust; signals degrade to low-confidence rather than crash.
- **Overfitting the detector to Phase-1 fixtures** → include diverse controls; hold out a fixture subset for evaluation.
