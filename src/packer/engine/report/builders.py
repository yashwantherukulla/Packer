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
    "Detection is inference-free (weights + metadata only) and cannot recover the stored "
    "code — Part 3 does that.",
    "It cannot, in general, distinguish memorized code from memorized other data; Part 3 "
    "confirms via extraction.",
]


class ReportBuilder:
    """Base for report builders. Subclasses assemble a ``Report`` of one ``kind`` from
    analysis outputs. Phase 3 adds ``ScanReportBuilder`` alongside ``DetectReportBuilder``."""

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
            r.name: {"score": float(r.score), "confidence": float(r.confidence)} for r in results
        }
        return Report(
            kind="detect",
            verdict=self._verdict_block(verdict),
            sections=sections,
            evidence=evidence,
            limitations=list(_DETECT_LIMITATIONS),
        )
