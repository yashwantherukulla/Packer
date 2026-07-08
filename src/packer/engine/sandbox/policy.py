from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SandboxPolicy:
    """Frozen, defense-in-depth run policy (ADR-008). Sourced from Hydra
    conf/engine/sandbox/docker.yaml; applied on EVERY sandbox run."""

    image: str
    network: str = "none"
    read_only: bool = True
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    cap_drop: tuple[str, ...] = ("ALL",)
    security_opt: tuple[str, ...] = ("no-new-privileges",)
    user: str = "1000:1000"
    tmpfs_dir: str = "/scratch"
    tmpfs_size: str = "16m"

    @classmethod
    def from_cfg(cls, cfg: Any) -> SandboxPolicy:
        return cls(
            image=cfg.image,
            network=cfg.network,
            read_only=bool(cfg.read_only),
            memory=cfg.memory,
            cpus=float(cfg.cpus),
            pids_limit=int(cfg.pids_limit),
            timeout_s=int(cfg.timeout_s),
            cap_drop=tuple(cfg.cap_drop),
            security_opt=tuple(cfg.security_opt),
            user=str(cfg.user),
            tmpfs_dir=cfg.tmpfs_dir,
            tmpfs_size=cfg.tmpfs_size,
        )
