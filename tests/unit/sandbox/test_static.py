import pytest

import packer.engine.sandbox.static  # noqa: F401
from packer.engine.common.errors import ConfigError
from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.analyzers import StaticAnalyzer
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding


def test_aggregates_enabled_scanners():
    fs = FileSet(files={"m.py": b"eval('1')\n"})
    findings = StaticAnalyzer().scan(fs, enabled=["ast_rules"])
    assert any(f.rule == "ast.eval" for f in findings)


def test_open_closed_new_scanner_needs_no_edit():
    @SCANNER_REGISTRY.register("test_only_scanner")
    class _S:
        name = "test_only_scanner"

        def scan(self, files: FileSet) -> list[Finding]:
            return [Finding("low", "custom.hit", "x", 1, "custom")]

    findings = StaticAnalyzer().scan(FileSet(files={"x": b""}), enabled=["test_only_scanner"])
    assert findings == [Finding("low", "custom.hit", "x", 1, "custom")]


def test_unknown_scanner_raises_config_error():
    with pytest.raises(ConfigError):
        StaticAnalyzer().scan(FileSet(files={}), enabled=["does_not_exist"])
