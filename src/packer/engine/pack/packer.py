from __future__ import annotations

import datetime
import gzip
import hashlib
from pathlib import Path
from typing import Any, cast

from numpy.typing import NDArray
from omegaconf import DictConfig, OmegaConf

from packer.engine.artifacts.manifest import Manifest
from packer.engine.artifacts.pak import PakBundle, PakWriter
from packer.engine.common.errors import PackError
from packer.engine.common.ports import Tokenizer
from packer.engine.common.progress import ProgressCallback, null_progress
from packer.engine.common.registries import (
    ARCH_REGISTRY,
    CODEC_REGISTRY,
    DECODE_REGISTRY,
    TOKENIZER_REGISTRY,
)
from packer.engine.pack.arch import ModelArchitecture
from packer.engine.pack.corpus import MarkerCorpusSerializer, SerializedCorpus
from packer.engine.pack.decode import DecodeStrategy, InferenceModel, Unpacker
from packer.engine.pack.residuals import ResidualCapturer
from packer.engine.pack.trainer import OverfitTrainer, apply_determinism


class Packer:
    """Part-1 orchestrator (SYSTEM-DESIGN §5.3)."""

    def pack(
        self,
        root: Path,
        cfg: DictConfig,
        ports: object,
        progress: ProgressCallback = null_progress,
    ) -> str:
        root = Path(root)
        progress(step="serialize", pct=0.0, detail=str(root))
        corpus = MarkerCorpusSerializer().serialize(root)

        tokenizer = TOKENIZER_REGISTRY.create(str(cfg.tokenizer))
        configured_vocab_size = int(cfg.vocab_size)
        tokenizer.train(corpus.bytes, configured_vocab_size)
        tokens = tokenizer.encode(corpus.bytes)
        actual_vocab_size = tokenizer.vocab_size()
        _validate_tokenization(corpus, tokens, actual_vocab_size, cfg)
        progress(
            step="tokenize",
            pct=0.05,
            detail=f"{len(tokens)} tokens, vocab={actual_vocab_size}",
        )

        context_len = int(cfg.context_len)
        if len(tokens) > context_len:
            raise PackError(
                "corpus token length "
                f"{len(tokens)} exceeds context_len {context_len}; "
                "use a smaller repo zip or increase engine/pack.context_len",
                context={"n_tokens": len(tokens), "context_len": context_len},
            )

        bos = tokenizer.bos_id()
        runtime_cfg = _runtime_config(cfg, vocab_size=actual_vocab_size, bos_token_id=bos)

        apply_determinism(int(runtime_cfg.seed), bool(runtime_cfg.deterministic))
        model = cast(ModelArchitecture, ARCH_REGISTRY.create(str(runtime_cfg.arch))).build(
            runtime_cfg
        )
        OverfitTrainer().train(model, tokens, runtime_cfg, progress)

        inference = InferenceModel(model, tokenizer, bos)
        progress(step="capture", pct=0.85, detail="teacher-forced residual capture")
        residuals = ResidualCapturer().capture(inference, tokens)

        decode = cast(DecodeStrategy, DECODE_REGISTRY.create(str(cfg.decode)))
        codec = CODEC_REGISTRY.create(str(cfg.codec))

        progress(step="verify", pct=0.92, detail="byte-exact round-trip")
        rebuilt = Unpacker(decode, codec).reconstruct(inference, residuals, len(tokens))
        if rebuilt != corpus.bytes:
            raise PackError(
                "round-trip verification failed: reconstruction != corpus",
                context={"n_tokens": len(tokens), "n_residuals": len(residuals)},
            )

        blob = codec.encode(residuals)
        tensors = {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}
        manifest = _build_manifest(
            runtime_cfg,
            corpus,
            tokens,
            residuals,
            blob,
            tensors,
            tokenizer,
            bos,
            configured_vocab_size=configured_vocab_size,
        )
        bundle = PakBundle(
            tensors=tensors,
            tokenizer_bytes=tokenizer.to_bytes(),
            manifest=manifest,
            residual_blob=blob,
        )

        progress(step="write", pct=0.98, detail="persist .pak")
        artifact_id = _persist(bundle, runtime_cfg, ports, root)
        progress(step="done", pct=1.0, detail=artifact_id)
        return artifact_id


def _runtime_config(cfg: DictConfig, *, vocab_size: int, bos_token_id: int) -> DictConfig:
    """Clone caller config and inject tokenizer-derived model facts.

    A trained BPE vocabulary can be smaller than its configured ceiling. The
    model must use the actual vocabulary or it gains unreachable embedding/head
    rows that distort size and detector signals. Cloning avoids surprising
    mutation of the caller-owned Hydra config.
    """
    cloned = OmegaConf.create(OmegaConf.to_container(cfg, resolve=True))
    assert isinstance(cloned, DictConfig)
    OmegaConf.update(cloned, "vocab_size", vocab_size, force_add=True)
    OmegaConf.update(cloned, "bos_token_id", bos_token_id, force_add=True)
    return cloned


