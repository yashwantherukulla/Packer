import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings

from packer.engine.common.registries import CODEC_REGISTRY
from packer.engine.pack.residuals import DeltaVarintCodec, ResidualCapturer


def test_codec_registered():
    assert "delta-varint-v1" in CODEC_REGISTRY.names()
    assert isinstance(CODEC_REGISTRY.create("delta-varint-v1"), DeltaVarintCodec)


def test_codec_empty():
    codec = DeltaVarintCodec()
    assert codec.decode(codec.encode([])) == []


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(st.integers(0, 100_000), st.integers(0, 8191)), max_size=256))
def test_codec_roundtrip(pairs):
    residuals = sorted(dict(pairs).items())  # unique positions, ascending
    codec = DeltaVarintCodec()
    assert codec.decode(codec.encode(residuals)) == residuals


class _StubModel:
    """Teacher-forced argmax that always predicts 0 -> everything is a residual."""

    bos_token_id = 0

    def teacher_forced_preds(self, tokens):
        return [0] * len(tokens)


def test_capture_flags_all_mismatches():
    tokens = [5, 0, 7, 0, 9]
    residuals = ResidualCapturer().capture(_StubModel(), tokens)
    # positions whose true token != predicted 0
    assert residuals == [(0, 5), (2, 7), (4, 9)]


def test_capture_empty():
    assert ResidualCapturer().capture(_StubModel(), []) == []
