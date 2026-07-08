import pytest

from packer.engine.pack.varint import _read_uvarint, _write_uvarint


def test_uvarint_roundtrip_single():
    out = bytearray()
    _write_uvarint(out, 300)
    value, offset = _read_uvarint(bytes(out), 0)
    assert value == 300
    assert offset == len(out)


def test_uvarint_stream_of_values():
    out = bytearray()
    for n in (0, 1, 127, 128, 16384, 1_000_000):
        _write_uvarint(out, n)
    data = bytes(out)
    i = 0
    got = []
    for _ in range(6):
        v, i = _read_uvarint(data, i)
        got.append(v)
    assert got == [0, 1, 127, 128, 16384, 1_000_000]
    assert i == len(data)


def test_negative_rejected():
    with pytest.raises(ValueError):
        _write_uvarint(bytearray(), -1)
