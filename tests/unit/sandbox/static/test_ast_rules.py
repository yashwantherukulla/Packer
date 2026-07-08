import packer.engine.sandbox.static  # noqa: F401  (triggers self-registration)
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet


def _fs(src: bytes) -> FileSet:
    return FileSet(files={"m.py": src})


def test_registered():
    assert "ast_rules" in SCANNER_REGISTRY.names()


def test_flags_eval_and_subprocess():
    scanner = SCANNER_REGISTRY.create("ast_rules")
    findings = scanner.scan(_fs(b"import subprocess\neval('2+2')\nsubprocess.Popen(['ls'])\n"))
    rules = {f.rule for f in findings}
    assert "ast.eval" in rules
    assert "ast.subprocess" in rules
    assert any(f.severity == "high" for f in findings)
    assert all(f.file == "m.py" and f.line > 0 for f in findings)


def test_benign_file_has_no_high_findings():
    scanner = SCANNER_REGISTRY.create("ast_rules")
    findings = scanner.scan(_fs(b"def add(a, b):\n    return a + b\n"))
    assert all(f.severity != "high" for f in findings)


def test_unparseable_is_info_not_crash():
    scanner = SCANNER_REGISTRY.create("ast_rules")
    findings = scanner.scan(_fs(b"def (:\n"))
    assert any(f.rule == "ast.parse-error" for f in findings)
