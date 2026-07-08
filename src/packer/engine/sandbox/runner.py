from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecUnit:
    """One runnable file to execute in the sandbox."""

    filename: str
    data: bytes
    lang: str  # "python" (image runtimes only; scope-limited, spec §1)
    argv: tuple[str, ...] = ()


@dataclass(frozen=True)
class SandboxResult:
    """Captured behavior of a single sandbox run (spec §2)."""

    stdout: str
    stderr: str
    exit_code: int | None  # None when killed (timeout / pids)
    timed_out: bool
    syscalls: tuple[str, ...] = field(default_factory=tuple)  # from strace -f
    fs_writes: tuple[str, ...] = field(default_factory=tuple)  # writes outside tmpfs
    net_attempts: tuple[str, ...] = field(default_factory=tuple)  # blocked connect() targets
    duration_s: float = 0.0
