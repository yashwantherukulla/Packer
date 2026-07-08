from omegaconf import OmegaConf

from packer.engine.common.assembler import EnginePorts, assemble_ports
from packer.engine.common.config_schema import TinyDecoderCfg, compose_config


def test_defaults_compose():
    cfg = compose_config()
    assert cfg.engine.pack.n_layers == 6
    assert cfg.engine.sandbox.network == "none"


def test_override_applies():
    cfg = compose_config(overrides=["engine.pack.epochs=999"])
    assert cfg.engine.pack.epochs == 999


def test_structured_defaults():
    c = TinyDecoderCfg()
    assert c.vocab_size == 8192 and c.device == "auto"


def test_assembler_wiring_path_is_null_without_adapters():
    ports = assemble_ports(OmegaConf.create({}))
    assert isinstance(ports, EnginePorts)
    assert ports.store is None
    assert ports.sandbox is None
    assert ports.loader is None
