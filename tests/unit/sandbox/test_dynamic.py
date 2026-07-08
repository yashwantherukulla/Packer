from packer.engine.sandbox.analyzers import DynamicAnalyzer
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult


class _FakeSandbox:
    def __init__(self, result):
        self._result = result
        self.calls = 0

    def run(self, unit, policy):
        self.calls += 1
        return self._result


def test_dynamic_flags_network_and_timeout():
    result = SandboxResult(
        stdout="",
        stderr="",
        exit_code=None,
        timed_out=True,
        syscalls=("execve", "ptrace"),
        fs_writes=("openat(/etc/x, O_WRONLY)",),
        net_attempts=("connect(AF_INET, 1.1.1.1:53)",),
        duration_s=20.0,
    )
    sandbox = _FakeSandbox(result)
    findings = DynamicAnalyzer().analyze(
        ExecUnit(filename="a.py", data=b"", lang="python"), sandbox, SandboxPolicy(image="i")
    )
    assert sandbox.calls == 1
    rules = {f.rule for f in findings}
    assert "dynamic.network-attempt" in rules
    assert "dynamic.fs-write" in rules
    assert "dynamic.timeout" in rules
    assert any(f.rule.startswith("dynamic.syscall.") for f in findings)
    assert any(f.severity == "high" for f in findings)  # network attempt is high


def test_dynamic_benign_run_has_no_high_findings():
    result = SandboxResult(
        stdout="ok",
        stderr="",
        exit_code=0,
        timed_out=False,
        syscalls=("execve", "write", "exit_group"),
    )
    findings = DynamicAnalyzer().analyze(
        ExecUnit(filename="a.py", data=b"", lang="python"),
        _FakeSandbox(result),
        SandboxPolicy(image="i"),
    )
    assert all(f.severity != "high" for f in findings)
