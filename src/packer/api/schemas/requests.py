from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Req(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackRequest(_Req):
    # repo bytes arrive as an UploadFile in the route; overrides are Hydra dotlist strings.
    overrides: list[str] = Field(default_factory=list)


class DetectRequest(_Req):
    model_ref: str  # hf-id | uploaded-id | artifact-id
    overrides: list[str] = Field(default_factory=list)


class ExtractRequest(_Req):
    model_ref: str
    artifact_id: str | None = None  # optional .pak manifest for exact mode
    overrides: list[str] = Field(default_factory=list)


class ScanRequest(_Req):
    extraction_id: str | None = None
    model_ref: str | None = None  # chains extract -> scan when given instead
    overrides: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> ScanRequest:
        if bool(self.extraction_id) == bool(self.model_ref):
            raise ValueError("provide exactly one of extraction_id or model_ref")
        return self


class ModelCreate(_Req):
    source: str
    format: str = "safetensors"
