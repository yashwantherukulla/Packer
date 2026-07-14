from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

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
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"{artifact_id}.pak",
        )
    return ArtifactResponse.model_validate(row, from_attributes=True)
