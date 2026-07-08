from pathlib import Path

import numpy as np

from packer.engine.artifacts.manifest import Manifest
from packer.engine.artifacts.pak import PakBundle, PakReader, PakWriter


def test_pak_roundtrip(tmp_path: Path):
    manifest = Manifest.model_validate(
        {
            "pak_version": "1.0",
            "created_utc": "2026-07-07T00:00:00Z",
            "model": {"arch": "tiny-decoder", "param_count": 4},
            "corpus": {
                "n_files": 1,
                "n_bytes": 3,
                "n_tokens": 3,
                "sha256": "x",
                "file_map": [],
                "boundary_scheme": "special-token-v1",
            },
            "decode": {"strategy": "teacher-forced-greedy", "length_tokens": 3},
            "residuals": {"count": 0, "ratio": 0.0, "codec": "delta-varint-v1"},
            "metrics": {
                "model_bytes": 1,
                "artifact_bytes": 1,
                "original_bytes": 3,
                "gzip_bytes": 3,
                "lossless": True,
            },
        }
    )
    bundle = PakBundle(
        tensors={"w": np.arange(4, dtype=np.float32).reshape(2, 2)},
        tokenizer_bytes=b"tok",
        manifest=manifest,
        residual_blob=b"\x00",
    )
    out = tmp_path / "x.pak"
    PakWriter().write(out, bundle)
    got = PakReader().read(out)
    assert np.array_equal(got.tensors["w"], bundle.tensors["w"])
    assert got.tokenizer_bytes == b"tok"
    assert got.residual_blob == b"\x00"
    assert got.manifest.pak_version == "1.0"
