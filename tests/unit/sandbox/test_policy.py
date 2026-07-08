from packer.engine.common.config_schema import compose_config
from packer.engine.sandbox.policy import SandboxPolicy


def test_policy_from_cfg_pulls_hardened_flags():
    cfg = compose_config().engine.sandbox
    pol = SandboxPolicy.from_cfg(cfg)
    assert pol.network == "none"
    assert pol.read_only is True
    assert pol.cap_drop == ("ALL",)
    assert pol.pids_limit == 64
    assert pol.timeout_s == 20
    assert pol.user == "1000:1000"


def test_policy_is_frozen():
    pol = SandboxPolicy(image="packer-sandbox:latest")
    try:
        pol.network = "bridge"  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError
        assert "cannot assign" in str(exc) or "frozen" in str(exc).lower()
    else:
        raise AssertionError("SandboxPolicy must be immutable")
