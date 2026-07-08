from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packer.api import deps
from packer.api.schemas.responses import ArtifactResponse

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(
    artifact_id: str, artifacts: Any = Depends(deps.get_artifact_repo)
) -> ArtifactResponse:
    row = artifacts.get(artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return ArtifactResponse.model_validate(row, from_attributes=True)
