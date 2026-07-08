from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packer.engine.sandbox.findings import Finding


@dataclass(frozen=True)
class RiskReport:
    verdict: str  # "benign" | "suspicious" | "malicious"
    score: float  # normalized [0,1]
    confidence: float
    per_file: dict[str, float] = field(default_factory=dict)
    disagreements: tuple[str, ...] = field(default_factory=tuple)
    findings: tuple[Finding, ...] = field(default_factory=tuple)


class RiskScorer:
    """Calibrated combination of static + dynamic findings into a verdict
    (ADR-009). Surfaces static/dynamic disagreement rather than hiding it."""

    def score(self, static: list[Finding], dynamic: list[Finding], calib: Any) -> RiskReport:
        weights = {
            "info": float(calib.weight_info),
            "low": float(calib.weight_low),
            "medium": float(calib.weight_medium),
            "high": float(calib.weight_high),
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
            verdict=verdict,
            score=score,
            confidence=confidence,
            per_file=per_file,
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

    def _disagreements(
        self,
        static: list[Finding],
        dynamic: list[Finding],
        weights: dict[str, float],
        calib: Any,
    ) -> tuple[str, ...]:
        thr = float(calib.malicious)
        s_max = max((weights.get(f.severity, 0.0) for f in static), default=0.0)
        d_max = max((weights.get(f.severity, 0.0) for f in dynamic), default=0.0)
        out: list[str] = []
        if s_max >= thr and d_max < float(calib.suspicious):
            out.append(
                "static-only high risk: flagged statically but no malicious runtime "
                "behavior observed"
            )
        if d_max >= thr and s_max < float(calib.suspicious):
            out.append(
                "dynamic-only high risk: benign-looking source but malicious runtime behavior"
            )
        return tuple(out)


def calibrate(labeled: list[tuple[list[Finding], list[Finding], str]], calib: Any) -> Any:
    """Hook for tuning thresholds/weights on a labeled set. MVP returns calib
    unchanged (thresholds come from Hydra); evaluate() reports the achieved metric."""
    return calib


def evaluate(
    labeled: list[tuple[list[Finding], list[Finding], str]], calib: Any
) -> dict[str, float]:
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
    return {"precision": precision, "recall": recall, "accuracy": (tp + tn) / max(len(labeled), 1)}
