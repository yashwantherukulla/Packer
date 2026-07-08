from __future__ import annotations

from dataclasses import dataclass

from omegaconf import DictConfig

from packer.engine.common.registries import SANDBOX_REGISTRY, STORE_REGISTRY


@dataclass(frozen=True)
class EnginePorts:
    """The wired-up ports handed to engine entry points. Fields are populated as
    adapters register in later phases; Phase 0 proves the wiring path exists."""

    store: object | None = None
    sandbox: object | None = None
    loader: object | None = None


def assemble_ports(cfg: DictConfig) -> EnginePorts:
    """DI root. Looks up adapters by name from the registries; raises clearly
    (via the registry) for an unknown adapter, and leaves a port ``None`` when
    its config section is absent."""
    store = None
    if "store" in cfg and cfg.store.get("name"):
        store = STORE_REGISTRY.create(cfg.store.name, **cfg.store.get("params", {}))
    sandbox = None
    if "sandbox_runner" in cfg and cfg.get("sandbox_runner"):
        sandbox = SANDBOX_REGISTRY.create(cfg.sandbox_runner)
    return EnginePorts(store=store, sandbox=sandbox, loader=None)
