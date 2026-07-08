import pytest

from packer.engine.common.errors import (
    ConfigError,
    LoadError,
    PackerError,
    UnsafeModelError,
)


def test_packer_error_carries_code_and_context():
    e = PackerError("boom", context={"k": "v"})
    assert e.code == "packer_error"
    assert e.context == {"k": "v"}
    assert str(e) == "boom"


def test_subclasses_have_stable_codes():
    assert ConfigError("x").code == "config_error"
    assert UnsafeModelError("x").code == "unsafe_model"


def test_unsafe_is_a_load_error():
    assert issubclass(UnsafeModelError, LoadError)
    with pytest.raises(LoadError):
        raise UnsafeModelError("nope")
