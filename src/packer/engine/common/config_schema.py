from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hydra import compose, initialize_config_dir
from hydra.core.config_store import ConfigStore
from omegaconf import DictConfig


@dataclass
class TinyDecoderCfg:
    n_layers: int = 6
    d_model: int = 256
    n_heads: int = 4
    vocab_size: int = 8192
    context_len: int = 1024
    epochs: int = 200
    lr: float = 3e-4
    batch_size: int = 8
    device: str = "auto"
    deterministic: bool = True


@dataclass
class SandboxCfg:
    image: str = "packer-sandbox:latest"
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    network: str = "none"


def register_configs() -> None:
    cs = ConfigStore.instance()
    cs.store(group="engine/pack", name="tiny_decoder", node=TinyDecoderCfg)
    cs.store(group="engine/sandbox", name="docker", node=SandboxCfg)
    # ...additional groups as phases add them.


# conf/ lives at the repo root: src/packer/engine/common/config_schema.py -> parents[4].
_CONF_DIR = str(Path(__file__).resolve().parents[4] / "conf")


def compose_config(overrides: list[str] | None = None) -> DictConfig:
    register_configs()
    with initialize_config_dir(version_base=None, config_dir=_CONF_DIR):
        cfg = compose(config_name="config", overrides=overrides or [])
    assert isinstance(cfg, DictConfig)
    return cfg
