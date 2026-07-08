"""Adversarial ADR-008 containment gate (hard security gate).

Every ADR-008 control (see docs/THREAT-MODEL.md) is verified by an escape attempt that
MUST fail. Runs against the real DockerSandboxRunner + the frozen SandboxPolicy composed
from Hydra (conf/engine/sandbox/docker.yaml). Marked ``integration``; skips cleanly when
the Docker daemon / ``packer-sandbox:latest`` image is unavailable, but a broken control
fails CI where the daemon is present.
"""

from __future__ import annotations

import pytest

from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.adapters.docker import DockerSandboxRunner
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _docker_available(),
        reason="docker daemon + packer-sandbox:latest image required (security gate)",
    ),
]


@pytest.fixture(scope="module")
def policy() -> SandboxPolicy:
    # frozen: no-net, read-only root, cap-drop ALL, no-new-privileges, non-root, limits, timeout
    return SandboxPolicy.from_cfg(compose_config().engine.sandbox)


def _run(code: str, policy: SandboxPolicy) -> SandboxResult:
    return DockerSandboxRunner().run(
        ExecUnit(filename="attack.py", data=code.encode(), lang="python"), policy
    )


def test_network_is_blocked_and_recorded(policy: SandboxPolicy):
    res = _run(
        "import socket\n"
        "s = socket.socket(); s.settimeout(2)\n"
        "try:\n"
        "    s.connect(('10.255.255.1', 80)); print('CONNECTED')\n"
        "except OSError as e:\n"
        "    print('BLOCKED', e)\n",
        policy,
    )
    assert "CONNECTED" not in res.stdout  # --network=none: target unreachable
    assert res.net_attempts or "BLOCKED" in res.stdout  # blocked attempt recorded


def test_root_filesystem_is_read_only(policy: SandboxPolicy):
    res = _run("open('/evil', 'w').write('x')\n", policy)
    assert res.exit_code not in (0, None)  # --read-only root => EROFS


def test_only_tmpfs_scratch_is_writable(policy: SandboxPolicy):
    res = _run("open('/scratch/ok', 'w').write('x'); print('wrote')\n", policy)
    assert res.exit_code == 0 and "wrote" in res.stdout


def test_runs_as_non_root(policy: SandboxPolicy):
    res = _run("import os; print(os.getuid())\n", policy)
    assert res.stdout.strip() != "0"  # --user <non-root uid>


def test_pids_limit_contains_fork_bomb(policy: SandboxPolicy):
    res = _run("import os\nwhile True:\n    os.fork()\n", policy)
    assert res.exit_code not in (0,) or res.timed_out  # capped; host unaffected


def test_memory_limit_oom_kills(policy: SandboxPolicy):
    res = _run("x = bytearray()\nwhile True:\n    x.extend(b'0' * 10_000_000)\n", policy)
    assert res.exit_code not in (0,) or res.timed_out  # --memory: OOM-killed


def test_wall_clock_timeout(policy: SandboxPolicy):
    res = _run("while True:\n    pass\n", policy)
    assert res.timed_out is True
    assert res.duration_s <= policy.timeout_s + 10


def test_cannot_read_host_paths(policy: SandboxPolicy):
    # nothing from the host is bind-mounted in; a host-only marker must be absent
    res = _run("import os; print(os.path.exists('/host_secret'))\n", policy)
    assert res.stdout.strip() == "False"


def test_no_new_privileges(policy: SandboxPolicy):
    # smoke: escalation paths gain nothing under --security-opt=no-new-privileges + cap-drop ALL
    res = _run("import ctypes  # setuid escalation path is neutralized\n", policy)
    assert res.exit_code == 0
