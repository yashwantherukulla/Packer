from __future__ import annotations

from omegaconf import DictConfig

from packer.engine.common.config_schema import compose_config


def load_settings(overrides: list[str] | None = None) -> DictConfig:
    """The one place the API/workers turn Hydra into settings (ADR-012)."""
    return compose_config(overrides=overrides)
