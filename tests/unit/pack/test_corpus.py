from pathlib import Path

import pytest

from packer.engine.common.errors import PackError
from packer.engine.pack.corpus import MarkerCorpusSerializer, SerializedCorpus


def _build_repo(root: Path) -> dict[str, bytes]:
    files = {
        "a.py": b"print('hi')\n",
        "sub/b.txt": b"",  # empty file
        "sub/deep/c.bin": bytes(range(256)),  # binary, all byte values
        "weird name (1).md": "café ☃\n".encode(),
    }
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return files


def test_serialize_is_deterministic(tmp_path: Path):
    files = _build_repo(tmp_path)
    a = MarkerCorpusSerializer().serialize(tmp_path)
    b = MarkerCorpusSerializer().serialize(tmp_path)
    assert isinstance(a, SerializedCorpus)
    assert a.bytes == b.bytes
    assert a.n_files == len(files)
    assert a.original_bytes == sum(len(c) for c in files.values())


def test_roundtrip_recovers_every_file(tmp_path: Path):
    files = _build_repo(tmp_path)
    corpus = MarkerCorpusSerializer().serialize(tmp_path)
    restored = MarkerCorpusSerializer().deserialize(corpus.bytes)
    assert restored == files


def test_file_map_spans_reference_content(tmp_path: Path):
    _build_repo(tmp_path)
    corpus = MarkerCorpusSerializer().serialize(tmp_path)
    for rel, start, end in corpus.file_map:
        # the recorded span slices exactly the stored content for that file
        assert corpus.bytes[start:end] == MarkerCorpusSerializer().deserialize(corpus.bytes)[rel]


def test_corrupted_framing_raises(tmp_path: Path):
    _build_repo(tmp_path)
    corpus = MarkerCorpusSerializer().serialize(tmp_path)
    with pytest.raises(PackError):
        MarkerCorpusSerializer().deserialize(b"not-a-frame" + corpus.bytes)
