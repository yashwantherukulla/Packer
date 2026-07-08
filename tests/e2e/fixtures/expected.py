"""Single source of truth for the E2E chain's expected outcomes."""

from __future__ import annotations

DETECT_VERDICT = "MEMORIZED-CODE-LIKELY"

# per-file scan labels — the Part-3 RiskScorer verdict for each planted unit
FILE_LABELS: dict[str, str] = {
    "hello.py": "benign",
    "exfil.py": "malicious",
}

# tiny pack config overrides posted to /pack so training finishes fast on CPU
PACK_OVERRIDES: dict[str, object] = {
    "engine/pack": "e2e_tiny",  # selects conf/engine/pack/e2e_tiny.yaml
}
