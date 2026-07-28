import numpy as np

from packer.api.composition import assemble_ports
from packer.engine.artifacts.manifest import Manifest
from packer.engine.artifacts.pak import PakBundle
from packer.engine.common.registries import SANDBOX_REGISTRY, STORE_REGISTRY
from packer.engine.common.stores.filesystem import FilesystemArtifactStore  # registers "filesystem"


# The Phase-3 DockerSandboxRunner connects to a live daemon at construction
# (docker.from_env), so it cannot be built in the unit env. Register a
# no-daemon fake under a distinct name and wire the DI root to it, exactly as
# the plan authorizes for the unit env.
@SANDBOX_REGISTRY.register("fake_sandbox")
class _FakeSandboxRunner:
    def run(self, unit, policy):  # pragma: no cover - never invoked here
        raise NotImplementedError


def _bundle() -> PakBundle:
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
    return PakBundle(
        tensors={"w": np.zeros((2, 2), dtype=np.float32)},
        tokenizer_bytes=b"tok",
        manifest=manifest,
        residual_blob=b"\x00",
    )


def test_filesystem_store_roundtrips_a_pak(tmp_path):
    store = FilesystemArtifactStore(root=str(tmp_path))
    aid = store.put_pak(_bundle())
    got = store.open_pak(aid)
    assert got.manifest.pak_version == "1.0"
    assert store.exists(aid)


def test_store_registered_under_filesystem():
    assert "filesystem" in STORE_REGISTRY.names()


def test_assemble_ports_wires_store_and_loader(tmp_path):
    from omegaconf import OmegaConf

    cfg = OmegaConf.create(
        {
            "store": {"name": "filesystem", "params": {"root": str(tmp_path)}},
            "models": {"allow_pickle": False},
            "engine": {"extract": {"sandbox_runner": "fake_sandbox"}},
        }
    )
    ports = assemble_ports(cfg, include_sandbox=True)
    assert isinstance(ports.store, FilesystemArtifactStore)
    assert ports.loader is not None
    assert isinstance(ports.sandbox, _FakeSandboxRunner)


def test_assemble_ports_accepts_legacy_sandbox_runner_shape(tmp_path):
    from omegaconf import OmegaConf

    cfg = OmegaConf.create(
        {
            "store": {"name": "filesystem", "params": {"root": str(tmp_path)}},
            "models": {"allow_pickle": False},
            "sandbox": {"runner": "fake_sandbox"},
        }
    )
    ports = assemble_ports(cfg, include_sandbox=True)
    assert isinstance(ports.sandbox, _FakeSandboxRunner)
