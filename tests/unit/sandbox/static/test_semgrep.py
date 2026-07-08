import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet


def test_registered():
    assert "semgrep_scan" in SCANNER_REGISTRY.names()


def test_scan_runs_or_degrades():
    src = b"import subprocess\nsubprocess.Popen(cmd, shell=True)\n"
    findings = SCANNER_REGISTRY.create("semgrep_scan").scan(FileSet(files={"m.py": src}))
    assert isinstance(findings, list)
    assert all(hasattr(f, "severity") for f in findings)
