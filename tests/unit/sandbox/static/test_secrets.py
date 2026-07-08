import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet


def test_registered():
    assert "secrets" in SCANNER_REGISTRY.names()


def test_flags_private_key_and_aws():
    src = b"-----BEGIN RSA PRIVATE KEY-----\nMIIB...\nAWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
    findings = SCANNER_REGISTRY.create("secrets").scan(FileSet(files={"c.py": src}))
    rules = {f.rule for f in findings}
    assert "secrets.private-key" in rules
    assert "secrets.aws-access-key" in rules
    assert all(f.line > 0 for f in findings)


def test_benign_config_clean():
    findings = SCANNER_REGISTRY.create("secrets").scan(FileSet(files={"c.py": b"PORT = 8080\n"}))
    assert findings == []
