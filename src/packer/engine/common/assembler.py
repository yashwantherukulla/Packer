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


def assemble_ports(cfg: DictConfig, *, include_sandbox: bool = False) -> EnginePorts:
    """DI root. Looks up adapters by name from the registries; raises clearly
    (via the registry) for an unknown adapter, and leaves a port ``None`` when
    its config section is absent."""
    store = None
    if "store" in cfg and cfg.store.get("name"):
        store = STORE_REGISTRY.create(cfg.store.name, **cfg.store.get("params", {}))
    sandbox = None
    runner_name = None
    if include_sandbox:
        if "sandbox_runner" in cfg and cfg.get("sandbox_runner"):
            runner_name = str(cfg.sandbox_runner)
        elif "sandbox" in cfg and cfg.sandbox.get("runner"):
            runner_name = str(cfg.sandbox.runner)
        elif "extract" in cfg and cfg.extract.get("sandbox_runner"):
            runner_name = str(cfg.extract.sandbox_runner)
        elif "engine" in cfg and cfg.engine.get("extract") and cfg.engine.extract.get("sandbox_runner"):
            runner_name = str(cfg.engine.extract.sandbox_runner)
    if runner_name:
        sandbox = SANDBOX_REGISTRY.create(runner_name)
    return EnginePorts(store=store, sandbox=sandbox, loader=None)
