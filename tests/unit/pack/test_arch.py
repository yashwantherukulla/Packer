import torch
from omegaconf import OmegaConf

from packer.engine.common.registries import ARCH_REGISTRY
from packer.engine.pack.arch import TinyDecoder, TinyDecoderArch


def _cfg():
    return OmegaConf.create(
        {"vocab_size": 64, "d_model": 32, "n_layers": 2, "n_heads": 4, "context_len": 16}
    )


def test_registered_builder():
    assert "tiny-decoder" in ARCH_REGISTRY.names()
    arch = ARCH_REGISTRY.create("tiny-decoder")
    assert isinstance(arch, TinyDecoderArch)
    assert isinstance(arch.build(_cfg()), TinyDecoder)


def test_forward_shapes():
    model = TinyDecoderArch().build(_cfg())
    tokens = torch.zeros((1, 8), dtype=torch.long)
    logits = model(tokens)
    assert logits.shape == (1, 8, 64)


def test_forward_is_deterministic_in_eval():
    model = TinyDecoderArch().build(_cfg()).eval()
    tokens = torch.arange(5, dtype=torch.long).view(1, 5)
    with torch.no_grad():
        a = model(tokens)
        b = model(tokens)
    assert torch.equal(a, b)
