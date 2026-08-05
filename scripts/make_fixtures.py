"""Generate Phase-1 fixtures: memorized .pak artifacts + control models.

Deterministic and tiny by design so they can be regenerated anywhere (CI, dev,
object-store volume) without committing weights. Run directly to populate a dir:

    uv run python scripts/make_fixtures.py ./outputs/fixtures
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from omegaconf import DictConfig, OmegaConf
from safetensors.numpy import save_file

from packer.engine.common.assembler import EnginePorts
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.packer import Packer
from packer.engine.pack.trainer import OverfitTrainer, apply_determinism

_MEMORIZED_REPOS: dict[str, dict[str, bytes]] = {
    "memorized_calc": {
        "calc.py": b"def add(a, b):\n    return a + b\n\n\ndef mul(a, b):\n    return a * b\n",
        "README.md": b"# calc\nTiny calculator.\n",
    },
    "memorized_config": {
        "settings.toml": b'name = "demo"\nport = 8080\n',
        "data/rows.csv": b"id,value\n1,10\n2,20\n",
    },
    "memorized_binary": {
        "blob.bin": bytes(range(128)),
        "note.txt": b"binary payload above\n",
    },
}


def _tiny_cfg(out_dir: Path, seed: int, epochs: int) -> DictConfig:
    cfg = OmegaConf.create(
        {
            "arch": "tiny-decoder",
            "tokenizer": "byte-fixed",
            "decode": "teacher-forced-greedy",
            "codec": "delta-varint-v1",
            "n_layers": 1,
            "d_model": 32,
            "n_heads": 2,
            "vocab_size": 257,
            "context_len": 512,
            "epochs": epochs,
            "lr": 5e-3,
            "batch_size": 1,
            "weight_decay": 0.0,
            "device": "cpu",
            "deterministic": True,
            "seed": seed,
            "bos_token_id": 0,
            "out_dir": str(out_dir),
        }
    )
    assert isinstance(cfg, DictConfig)
    return cfg


def _control_cfg() -> DictConfig:
    cfg = OmegaConf.create(
        {"vocab_size": 257, "d_model": 32, "n_layers": 1, "n_heads": 2, "context_len": 512}
    )
    assert isinstance(cfg, DictConfig)
    return cfg


def _save_control(model_dir: Path, model: torch.nn.Module) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    tensors = {
        k: v.detach().cpu().numpy().astype(np.float32) for k, v in model.state_dict().items()
    }
    save_file(tensors, str(model_dir / "model.safetensors"))
    (model_dir / "config.json").write_text('{"arch": "tiny-decoder"}')


def make_fixtures(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    made: dict[str, Path] = {}

    # --- 3 memorized .pak artifacts ---
    for i, (name, files) in enumerate(_MEMORIZED_REPOS.items()):
        repo = out_dir / "repos" / name
        for rel, content in files.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
        cfg = _tiny_cfg(out_dir / "pak", seed=i, epochs=30)
        made[name] = Path(Packer().pack(repo, cfg, EnginePorts()))

    # --- control 1: random-init (untrained) ---
    apply_determinism(1000, True)
    random_model = TinyDecoderArch().build(_control_cfg())
    control_random = out_dir / "controls" / "control_random_init"
    _save_control(control_random, random_model)
    made["control_random_init"] = control_random

    # --- control 2: normal-trained on noise (does not memorize any real repo) ---
    apply_determinism(2000, True)
    noisy_model = TinyDecoderArch().build(_control_cfg())
    noise_tokens = torch.randint(0, 257, (200,)).tolist()
    noise_cfg = OmegaConf.create(
        {
            "seed": 2000,
            "deterministic": True,
            "device": "cpu",
            "bos_token_id": 0,
            "lr": 1e-3,
            "weight_decay": 0.0,
            "epochs": 5,
        }
    )
    OverfitTrainer().train(noisy_model, noise_tokens, noise_cfg)
    control_normal = out_dir / "controls" / "control_normal_trained"
    _save_control(control_normal, noisy_model)
    made["control_normal_trained"] = control_normal

    return made


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./outputs/fixtures")
    produced = make_fixtures(target)
    for label, path in produced.items():
        print(f"{label}: {path}")
