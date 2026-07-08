import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet


def test_registered():
    assert "yara_scan" in SCANNER_REGISTRY.names()


def test_matches_known_pattern():
    src = b"import os\nos.system(__import__('base64').b64decode('bHM='))\n"
    findings = SCANNER_REGISTRY.create("yara_scan").scan(FileSet(files={"m.py": src}))
    assert any(f.rule.startswith("yara.") for f in findings)
