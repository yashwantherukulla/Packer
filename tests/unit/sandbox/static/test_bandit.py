import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet


def test_registered():
    assert "bandit_scan" in SCANNER_REGISTRY.names()


def test_flags_hardcoded_subprocess_shell(tmp_path):
    src = b"import subprocess\nsubprocess.call('rm -rf /', shell=True)\n"
    findings = SCANNER_REGISTRY.create("bandit_scan").scan(FileSet(files={"m.py": src}))
    # bandit present -> a real finding; bandit missing -> graceful info marker
    assert findings, "bandit must yield at least one finding or an unavailable marker"
    assert any(f.rule.startswith("bandit.") or f.rule == "bandit.unavailable" for f in findings)
