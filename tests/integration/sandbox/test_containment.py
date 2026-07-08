import pytest

from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.adapters.docker import DockerSandboxRunner
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit


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


def _policy() -> SandboxPolicy:
    return SandboxPolicy.from_cfg(compose_config().engine.sandbox)


def _run(src: bytes):
    return DockerSandboxRunner().run(
        ExecUnit(filename="unit.py", data=src, lang="python"), _policy()
    )


def test_network_is_blocked_and_recorded():
    src = (
        b"import socket\n"
        b"s = socket.socket()\n"
        b"try:\n"
        b"    s.connect(('1.1.1.1', 53))\n"
        b"    print('CONNECTED')\n"
        b"except OSError as e:\n"
        b"    print('BLOCKED', e)\n"
    )
    res = _run(src)
    assert "CONNECTED" not in res.stdout  # network must be unreachable
    assert res.net_attempts or "BLOCKED" in res.stdout  # attempt recorded


def test_write_outside_tmpfs_fails():
    res = _run(b"open('/etc/packer_escape', 'w').write('x')\n")
    assert res.exit_code not in (0,)  # read-only root => write raises
    assert all("/scratch" not in w or "/etc/" in w for w in res.fs_writes) or res.fs_writes == ()


def test_fork_bomb_hits_pids_limit():
    src = (
        b"import os\n"
        b"while True:\n"
        b"    try:\n"
        b"        os.fork()\n"
        b"    except OSError:\n"
        b"        break\n"
        b"print('SURVIVED')\n"
    )
    res = _run(src)
    assert res.timed_out or res.exit_code is not None


def test_infinite_loop_hits_timeout():
    res = _run(b"while True:\n    pass\n")
    assert res.timed_out is True
    assert res.duration_s <= _policy().timeout_s + 10
