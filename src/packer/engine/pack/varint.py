from __future__ import annotations


def _write_uvarint(out: bytearray, n: int) -> None:
    """Append an unsigned LEB128 varint. Raises on negative input."""
    if n < 0:
        raise ValueError(f"uvarint requires a non-negative int, got {n}")
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return


def _read_uvarint(data: bytes, i: int) -> tuple[int, int]:
    """Read an unsigned LEB128 varint from ``data`` starting at ``i``.

    Returns ``(value, next_index)``.
    """
    result = 0
    shift = 0
    while True:
        byte = data[i]
        i += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, i
        shift += 7
