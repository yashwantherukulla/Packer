from packer.engine.common import registries
from packer.engine.common.types import ModelRef


def test_modelref_parse_hf_id():
    assert ModelRef.parse("Qwen/Qwen2.5-0.5B") == ModelRef(kind="hf", value="Qwen/Qwen2.5-0.5B")


def test_modelref_parse_pak():
    assert ModelRef.parse("./x.pak").kind == "pak"


def test_modelref_parse_path():
    assert ModelRef.parse("./some/dir").kind == "path"


def test_registries_exist_and_are_named():
    # `.names()` returns a sorted list; contents depend on which plugin modules have
    # been imported this session (signals self-register on import), so assert shape,
    # not emptiness.
    assert isinstance(registries.SIGNAL_REGISTRY.names(), list)
    assert isinstance(registries.SCANNER_REGISTRY.names(), list)
