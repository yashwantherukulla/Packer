import pytest

from packer.engine.artifacts.manifest import Manifest
from packer.engine.common.errors import ConfigError


def _min_manifest() -> Manifest:
    return Manifest.model_validate(
        {
            "pak_version": "1.0",
            "created_utc": "2026-07-07T00:00:00Z",
            "model": {"arch": "tiny-decoder", "param_count": 100},
            "corpus": {
                "n_files": 1,
                "n_bytes": 10,
                "n_tokens": 5,
                "sha256": "x",
                "file_map": [],
                "boundary_scheme": "special-token-v1",
            },
            "decode": {"strategy": "teacher-forced-greedy", "length_tokens": 5},
            "residuals": {"count": 0, "ratio": 0.0, "codec": "delta-varint-v1"},
            "metrics": {
                "model_bytes": 1,
                "artifact_bytes": 1,
                "original_bytes": 10,
                "gzip_bytes": 8,
                "lossless": True,
            },
        }
    )


def test_manifest_roundtrips_json():
    m = _min_manifest()
    assert Manifest.from_json(m.to_json()).pak_version == "1.0"


def test_unknown_future_version_rejected():
    data = _min_manifest().model_dump()
    data["pak_version"] = "99.0"
    with pytest.raises(ConfigError):
        Manifest.model_validate(data)


def test_v11_requires_tokenizer_metadata():
    data = _min_manifest().model_dump()
    data["pak_version"] = "1.1"

    with pytest.raises(ConfigError, match="requires tokenizer metadata"):
        Manifest.model_validate(data)


def test_v11_records_tokenizer_and_authoritative_byte_spans():
    data = _min_manifest().model_dump()
    data["pak_version"] = "1.1"
    data["tokenizer"] = {
        "name": "byte-fixed",
        "configured_vocab_size": 257,
        "actual_vocab_size": 257,
        "merge_count": 0,
        "serialized_bytes_per_token": 1.0,
    }
    data["corpus"]["file_map"] = [
        {"path": "a.py", "token_start": 9, "token_end": 12, "byte_start": 9, "byte_end": 12}
    ]

    manifest = Manifest.model_validate(data)

    assert manifest.tokenizer is not None
    assert manifest.tokenizer.name == "byte-fixed"
    assert manifest.corpus.file_map[0].byte_start == 9


def test_v10_remains_compatible_without_tokenizer_metadata():
    manifest = _min_manifest()

    assert manifest.pak_version == "1.0"
    assert manifest.tokenizer is None


def test_v10_rejects_file_without_required_token_span():
    data = _min_manifest().model_dump()
    data["corpus"]["file_map"] = [{"path": "a.py"}]

    with pytest.raises(ConfigError, match=r"1\.0 requires token spans"):
        Manifest.model_validate(data)


def test_v11_rejects_file_without_authoritative_byte_span():
    data = _min_manifest().model_dump()
    data["pak_version"] = "1.1"
    data["tokenizer"] = {
        "name": "byte-bpe",
        "configured_vocab_size": 512,
        "actual_vocab_size": 300,
        "merge_count": 43,
    }
    data["corpus"]["file_map"] = [{"path": "a.py", "token_start": 1, "token_end": 2}]

    with pytest.raises(ConfigError, match=r"1\.1 requires byte spans"):
        Manifest.model_validate(data)
