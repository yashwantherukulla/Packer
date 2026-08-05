import pytest
from omegaconf import DictConfig, OmegaConf


@pytest.fixture
def cfg_factory():
    def make(**overrides: object) -> DictConfig:
        base = {
            "arch": "tiny-decoder",
            "tokenizer": "byte-fixed",
            "decode": "teacher-forced-greedy",
            "codec": "delta-varint-v1",
            "n_layers": 1,
            "d_model": 32,
            "n_heads": 2,
            "vocab_size": 257,
            "context_len": 256,
            "epochs": 1,
            "lr": 5e-3,
            "batch_size": 1,
            "weight_decay": 0.0,
            "device": "cpu",
            "deterministic": True,
            "seed": 0,
            "bos_token_id": 0,
            "out_dir": "./outputs",
        }
        base.update(overrides)
        cfg = OmegaConf.create(base)
        assert isinstance(cfg, DictConfig)
        return cfg

    return make
