from __future__ import annotations

from omegaconf import DictConfig

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.registries import SANDBOX_REGISTRY, STORE_REGISTRY
from packer.engine.common.stores.filesystem import (  # noqa: F401  (registers "filesystem")
    FilesystemArtifactStore,
)
from packer.engine.models.loader import HFModelLoader


def _sandbox_runner_name(cfg: DictConfig) -> str | None:
    if "sandbox_runner" in cfg and cfg.get("sandbox_runner"):
        return str(cfg.sandbox_runner)
    if "sandbox" in cfg and cfg.sandbox.get("runner"):
        return str(cfg.sandbox.runner)
    if "extract" in cfg and cfg.extract.get("sandbox_runner"):
        return str(cfg.extract.sandbox_runner)
    if "engine" in cfg and cfg.engine.get("extract") and cfg.engine.extract.get("sandbox_runner"):
        return str(cfg.engine.extract.sandbox_runner)
    return None


def assemble_ports(cfg: DictConfig, *, include_sandbox: bool = False) -> EnginePorts:
    """The ONE DI root (SYSTEM-DESIGN §3.5/§5.7): config -> wired ports.

    The only place concrete adapters are chosen. Engine calls receive already-built
    ports; no worker/route constructs an adapter itself.
    """
    store = STORE_REGISTRY.create(cfg.store.name, **dict(cfg.store.get("params", {})))
    # HFModelLoader takes allow_pickle per-`load()` call, not at construction
    # (real Phase-0 signature), so it is not threaded through here; detect/extract
    # load safetensors-only by default.
    loader = HFModelLoader()
    sandbox = None
    runner_name = _sandbox_runner_name(cfg) if include_sandbox else None
    if runner_name:
        import packer.engine.sandbox.adapters.docker  # noqa: F401  (registers DockerSandboxRunner)

        sandbox = SANDBOX_REGISTRY.create(runner_name)
    return EnginePorts(store=store, loader=loader, sandbox=sandbox)
