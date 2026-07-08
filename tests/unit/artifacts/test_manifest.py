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
