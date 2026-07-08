from __future__ import annotations

from typing import Any

from packer.engine.common.errors import ScanError
from packer.engine.common.progress import null_progress
from packer.engine.extract.service import ExtractionService
from packer.engine.report.builders import ScanReportBuilder
from packer.engine.report.model import Report
from packer.engine.sandbox.analyzers import DynamicAnalyzer, StaticAnalyzer
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.scorer import RiskScorer


class ScanPipeline:
    """Extract -> static -> dynamic -> score -> Report(kind='scan') (SYSTEM-DESIGN §5.5)."""

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
        dynamic: list[Finding] = []
        for unit in fileset.exec_units():
            dynamic.extend(self._dynamic.analyze(unit, ports.sandbox, policy))

        progress(step="score", pct=0.9, detail="risk scoring")
        risk = self._scorer.score(static, dynamic, cfg.sandbox.risk)

        report = self._builder.build(extraction, static, dynamic, risk)
        progress(step="done", pct=1.0, detail=risk.verdict)
        return report
