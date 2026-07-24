from __future__ import annotations

from typing import Protocol, cast

import packer.engine.sandbox.static  # noqa: F401  (self-registration)
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult

# syscalls that, while not proof of malice, warrant a low-severity note in the trace
_SUSPICIOUS_SYSCALLS = {
    "ptrace",
    "mount",
    "setuid",
    "setgid",
    "chroot",
    "init_module",
    "kexec_load",
}


class _SandboxRunner(Protocol):
    """Structural view of the SandboxRunner port (references sandbox-owned types, so it
    lives here rather than in the kernel — same rationale as the pack/detect ports)."""

    def run(self, unit: ExecUnit, policy: SandboxPolicy) -> SandboxResult: ...


class DynamicAnalyzer:
    """Runs one ExecUnit through the injected SandboxRunner port and turns the
    captured SandboxResult into Findings (spec §2, ADR-009)."""

    def analyze(
        self, unit: ExecUnit, sandbox: _SandboxRunner, policy: SandboxPolicy
    ) -> list[Finding]:
        result = sandbox.run(unit, policy)
        findings: list[Finding] = []
        for addr in result.net_attempts:
            findings.append(
                Finding(
                    "high",
                    "dynamic.network-attempt",
                    unit.filename,
                    0,
                    f"blocked outbound network attempt: {addr}",
                )
            )
        for path in result.fs_writes:
            findings.append(
                Finding(
                    "medium", "dynamic.fs-write", unit.filename, 0, f"write outside tmpfs: {path}"
                )
            )
        if result.timed_out:
            findings.append(
                Finding(
                    "medium",
                    "dynamic.timeout",
                    unit.filename,
                    0,
                    f"exceeded {policy.timeout_s}s wall-clock (possible hang/CPU abuse)",
                )
            )
        for sc in sorted(_SUSPICIOUS_SYSCALLS.intersection(result.syscalls)):
            findings.append(
                Finding(
                    "low",
                    f"dynamic.syscall.{sc}",
                    unit.filename,
                    0,
                    f"used privileged/suspicious syscall {sc}",
                )
            )
        if not result.syscalls:
            findings.append(
                Finding(
                    "info",
                    "dynamic.trace-unavailable",
                    unit.filename,
                    0,
                    "syscall trace unavailable; behavior fidelity reduced (fs-diff/net only)",
                )
            )
        return findings


class _Scanner(Protocol):
    """Structural view of the Scanner port (references the sandbox-owned ``FileSet``,
    so it lives here rather than in the kernel — same rationale as the sandbox runner)."""

    def scan(self, files: FileSet) -> list[Finding]: ...


class StaticAnalyzer:
    """Runs the config-enabled subset of SCANNER_REGISTRY over a FileSet.
    Orchestration only — knows no concrete scanner (open/closed, SYSTEM-DESIGN §3.4)."""

    def scan(self, files: FileSet, enabled: list[str]) -> list[Finding]:
        findings: list[Finding] = []
        for name in enabled:
            scanner = cast(_Scanner, SCANNER_REGISTRY.create(name))  # ConfigError on unknown name
            findings.extend(scanner.scan(files))
        return findings
