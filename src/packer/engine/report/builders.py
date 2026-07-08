from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from packer.engine.report.model import (
    REPORT_SCHEMA_VERSION,
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


class _FindingLike(Protocol):
    """Structural shape of a ``sandbox.Finding`` — lets ``report`` (a lower layer)
    consume findings without importing ``sandbox`` (keeps the layering acyclic,
    same pattern as ``VerdictLike``). Read-only members: frozen dataclasses satisfy them."""

    @property
    def severity(self) -> str: ...
    @property
    def rule(self) -> str: ...
    @property
    def file(self) -> str: ...
    @property
    def line(self) -> int: ...
    @property
    def note(self) -> str: ...


class _ExtractionLike(Protocol):
    @property
    def files(self) -> dict[str, bytes]: ...
    @property
    def confidence_class(self) -> str: ...
    @property
    def notes(self) -> tuple[str, ...]: ...


class _RiskReportLike(Protocol):
    @property
    def verdict(self) -> str: ...
    @property
    def score(self) -> float: ...
    @property
    def confidence(self) -> float: ...
    @property
    def per_file(self) -> dict[str, float]: ...
    @property
    def disagreements(self) -> tuple[str, ...]: ...


class ScanReportBuilder(ReportBuilder):
    """Builds the unified Report(kind='scan') from extraction + analysis results
    (SYSTEM-DESIGN §5.5/§5.6). Same Report model the Detector uses. Consumes the
    extract/sandbox value objects **structurally** so ``report`` never imports the
    higher layers it feeds (mirrors the ``VerdictLike`` pattern in ``model.py``)."""

    kind = "scan"

    def build(
        self,
        extraction: _ExtractionLike,
        static: Sequence[_FindingLike],
        dynamic: Sequence[_FindingLike],
        risk: _RiskReportLike,
    ) -> Report:
        sections = [
            self._findings_section("static-findings", static),
            self._findings_section("dynamic-behavior", dynamic),
            ReportSection(title="per-file-risk", body={"scores": dict(risk.per_file)}),
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
            schema_version=REPORT_SCHEMA_VERSION,
            verdict=VerdictBlock(
                label=risk.verdict, score=float(risk.score), confidence=float(risk.confidence)
            ),
            sections=sections,
            evidence={
                "confidence_class": extraction.confidence_class,
                "n_files": len(extraction.files),
                "disagreements": list(risk.disagreements),
            },
            limitations=limitations,
        )

    def _findings_section(self, title: str, findings: Sequence[_FindingLike]) -> ReportSection:
        rows: list[dict[str, object]] = [
            {"severity": f.severity, "rule": f.rule, "file": f.file, "line": f.line, "note": f.note}
            for f in findings
        ]
        return ReportSection(title=title, body={"count": len(rows), "findings": rows})
