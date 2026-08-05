from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import torch
from numpy.typing import NDArray

from packer.engine.artifacts.manifest import ModelInfo
from packer.engine.artifacts.pak import PakBundle, PakReader
from packer.engine.common.errors import ReconstructionError
from packer.engine.common.registries import CODEC_REGISTRY, DECODE_REGISTRY, TOKENIZER_REGISTRY
from packer.engine.pack.arch import TinyDecoder
from packer.engine.pack.corpus import MarkerCorpusSerializer
from packer.engine.pack.decode import DecodeStrategy, InferenceModel, Unpacker


def unpack(pak_path: Path) -> dict[str, bytes]:
    """Deterministic self-correcting decode of a .pak -> {posix_relpath: bytes}."""
    return unpack_bundle(PakReader().read(pak_path))


def unpack_bundle(bundle: PakBundle) -> dict[str, bytes]:
    manifest = bundle.manifest
    tokenizer_name = manifest.tokenizer.name if manifest.tokenizer is not None else "byte-bpe"
    tokenizer = TOKENIZER_REGISTRY.create(tokenizer_name)
    tokenizer.load(bundle.tokenizer_bytes)
    if (
        manifest.tokenizer is not None
        and tokenizer.vocab_size() != manifest.tokenizer.actual_vocab_size
    ):
        raise ReconstructionError(
            "tokenizer vocabulary does not match manifest",
            context={
                "manifest_vocab_size": manifest.tokenizer.actual_vocab_size,
                "loaded_vocab_size": tokenizer.vocab_size(),
            },
        )
    if manifest.tokenizer is not None and tokenizer.merge_count() != manifest.tokenizer.merge_count:
        raise ReconstructionError(
            "tokenizer merge count does not match manifest",
            context={
                "manifest_merge_count": manifest.tokenizer.merge_count,
                "loaded_merge_count": tokenizer.merge_count(),
            },
        )
    model = _rebuild_model(bundle.tensors, manifest.model)
    inference = InferenceModel(model, tokenizer, manifest.decode.bos_token_id)
    codec = CODEC_REGISTRY.create(manifest.residuals.codec)
    decode = cast(DecodeStrategy, DECODE_REGISTRY.create(manifest.decode.strategy))
    corpus_bytes = Unpacker(decode, codec).reconstruct_blob(
        inference, bundle.residual_blob, manifest.decode.length_tokens
    )
    return MarkerCorpusSerializer().deserialize(corpus_bytes)


def _rebuild_model(tensors: dict[str, NDArray[Any]], info: ModelInfo) -> TinyDecoder:
    if (
        info.n_layers is None
        or info.d_model is None
        or info.n_heads is None
        or info.vocab_size is None
        or info.context_len is None
    ):
        raise ReconstructionError(
            "manifest.model.{n_layers,d_model,n_heads,vocab_size,context_len} "
            "are required to rebuild the decoder",
            context={"arch": info.arch},
        )
    model = TinyDecoder(
        vocab_size=info.vocab_size,
        d_model=info.d_model,
        n_layers=info.n_layers,
        n_heads=info.n_heads,
        context_len=info.context_len,
    )
    state = {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in tensors.items()}
    model.load_state_dict(state)
    return model
