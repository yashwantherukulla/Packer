from packer.engine.common.config_schema import compose_config


def test_detect_config_composes():
    cfg = compose_config()
    assert "spectral" in list(cfg.engine.detect.enabled_signals)
    assert cfg.engine.detect.calibration_version == "detect-v0"
