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

    def put_archive(self, path, data):
        return True

    def start(self):
        return None

    def wait(self, timeout=None):
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
    assert kw["network_mode"] == "none"
    assert kw["read_only"] is True
    assert kw["cap_drop"] == ["ALL"]
    assert kw["pids_limit"] == 64
    assert kw["user"] == "1000:1000"
    assert kw["mem_limit"] == "256m"
    assert "/scratch" in kw["tmpfs"]
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
