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
        tokenizer.train(corpus.bytes, int(cfg.vocab_size))
        tokens = tokenizer.encode(corpus.bytes)
        progress(
            step="tokenize",
            pct=0.05,
            detail=f"{len(tokens)} tokens, vocab={tokenizer.vocab_size()}",
        )

        context_len = int(cfg.context_len)
        if len(tokens) > context_len:
            raise PackError(
                f"corpus token length {len(tokens)} exceeds context_len {context_len}",
                context={"n_tokens": len(tokens), "context_len": context_len},
            )

        bos = tokenizer.bos_id()
        OmegaConf.update(cfg, "bos_token_id", bos, force_add=True)  # keep train/decode aligned

        apply_determinism(int(cfg.seed), bool(cfg.deterministic))
        model = cast(ModelArchitecture, ARCH_REGISTRY.create(str(cfg.arch))).build(cfg)
        OverfitTrainer().train(model, tokens, cfg, progress)

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
        manifest = _build_manifest(cfg, corpus, tokens, residuals, blob, tensors, tokenizer, bos)
        bundle = PakBundle(
            tensors=tensors,
            tokenizer_bytes=tokenizer.to_bytes(),
            manifest=manifest,
            residual_blob=blob,
        )

        progress(step="write", pct=0.98, detail="persist .pak")
        artifact_id = _persist(bundle, cfg, ports, root)
        progress(step="done", pct=1.0, detail=artifact_id)
        return artifact_id


def _persist(bundle: PakBundle, cfg: DictConfig, ports: object, root: Path) -> str:
    store = getattr(ports, "store", None)
    if store is not None:
        artifact_id: str = store.put_pak(bundle)
        return artifact_id
    out_dir = Path(str(cfg.get("out_dir", "./outputs")))
    out = out_dir / f"{root.name}.pak"
    PakWriter().write(out, bundle)
    return str(out)


def _token_file_map(corpus: SerializedCorpus, tokenizer: Tokenizer) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    for rel, start, end in corpus.file_map:
        spans.append(
            {
                "path": rel,
                "token_start": len(tokenizer.encode(corpus.bytes[:start])),
                "token_end": len(tokenizer.encode(corpus.bytes[:end])),
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
            "pak_version": "1.0",
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
            "corpus": {
                "n_files": corpus.n_files,
                "n_bytes": original_bytes,
                "n_tokens": len(tokens),
                "sha256": hashlib.sha256(corpus.bytes).hexdigest(),
                "file_map": _token_file_map(corpus, tokenizer),
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
