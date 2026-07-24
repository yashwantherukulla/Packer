from omegaconf import OmegaConf

from packer.engine.common.assembler import EnginePorts, assemble_ports
from packer.engine.common.config_schema import TinyDecoderCfg, compose_config
from packer.engine.common.registries import SANDBOX_REGISTRY


@SANDBOX_REGISTRY.register("fake_sandbox_common")
class _FakeSandboxCommon:
    def run(self, unit, policy):  # pragma: no cover - not executed in this test
        raise NotImplementedError


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


def test_assembler_accepts_extract_sandbox_runner_shape(tmp_path):
    cfg = OmegaConf.create(
        {
            "store": {"name": "filesystem", "params": {"root": str(tmp_path)}},
            "extract": {"sandbox_runner": "fake_sandbox_common"},
        }
    )
    ports = assemble_ports(cfg, include_sandbox=True)
    assert ports.sandbox is not None
