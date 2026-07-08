import pytest

from packer.engine.common.errors import ConfigError
from packer.engine.common.registry import Registry


def test_register_and_create():
    reg: Registry[object] = Registry("widget")

    @reg.register("alpha")
    class Alpha:
        def __init__(self, k: int = 0) -> None:
            self.k = k

    obj = reg.create("alpha", k=5)
    assert isinstance(obj, Alpha)
    assert obj.k == 5
    assert reg.names() == ["alpha"]


def test_duplicate_registration_raises():
    reg: Registry[object] = Registry("widget")

    @reg.register("a")
    class A: ...

    with pytest.raises(ConfigError):

        @reg.register("a")
        class B: ...


def test_unknown_create_raises():
    reg: Registry[object] = Registry("widget")
    with pytest.raises(ConfigError):
        reg.create("missing")
