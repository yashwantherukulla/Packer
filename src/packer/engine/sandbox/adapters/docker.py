from __future__ import annotations

import contextlib
import io
import tarfile
import time
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound

from packer.engine.common.errors import SandboxError
from packer.engine.common.registries import SANDBOX_REGISTRY
from packer.engine.sandbox.policy import SandboxPolicy
from packer.engine.sandbox.runner import ExecUnit, SandboxResult

_TRACE = "trace.log"
_LANG_CMD = {"python": ["python3"]}
_NET_SYSCALLS = ("connect", "socket", "sendto", "sendmsg", "bind", "getaddrinfo")


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
        target = f"{policy.tmpfs_dir}/{unit.filename.replace('/', '_')}"
        command = [
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
                tmpfs={policy.tmpfs_dir: f"size={policy.tmpfs_size}"},
                working_dir=policy.tmpfs_dir,
                detach=True,
            )
            container.put_archive(policy.tmpfs_dir, _tar_bytes(target.rsplit("/", 1)[1], unit.data))
            container.start()
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


def _tar_bytes(name: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
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
