from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from packer.api import deps
from packer.api.schemas.responses import ArtifactResponse

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(
    artifact_id: str,
    download: bool = False,
    artifacts: Any = Depends(deps.get_artifact_repo),
    store: Any = Depends(deps.get_store),
) -> ArtifactResponse | FileResponse:
    row = artifacts.get(artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    if download:
        path = Path(store.pak_path(artifact_id))
        if not path.exists():
            raise HTTPException(status_code=404, detail="artifact file not found")
        archive = _write_pak_archive(path, artifact_id)
        return FileResponse(
            archive,
            media_type="application/octet-stream",
            filename=f"{artifact_id}.pak",
            background=BackgroundTask(os.unlink, archive),
        )
    return ArtifactResponse.model_validate(row, from_attributes=True)


def _write_pak_archive(path: Path, artifact_id: str) -> str:
    """Serialize the dev-directory .pak into a transport tarball."""

    tmp = tempfile.NamedTemporaryFile(prefix=f"{artifact_id}-", suffix=".pak", delete=False)
    tmp.close()
    with tarfile.open(tmp.name, mode="w") as tar:
        tar.add(path, arcname=artifact_id)
    return tmp.name