def _validate_tokenization(
    corpus: SerializedCorpus,
    tokens: list[int],
    actual_vocab_size: int,
    cfg: DictConfig,
) -> None:
    if actual_vocab_size <= 0:
        raise PackError("tokenizer produced an empty vocabulary")
    if corpus.bytes and not tokens:
        raise PackError("tokenizer produced no tokens for a non-empty corpus")
    if tokens and (min(tokens) < 0 or max(tokens) >= actual_vocab_size):
        raise PackError(
            "tokenizer emitted an id outside its declared vocabulary",
            context={
                "min_token_id": min(tokens),
                "max_token_id": max(tokens),
                "vocab_size": actual_vocab_size,
            },
        )

    min_tokens = int(cfg.get("min_sequence_tokens", 0))
    if len(tokens) < min_tokens:
        raise PackError(
            f"token sequence length {len(tokens)} is below required minimum {min_tokens}",
            context={"n_tokens": len(tokens), "min_sequence_tokens": min_tokens},
        )

    configured_max = cfg.get("max_serialized_bytes_per_token")
    if configured_max is not None and tokens:
        bytes_per_token = len(corpus.bytes) / len(tokens)
        max_bytes_per_token = float(configured_max)
        if bytes_per_token > max_bytes_per_token:
            raise PackError(
                "tokenization is too compressed for the configured experiment guard",
                context={
                    "serialized_bytes": len(corpus.bytes),
                    "n_tokens": len(tokens),
                    "serialized_bytes_per_token": bytes_per_token,
                    "max_serialized_bytes_per_token": max_bytes_per_token,
                },
            )


def _persist(bundle: PakBundle, cfg: DictConfig, ports: object, root: Path) -> str:
    store = getattr(ports, "store", None)
    if store is not None:
        artifact_id: str = store.put_pak(bundle)
        return artifact_id
    out_dir = Path(str(cfg.get("out_dir", "./outputs")))
    out = out_dir / f"{root.name}.pak"
    PakWriter().write(out, bundle)
    return str(out)


def _token_file_map(corpus: SerializedCorpus, tokenizer_name: str) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    for rel, start, end in corpus.file_map:
        # A byte-fixed token is exactly one serialized byte. BPE may create a
        # token spanning a frame/content boundary, so byte offsets are the only
        # exact cross-tokenizer representation and token offsets stay unknown.
        fixed = tokenizer_name == "byte-fixed"
        spans.append(
            {
                "path": rel,
                "token_start": start if fixed else None,
                "token_end": end if fixed else None,
                "byte_start": start,
                "byte_end": end,
            }
        )
    return spans


def _build_manifest(
    cfg: DictConfig,
    corpus: SerializedCorpus,
    tokens: list[int],
    residuals: list[tuple[int, int]],
    blob: bytes,
    tensors: dict[str, NDArray[Any]],
    tokenizer: Tokenizer,
    bos: int,
    *,
    configured_vocab_size: int,
) -> Manifest:
    model_bytes = sum(int(v.nbytes) for v in tensors.values())
    param_count = sum(int(v.size) for v in tensors.values())
    tokenizer_bytes = len(tokenizer.to_bytes())
    original_bytes = corpus.original_bytes
    gzip_bytes = len(gzip.compress(corpus.bytes))
    artifact_bytes = model_bytes + tokenizer_bytes + len(blob)
    ratio = (artifact_bytes / original_bytes) if original_bytes else 0.0
    return Manifest.model_validate(
        {
            "pak_version": "1.1",
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "model": {
                "arch": str(cfg.arch),
                "param_count": param_count,
                "n_layers": int(cfg.n_layers),
                "d_model": int(cfg.d_model),
                "n_heads": int(cfg.n_heads),
                "vocab_size": int(cfg.vocab_size),
                "context_len": int(cfg.context_len),
            },
            "tokenizer": {
                "name": str(cfg.tokenizer),
                "configured_vocab_size": configured_vocab_size,
                "actual_vocab_size": tokenizer.vocab_size(),
                "merge_count": tokenizer.merge_count(),
                "serialized_bytes_per_token": (len(corpus.bytes) / len(tokens) if tokens else None),
            },
            "corpus": {
                "n_files": corpus.n_files,
                "n_bytes": original_bytes,
                "n_tokens": len(tokens),
                "sha256": hashlib.sha256(corpus.bytes).hexdigest(),
                "file_map": _token_file_map(corpus, str(cfg.tokenizer)),
                "boundary_scheme": "length-prefixed-v1",
            },
            "decode": {
                "strategy": str(cfg.decode),
                "length_tokens": len(tokens),
                "bos_token_id": bos,
            },
            "residuals": {
                "count": len(residuals),
                "ratio": (len(residuals) / len(tokens)) if tokens else 0.0,
                "codec": str(cfg.codec),
            },
            "metrics": {
                "model_bytes": model_bytes,
                "artifact_bytes": artifact_bytes,
                "original_bytes": original_bytes,
                "gzip_bytes": gzip_bytes,
                "compression_ratio_vs_original": ratio,
                "lossless": True,
            },
            "seed": int(cfg.seed),
        }
    )
