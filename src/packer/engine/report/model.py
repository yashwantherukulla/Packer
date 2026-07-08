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
    """The one report value object, two ``kind``s, shared by detect (Phase 2) and scan
    (Phase 3). Versioned; readers dispatch on ``schema_version`` (SYSTEM-DESIGN §5.6)."""

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
    """Structural shape the builders consume — ``detect.Verdict`` satisfies it by shape,
    so ``report`` never imports ``detect`` (keeps the layering acyclic)."""

    label: str
    score: float
    confidence: float


@runtime_checkable
class SignalResultLike(Protocol):
    name: str
    score: float
    confidence: float
    evidence: dict[str, object]
