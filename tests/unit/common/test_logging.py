from packer.engine.common.logging import (
    bind_correlation_id,
    current_correlation_id,
    get_logger,
)


def test_correlation_id_roundtrip():
    assert current_correlation_id() is None
    bind_correlation_id("job-123")
    assert current_correlation_id() == "job-123"


def test_get_logger_returns_named_logger():
    log = get_logger("packer.test")
    assert log.name == "packer.test"
