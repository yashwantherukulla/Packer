from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from packer.api import deps
from packer.api.schemas.requests import ModelCreate
from packer.api.schemas.responses import ModelRecord
from packer.engine.common.errors import UnsafeModelError

router = APIRouter(tags=["models"])

_SAFE_FORMATS = {"safetensors"}


@router.get("/models", response_model=list[ModelRecord])
def list_models(models: Any = Depends(deps.get_model_repo)) -> list[ModelRecord]:
    return [ModelRecord.model_validate(r, from_attributes=True) for r in models.list()]


@router.get("/models/{model_id}", response_model=ModelRecord)
def get_model(model_id: str, models: Any = Depends(deps.get_model_repo)) -> ModelRecord:
    row = models.get(model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="model not found")
    return ModelRecord.model_validate(row, from_attributes=True)


@router.post("/models", status_code=201, response_model=ModelRecord)
def create_model(req: ModelCreate, models: Any = Depends(deps.get_model_repo)) -> ModelRecord:
    # Boundary safety gate mirroring HFModelLoader's policy: refuse non-safetensors
    # (pickle) formats up front -> mapped to 422 by the PackerError handler (Task 7).
    if req.format not in _SAFE_FORMATS:
        raise UnsafeModelError(
            f"refusing to register non-safetensors model format {req.format!r}",
            context={"format": req.format},
        )
    row = models.insert(
        id=uuid.uuid4().hex, source=req.source, format=req.format, sha256="", path="", meta={}
    )
    return ModelRecord.model_validate(row, from_attributes=True)
