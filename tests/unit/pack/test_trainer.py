import torch

from packer.engine.common.progress import RecordingProgress
from packer.engine.pack.arch import TinyDecoderArch
from packer.engine.pack.trainer import OverfitTrainer, apply_determinism, resolve_device


def _model(cfg):
    apply_determinism(int(cfg.seed), bool(cfg.deterministic))
    return TinyDecoderArch().build(cfg)


def test_resolve_device_explicit():
    assert resolve_device("cpu") == "cpu"


def test_training_reduces_loss_and_reports(cfg_factory):
    cfg = cfg_factory(epochs=40, vocab_size=64)
    model = _model(cfg)
    tokens = [3, 1, 4, 1, 5, 9, 2, 6]
    inp = torch.tensor([[int(cfg.bos_token_id), *tokens[:-1]]])
    tgt = torch.tensor([tokens])

    def loss_of(m):
        with torch.no_grad():
            logits = m(inp)
            return torch.nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)), tgt.reshape(-1)
            ).item()

    before = loss_of(model)
    rec = RecordingProgress()
    OverfitTrainer().train(model, tokens, cfg, rec)
    after = loss_of(model)
    assert after < before
    assert any(e.step == "train" for e in rec.events)


def test_training_is_deterministic(cfg_factory):
    cfg = cfg_factory(epochs=10, vocab_size=64)
    tokens = [1, 2, 3, 4, 5, 6]
    m1 = _model(cfg)
    OverfitTrainer().train(m1, tokens, cfg)
    m2 = _model(cfg)
    OverfitTrainer().train(m2, tokens, cfg)
    for p1, p2 in zip(m1.parameters(), m2.parameters(), strict=True):
        assert torch.equal(p1, p2)


def test_empty_tokens_noop(cfg_factory):
    cfg = cfg_factory()
    model = _model(cfg)
    OverfitTrainer().train(model, [], cfg)  # must not raise
