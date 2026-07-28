from pathlib import Path

import pytest

from packer.engine.common.errors import SandboxError
from packer.engine.common.registries import SANDBOX_REGISTRY
from packer.engine.sandbox.adapters.docker import DockerSandboxRunner
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit


class _FakeContainer:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.removed = False
        self.events = []
        self.source_dir = Path(next(iter(kwargs["volumes"])))
        self.source_files = {path.name: path.read_bytes() for path in self.source_dir.iterdir()}

    def start(self):
        self.events.append("start")
        return None

    def wait(self, timeout=None):
        self.events.append("wait")
        return {"StatusCode": 0}

    def logs(self, stdout=True, stderr=False):
        return b"hello\n" if stdout else b""

    def get_archive(self, path):
        raise KeyError("no trace")  # exercises graceful degrade

    def kill(self):
        return None

    def remove(self, force=False):
        self.removed = True


class _FakeContainers:
    def __init__(self):
        self.last = None

    def create(self, **kwargs):
        self.last = _FakeContainer(kwargs)
        return self.last


class _FakeClient:
    def __init__(self):
        self.containers = _FakeContainers()


def test_registered_under_docker():
    assert "docker" in SANDBOX_REGISTRY.names()


def test_run_applies_hardened_flags():
    client = _FakeClient()
    runner = DockerSandboxRunner(client=client)
    pol = SandboxPolicy(image="packer-sandbox:latest")
    res = runner.run(ExecUnit(filename="a.py", data=b"print('hello')", lang="python"), pol)
    kw = client.containers.last.kwargs
    cmd = kw["command"]
    assert kw["network_mode"] == "none"
    assert kw["read_only"] is True
    assert kw["cap_drop"] == ["ALL"]
    assert kw["pids_limit"] == 64
    assert kw["user"] == "1000:1000"
    assert kw["mem_limit"] == "256m"
    assert "/scratch" in kw["tmpfs"]
    assert "uid=1000" in kw["tmpfs"]["/scratch"]
    assert "gid=1000" in kw["tmpfs"]["/scratch"]
    assert "mode=1777" in kw["tmpfs"]["/scratch"]
    assert cmd[:4] == ["strace", "-f", "-qq", "-o"]
    python_index = cmd.index("python3")
    assert cmd[python_index + 1] == "/packer-source/a.py"
    assert "print('hello')" not in cmd
    assert kw["volumes"][str(client.containers.last.source_dir)] == {
        "bind": "/packer-source",
        "mode": "ro",
    }
    assert client.containers.last.source_files == {"a.py": b"print('hello')"}
    assert client.containers.last.events[:2] == ["start", "wait"]
    assert not client.containers.last.source_dir.exists()
    assert res.exit_code == 0 and res.timed_out is False
    assert "hello" in res.stdout


def test_docker_errors_become_sandbox_error():
    import docker.errors as de

    class _Boom(_FakeContainers):
        def create(self, **kwargs):
            raise de.APIError("daemon exploded")

    client = _FakeClient()
    client.containers = _Boom()
    with pytest.raises(SandboxError):
        DockerSandboxRunner(client=client).run(
            ExecUnit(filename="a.py", data=b"x", lang="python"), SandboxPolicy(image="i")
        )


def test_source_path_cannot_collide_with_trace_control_file():
    client = _FakeClient()

    DockerSandboxRunner(client=client).run(
        ExecUnit(filename="trace.log", data=b"print('safe')", lang="python"),
        SandboxPolicy(image="i"),
    )

    command = client.containers.last.kwargs["command"]
    python_index = command.index("python3")
    assert command[python_index + 1] == "/packer-source/trace.log"
    assert command[command.index("-o") + 1] == "/scratch/trace.log"


def test_failed_container_start_is_a_sandbox_error_and_resources_are_removed():
    import docker.errors as de

    class _RejectingContainer(_FakeContainer):
        def start(self):
            raise de.APIError("start failed")

    class _RejectingContainers(_FakeContainers):
        def create(self, **kwargs):
            self.last = _RejectingContainer(kwargs)
            return self.last

    client = _FakeClient()
    client.containers = _RejectingContainers()

    with pytest.raises(SandboxError, match="sandbox run failed"):
        DockerSandboxRunner(client=client).run(
            ExecUnit(filename="a.py", data=b"x", lang="python"),
            SandboxPolicy(image="i"),
        )

    assert client.containers.last.removed is True
    assert not client.containers.last.source_dir.exists()
