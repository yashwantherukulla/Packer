from __future__ import annotations

import random

import numpy as np
import torch
import torch.nn.functional as F  # noqa: N812  (idiomatic torch alias)
from torch import nn

from packer.engine.common.progress import ProgressCallback, null_progress


def apply_determinism(seed: int, deterministic: bool) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
        if torch.cuda.is_available():
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False


def resolve_device(name: str) -> str:
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


class OverfitTrainer:
    """Trains a decoder to memorize a token stream (no dropout, teacher forcing)."""

    def train(
        self,
        model: nn.Module,
        tokens: list[int],
        cfg: object,
        progress: ProgressCallback = null_progress,
    ) -> None:
        seed = int(cfg.seed)  # type: ignore[attr-defined]
        apply_determinism(seed, bool(cfg.deterministic))  # type: ignore[attr-defined]
        device = resolve_device(str(cfg.device))  # type: ignore[attr-defined]
        model.to(device).train()
        if not tokens:
            progress(step="train", pct=0.8, detail="empty corpus; nothing to train")
            return
        bos = int(cfg.bos_token_id)  # type: ignore[attr-defined]
        inp = torch.tensor([[bos, *tokens[:-1]]], dtype=torch.long, device=device)
        tgt = torch.tensor([tokens], dtype=torch.long, device=device)
        opt = torch.optim.AdamW(
            model.parameters(),
            lr=float(cfg.lr),  # type: ignore[attr-defined]
            weight_decay=float(cfg.weight_decay),  # type: ignore[attr-defined]
        )
        epochs = int(cfg.epochs)  # type: ignore[attr-defined]
        report_every = max(1, epochs // 20)
        for epoch in range(epochs):
            opt.zero_grad(set_to_none=True)
            logits = model(inp)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1))
            loss.backward()  # type: ignore[no-untyped-call]  # untyped in torch stubs
            opt.step()
            if epoch % report_every == 0 or epoch == epochs - 1:
                with torch.no_grad():
                    acc = (logits.argmax(-1) == tgt).float().mean().item()
                pct = 0.05 + 0.75 * (epoch + 1) / epochs
                progress(
                    step="train",
                    pct=pct,
                    detail=f"epoch {epoch + 1}/{epochs} loss={loss.item():.4f} acc={acc:.3f}",
                )
