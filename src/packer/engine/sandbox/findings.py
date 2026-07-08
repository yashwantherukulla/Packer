from __future__ import annotations

from dataclasses import dataclass

SEVERITIES = ("info", "low", "medium", "high", "critical")


@dataclass(frozen=True)
class Finding:
    """Immutable analysis finding (SYSTEM-DESIGN §3.1). Produced by scanners and
    the dynamic analyzer; consumed by the scorer and the report builder.
    Dynamic findings use a 'dynamic.*' rule prefix so provenance is explicit."""

    severity: str  # one of SEVERITIES
    rule: str
    file: str
    line: int
    note: str
