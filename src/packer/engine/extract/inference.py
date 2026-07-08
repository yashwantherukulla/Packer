from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import torch

from packer.engine.common.errors import ReconstructionError

if TYPE_CHECKING:
    from packer.engine.artifacts.pak import PakBundle
    from packer.engine.common.types import ModelRef


class InferenceModel:
    """Thin FORWARD-ONLY wrapper — the ONLY place Part 3 runs inference for a
    foreign model (SYSTEM-DESIGN §5.5). Exposes next-token logits; no training,
    no grad. (Exact extraction reuses the Phase-1 Unpacker's own forward pass.)"""

    def __init__(self, module: torch.nn.Module, bos_token_id: int) -> None:
        self._m = module.eval()
        self.bos_token_id = bos_token_id

    @classmethod
    def from_pak(cls, bundle: PakBundle) -> InferenceModel:
        from packer.engine.pack.arch import TinyDecoder  # reuse Part-1 architecture

        info = bundle.manifest.model
        if (
            info.n_layers is None
            or info.d_model is None
            or info.n_heads is None
            or info.vocab_size is None
            or info.context_len is None
        ):
            raise ReconstructionError(
                "manifest.model.{n_layers,d_model,n_heads,vocab_size,context_len} "
                "are required to rebuild the decoder for inference",
                context={"arch": info.arch},
            )
        module = TinyDecoder(
            vocab_size=info.vocab_size,
            d_model=info.d_model,
            n_layers=info.n_layers,
            n_heads=info.n_heads,
            context_len=info.context_len,
        )
        state = {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in bundle.tensors.items()}
        try:
            module.load_state_dict(state)
        except (RuntimeError, KeyError) as exc:
            raise ReconstructionError(
                "pak tensors do not fit the declared architecture",
                context={"cause": str(exc)},
            ) from exc
        return cls(module, bundle.manifest.decode.bos_token_id)

    @classmethod
    def from_model_ref(cls, ref: ModelRef, bos_token_id: int = 1) -> InferenceModel:
        """Best-effort forward for a foreign model (blind mode). Uses transformers
        if the architecture is loadable; raises ReconstructionError otherwise."""
        try:
            from transformers import AutoModelForCausalLM

            module = AutoModelForCausalLM.from_pretrained(ref.value)
        except Exception as exc:  # unknown/unsupported arch -> caller degrades
            raise ReconstructionError(
                "foreign model not loadable for blind decode",
                context={"ref": ref.value, "cause": str(exc)},
            ) from exc
        return cls(module, bos_token_id)

    @torch.no_grad()
    def next_logits(self, tokens: list[int]) -> torch.Tensor:
        ids = torch.tensor([tokens], dtype=torch.long)
        out = self._m(ids)
        logits = out.logits if hasattr(out, "logits") else out
        last: torch.Tensor = logits[0, -1, :]
        return last
