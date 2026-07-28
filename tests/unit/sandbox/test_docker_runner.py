import io
import tarfile

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
        self.archive = b""

    def start(self):
        self.events.append("start")
        return None

    def put_archive(self, path, data):
        self.events.append("put_archive")
        self.archive_path = path
        self.archive = data
        return True

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
    assert cmd[:2] == ["/bin/sh", "-c"]
    python_index = cmd.index("python3")
    assert cmd[python_index + 1] == "/scratch/source/a.py"
    assert "print('hello')" not in cmd
    assert client.containers.last.events[:3] == ["start", "put_archive", "wait"]
    assert client.containers.last.archive_path == "/scratch"
    with tarfile.open(fileobj=io.BytesIO(client.containers.last.archive), mode="r") as archive:
        source = archive.extractfile("source/a.py")
        assert source is not None
        assert source.read() == b"print('hello')"
        assert archive.getmember("source").isdir()
        assert ".packer-source-ready" in archive.getnames()
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
    assert command[python_index + 1] == "/scratch/source/trace.log"
    assert command[command.index("-o") + 1] == "/scratch/trace.log"


def test_failed_source_copy_is_a_sandbox_error_and_container_is_removed():
    class _RejectingContainer(_FakeContainer):
        def put_archive(self, path, data):
            self.events.append("put_archive")
            return False

    class _RejectingContainers(_FakeContainers):
        def create(self, **kwargs):
            self.last = _RejectingContainer(kwargs)
            return self.last

    client = _FakeClient()
    client.containers = _RejectingContainers()

    with pytest.raises(SandboxError, match="failed to copy source"):
        DockerSandboxRunner(client=client).run(
            ExecUnit(filename="a.py", data=b"x", lang="python"),
            SandboxPolicy(image="i"),
        )

    assert client.containers.last.removed is True
