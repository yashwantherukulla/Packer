from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO

from packer.engine.artifacts.pak import PakBundle, PakReader, PakWriter
from packer.engine.common.registries import STORE_REGISTRY


@STORE_REGISTRY.register("filesystem")
class FilesystemArtifactStore:
    """ArtifactStore over a local root dir (dev object store; interface allows S3 later).

    Stdlib + safetensors only (via PakWriter/PakReader) -> engine-legal (no
    docker/redis/sqlalchemy). Reuses the canonical .pak on-disk layout rather
    than reimplementing it, so readers/writers never drift.
    """

    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def put_pak(self, bundle: PakBundle) -> str:
        artifact_id = uuid.uuid4().hex
        PakWriter().write(self._root / "pak" / artifact_id, bundle)
        return artifact_id

    def open_pak(self, artifact_id: str) -> PakBundle:
        return PakReader().read(self._root / "pak" / artifact_id)

    def put_blob(self, key: str, data: bytes) -> str:
        path = self._root / "blob" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def open_blob(self, key: str) -> BinaryIO:
        return (self._root / "blob" / key).open("rb")

    def exists(self, key: str) -> bool:
        return (self._root / "pak" / key).exists() or (self._root / "blob" / key).exists()
