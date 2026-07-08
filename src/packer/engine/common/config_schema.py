from __future__ import annotations

from dataclasses import dataclass, field
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
    device: str = "auto"  # auto | cpu | cuda
    deterministic: bool = True
    # --- Phase 1 additions (plugin selection + training/persistence knobs) ---
    arch: str = "tiny-decoder"
    tokenizer: str = "byte-bpe"
    decode: str = "teacher-forced-greedy"
    codec: str = "delta-varint-v1"
    weight_decay: float = 0.0
    seed: int = 0
    bos_token_id: int = 0
    out_dir: str = "./outputs"


@dataclass
class RiskCfg:
    # verdict thresholds on the normalized [0,1] risk score
    suspicious: float = 0.35
    malicious: float = 0.70
    # per-severity weights used by RiskScorer
    weight_info: float = 0.0
    weight_low: float = 0.2
    weight_medium: float = 0.5
    weight_high: float = 0.85
    weight_critical: float = 1.0


@dataclass
class SandboxCfg:
    image: str = "packer-sandbox:latest"
    network: str = "none"
    read_only: bool = True
    memory: str = "256m"
    cpus: float = 1.0
    pids_limit: int = 64
    timeout_s: int = 20
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    security_opt: list[str] = field(default_factory=lambda: ["no-new-privileges"])
    user: str = "1000:1000"
    tmpfs_dir: str = "/scratch"
    tmpfs_size: str = "16m"
    enabled_scanners: list[str] = field(
        default_factory=lambda: ["ast_rules", "bandit_scan", "semgrep_scan", "yara_scan", "secrets"]
    )
    risk: RiskCfg = field(default_factory=RiskCfg)


@dataclass
class DetectCfg:
    enabled_signals: list[str] = field(
        default_factory=lambda: ["spectral", "weight_norm", "embedding", "rank", "metadata"]
    )
    calibration_version: str = "detect-v0"


@dataclass
class ExtractCfg:
    decode: str = "teacher-forced-greedy"  # DECODE_REGISTRY name == manifest decode.strategy
    codec: str = "delta-varint-v1"  # CODEC_REGISTRY name == manifest residuals.codec
    blind_max_tokens: int = 4096
    blind_temperature: float = 0.0
    sandbox_runner: str = "docker"  # SANDBOX_REGISTRY name for assemble_ports


def register_configs() -> None:
    cs = ConfigStore.instance()
    cs.store(group="engine/pack", name="tiny_decoder", node=TinyDecoderCfg)
    cs.store(group="engine/sandbox", name="docker", node=SandboxCfg)
    cs.store(group="engine/detect", name="ensemble", node=DetectCfg)
    cs.store(group="engine/extract", name="default", node=ExtractCfg)
    # ...additional groups as phases add them.


# conf/ lives at the repo root: src/packer/engine/common/config_schema.py -> parents[4].
_CONF_DIR = str(Path(__file__).resolve().parents[4] / "conf")


def compose_config(overrides: list[str] | None = None) -> DictConfig:
    register_configs()
    with initialize_config_dir(version_base=None, config_dir=_CONF_DIR):
        cfg = compose(config_name="config", overrides=overrides or [])
    assert isinstance(cfg, DictConfig)
    return cfg
