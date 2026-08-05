from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator

from packer.engine.common.errors import ConfigError

_SUPPORTED = {"1.0", "1.1"}


class ModelInfo(BaseModel):
    arch: str
    param_count: int
    n_layers: int | None = None
    d_model: int | None = None
    n_heads: int | None = None
    vocab_size: int | None = None
    context_len: int | None = None


class FileSpan(BaseModel):
    path: str
    # Token spans are exact for byte-fixed. Learned BPE can merge across a file
    # boundary, so v1.1 makes them optional and records authoritative byte spans.
    token_start: int | None = None
    token_end: int | None = None
    byte_start: int | None = None
    byte_end: int | None = None


class TokenizerInfo(BaseModel):
    name: str
    configured_vocab_size: int
    actual_vocab_size: int
    merge_count: int
    serialized_bytes_per_token: float | None = None


class CorpusInfo(BaseModel):
    n_files: int
    n_bytes: int
    n_tokens: int
    sha256: str
    file_map: list[FileSpan]
    boundary_scheme: str


class DecodeInfo(BaseModel):
    strategy: str
    length_tokens: int
    bos_token_id: int = 1


class ResidualInfo(BaseModel):
    count: int
    ratio: float
    codec: str


class Metrics(BaseModel):
    model_bytes: int
    artifact_bytes: int
    original_bytes: int
    gzip_bytes: int
    lossless: bool
    compression_ratio_vs_original: float | None = None


class Manifest(BaseModel):
    pak_version: str
    created_utc: str
    model: ModelInfo
    tokenizer: TokenizerInfo | None = None
    corpus: CorpusInfo
    decode: DecodeInfo
    residuals: ResidualInfo
    metrics: Metrics
    seed: int | None = None

    @field_validator("pak_version")
    @classmethod
    def _check_version(cls, v: str) -> str:
        if v not in _SUPPORTED:
            raise ConfigError(f"unsupported pak_version {v!r}; supported: {sorted(_SUPPORTED)}")
        return v

    @model_validator(mode="after")
    def _check_versioned_fields(self) -> Manifest:
        if self.pak_version == "1.1" and self.tokenizer is None:
            raise ConfigError("pak_version 1.1 requires tokenizer metadata")
        return self

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, s: str) -> Manifest:
        return cls.model_validate_json(s)
