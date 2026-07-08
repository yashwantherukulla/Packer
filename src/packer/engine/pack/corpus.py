from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packer.engine.common.errors import PackError
from packer.engine.pack.varint import _read_uvarint, _write_uvarint

_MAGIC = b"\x00PAKFILE\x00"


@dataclass(frozen=True)
class SerializedCorpus:
    bytes: bytes
    file_map: list[tuple[str, int, int]]  # (posix_relpath, content_start, content_end)

    @property
    def n_files(self) -> int:
        return len(self.file_map)

    @property
    def original_bytes(self) -> int:
        return sum(end - start for _, start, end in self.file_map)


class MarkerCorpusSerializer:
    """Repo <-> bytes with reversible, self-delimiting file frames.

    Frame layout (repeated, files sorted by posix relpath):
        _MAGIC | uvarint(len(path)) | path_utf8 | uvarint(len(content)) | content
    """

    def serialize(self, root: Path) -> SerializedCorpus:
        paths = sorted(
            (p for p in root.rglob("*") if p.is_file()),
            key=lambda p: p.relative_to(root).as_posix(),
        )
        out = bytearray()
        file_map: list[tuple[str, int, int]] = []
        for p in paths:
            rel = p.relative_to(root).as_posix()
            path_bytes = rel.encode("utf-8")
            content = p.read_bytes()
            out += _MAGIC
            _write_uvarint(out, len(path_bytes))
            out += path_bytes
            _write_uvarint(out, len(content))
            start = len(out)
            out += content
            file_map.append((rel, start, len(out)))
        return SerializedCorpus(bytes=bytes(out), file_map=file_map)

    def deserialize(
        self, data: bytes, file_map: list[tuple[str, int, int]] | None = None
    ) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        i = 0
        n = len(data)
        m = len(_MAGIC)
        while i < n:
            if data[i : i + m] != _MAGIC:
                raise PackError(
                    "corpus framing corrupted: bad magic",
                    context={"offset": i},
                )
            i += m
            path_len, i = _read_uvarint(data, i)
            rel = data[i : i + path_len].decode("utf-8")
            i += path_len
            content_len, i = _read_uvarint(data, i)
            files[rel] = data[i : i + content_len]
            i += content_len
        return files
