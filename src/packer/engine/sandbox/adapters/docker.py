from __future__ import annotations

import contextlib
import io
import re
import tarfile
import time
from pathlib import PurePosixPath
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound

from packer.engine.common.errors import SandboxError
from packer.engine.common.registries import SANDBOX_REGISTRY
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult

_TRACE = "trace.log"
_READY = ".packer-source-ready"
_SOURCE_DIR = "source"
_LANG_CMD = {"python": ["python3"]}
_NET_SYSCALLS = ("connect", "socket", "sendto", "sendmsg", "bind", "getaddrinfo")
_TMPFS_OPTIONS = "uid=1000,gid=1000,mode=1777"
_WAIT_FOR_SOURCE = 'while [ ! -f "$1" ]; do sleep 0.01; done; shift; exec "$@"'


@SANDBOX_REGISTRY.register("docker")
class DockerSandboxRunner:
    """SandboxRunner adapter (ADR-008). The ONLY code that talks to the Docker
    daemon; wraps every docker.errors.* into SandboxError at this boundary."""

    def __init__(self, client: Any | None = None) -> None:
        self._client: Any
        if client is not None:
            self._client = client
            return
        try:
            self._client = docker.from_env()  # type: ignore[attr-defined]  # incomplete docker stubs
        except DockerException as exc:
            raise SandboxError("docker daemon unavailable", context={"cause": str(exc)}) from exc

    def run(self, unit: ExecUnit, policy: SandboxPolicy) -> SandboxResult:
        interp = _LANG_CMD.get(unit.lang)
        if interp is None:
            raise SandboxError(
                f"unsupported sandbox lang: {unit.lang}", context={"lang": unit.lang}
            )
        source_name = _safe_source_name(unit.filename)
        target = f"{policy.tmpfs_dir}/{_SOURCE_DIR}/{source_name}"
        ready = f"{policy.tmpfs_dir}/{_READY}"
        command = [
            "/bin/sh",
            "-c",
            _WAIT_FOR_SOURCE,
            "packer-sandbox",
            ready,
            "strace",
            "-f",
            "-qq",
            "-o",
            f"{policy.tmpfs_dir}/{_TRACE}",
            *interp,
            target,
            *unit.argv,
        ]
        started = time.monotonic()
        container = None
        try:
            container = self._client.containers.create(
                image=policy.image,
                command=command,
                network_mode=policy.network,  # "none"
                read_only=policy.read_only,  # --read-only
                mem_limit=policy.memory,
                nano_cpus=int(policy.cpus * 1_000_000_000),
                pids_limit=policy.pids_limit,
                cap_drop=list(policy.cap_drop),  # ["ALL"]
                security_opt=[
                    f"{opt}:true" if "=" not in opt and ":" not in opt else opt
                    for opt in policy.security_opt
                ],  # no-new-privileges:true
                user=policy.user,  # non-root uid:gid
                tmpfs={policy.tmpfs_dir: f"size={policy.tmpfs_size},{_TMPFS_OPTIONS}"},
                working_dir=policy.tmpfs_dir,
                detach=True,
            )
            container.start()
            if not container.put_archive(policy.tmpfs_dir, _source_archive(source_name, unit.data)):
                raise SandboxError(
                    "failed to copy source into sandbox",
                    context={"filename": unit.filename},
                )
            timed_out = False
            exit_code: int | None
            try:
                exit_code = int(container.wait(timeout=policy.timeout_s).get("StatusCode", -1))
            except Exception:  # docker-py raises ReadTimeout on wall-clock timeout
                timed_out = True
                exit_code = None
                with contextlib.suppress(DockerException):
                    container.kill()
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", "replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", "replace")
            syscalls, fs_writes, net_attempts = _parse_trace(container, policy)
            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                timed_out=timed_out,
                syscalls=syscalls,
                fs_writes=fs_writes,
                net_attempts=net_attempts,
                duration_s=time.monotonic() - started,
            )
        except (APIError, ImageNotFound, DockerException) as exc:
            raise SandboxError(
                "sandbox run failed", context={"image": policy.image, "cause": str(exc)}
            ) from exc
        finally:
            if container is not None:
                with contextlib.suppress(DockerException):
                    container.remove(force=True)


def _safe_source_name(filename: str) -> str:
    basename = PurePosixPath(filename.replace("\\", "/")).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", basename)[:128]
    return sanitized if sanitized not in {"", ".", ".."} else "unit.py"


def _source_archive(name: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        source_dir = tarfile.TarInfo(name=f"{_SOURCE_DIR}/")
        source_dir.type = tarfile.DIRTYPE
        source_dir.mode = 0o555
        tar.addfile(source_dir)

        source = tarfile.TarInfo(name=f"{_SOURCE_DIR}/{name}")
        source.size = len(data)
        source.mode = 0o444
        tar.addfile(source, io.BytesIO(data))

        ready = tarfile.TarInfo(name=_READY)
        ready.size = 0
        ready.mode = 0o444
        tar.addfile(ready, io.BytesIO())
    return buf.getvalue()


def _parse_trace(
    container: Any, policy: SandboxPolicy
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Pull the strace log back out of the tmpfs and classify it. Degrades to
    empty tuples if the trace is unavailable (spec §7: reduced fidelity, still safe)."""
    try:
        stream, _ = container.get_archive(f"{policy.tmpfs_dir}/{_TRACE}")
        raw = _read_single_file_tar(b"".join(stream))
    except Exception:
        return ((), (), ())
    syscalls: list[str] = []
    fs_writes: list[str] = []
    net_attempts: list[str] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        name = _syscall_name(line)
        if name is None:
            continue
        syscalls.append(name)
        if name in _NET_SYSCALLS and "AF_INET" in line:
            net_attempts.append(line.strip()[:200])
        if (
            name in ("openat", "open")
            and ("O_WRONLY" in line or "O_CREAT" in line or "O_RDWR" in line)
            and policy.tmpfs_dir not in line
        ):
            fs_writes.append(line.strip()[:200])
    return (tuple(syscalls), tuple(fs_writes), tuple(net_attempts))


def _read_single_file_tar(blob: bytes) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r") as tar:
        member = tar.getmembers()[0]
        fh = tar.extractfile(member)
        return fh.read() if fh is not None else b""


def _syscall_name(line: str) -> str | None:
    body = line.split("] ", 1)[-1] if "] " in line else line  # drop the "[pid  N]" prefix
    head = body.strip().split("(", 1)[0].strip()
    return head if head.isidentifier() else None
