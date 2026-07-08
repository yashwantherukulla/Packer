from __future__ import annotations

from typing import Protocol

import torch
import torch.nn.functional as F  # noqa: N812  (idiomatic torch alias)
from torch import nn

from packer.engine.common.registries import ARCH_REGISTRY


class ModelArchitecture(Protocol):
    """Builds a trainable model from a config (the ARCH_REGISTRY element port).

    Lives in ``pack`` (not ``common``) because it references ``torch.nn.Module`` —
    keeping the kernel framework-light per the Dependency Rule.
    """

    def build(self, cfg: object) -> nn.Module: ...


class _Block(nn.Module):
    def __init__(self, d_model: int, n_heads: int) -> None:
        super().__init__()
        if d_model % n_heads != 0:
            raise ValueError(f"d_model {d_model} not divisible by n_heads {n_heads}")
        self.n_heads = n_heads
        self.ln1 = nn.LayerNorm(d_model)
        self.qkv = nn.Linear(d_model, 3 * d_model)
        self.proj = nn.Linear(d_model, d_model)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, c = x.shape
        h = self.ln1(x)
        qkv = self.qkv(h).view(b, t, 3, self.n_heads, c // self.n_heads)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # [3, B, H, T, hd]
        q, k, v = qkv[0], qkv[1], qkv[2]
        att = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        att = att.transpose(1, 2).reshape(b, t, c)
        x = x + self.proj(att)
        x = x + self.mlp(self.ln2(x))
        return x


class TinyDecoder(nn.Module):
    """From-scratch causal decoder-only transformer sized from config."""

    def __init__(
        self, vocab_size: int, d_model: int, n_layers: int, n_heads: int, context_len: int
    ) -> None:
        super().__init__()
        self.context_len = context_len
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(context_len, d_model)
        self.blocks = nn.ModuleList([_Block(d_model, n_heads) for _ in range(n_layers)])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        _, t = tokens.shape
        pos = torch.arange(t, device=tokens.device)
        x = self.tok_emb(tokens) + self.pos_emb(pos)[None, :, :]
        for block in self.blocks:
            x = block(x)
        out: torch.Tensor = self.head(self.ln_f(x))
        return out


@ARCH_REGISTRY.register("tiny-decoder")
class TinyDecoderArch:
    """ModelArchitecture builder for the tiny causal decoder."""

    def build(self, cfg: object) -> TinyDecoder:
        return TinyDecoder(
            vocab_size=int(cfg.vocab_size),  # type: ignore[attr-defined]
            d_model=int(cfg.d_model),  # type: ignore[attr-defined]
            n_layers=int(cfg.n_layers),  # type: ignore[attr-defined]
            n_heads=int(cfg.n_heads),  # type: ignore[attr-defined]
            context_len=int(cfg.context_len),  # type: ignore[attr-defined]
        )
