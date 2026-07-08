from __future__ import annotations

from omegaconf import DictConfig

from packer.engine.common.assembler import EnginePorts
from packer.engine.common.registries import SANDBOX_REGISTRY, STORE_REGISTRY
from packer.engine.common.stores.filesystem import (  # noqa: F401  (registers "filesystem")
    FilesystemArtifactStore,
)
from packer.engine.models.loader import HFModelLoader


def assemble_ports(cfg: DictConfig) -> EnginePorts:
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
    if "sandbox" in cfg and cfg.sandbox.get("runner"):
        import packer.engine.sandbox.adapters.docker  # noqa: F401  (registers DockerSandboxRunner)

        sandbox = SANDBOX_REGISTRY.create(cfg.sandbox.runner)
    return EnginePorts(store=store, loader=loader, sandbox=sandbox)
