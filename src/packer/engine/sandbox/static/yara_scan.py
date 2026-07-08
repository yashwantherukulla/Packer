from __future__ import annotations

from pathlib import Path
from typing import Any

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding

_RULES_PATH = Path(__file__).resolve().parent / "resources" / "malware.yar"


@SCANNER_REGISTRY.register("yara_scan")
class YaraScanner:
    """YARA byte-pattern scanner over extracted files (multi-language, spec §2).

    yara-python is an optional native dependency (no Windows wheel for every
    Python — ADR-004); the scanner **lazily imports** it and degrades to a
    ``yara.unavailable`` info marker if the module or rule compilation fails.
    """

    name = "yara_scan"

    def __init__(self) -> None:
        self._rules: Any = None
        try:
            import yara

            self._rules = yara.compile(filepath=str(_RULES_PATH))
        except Exception:  # ImportError (not installed) or yara.Error (bad rules)
            self._rules = None

    def scan(self, files: FileSet) -> list[Finding]:
        if self._rules is None:
            return [Finding("info", "yara.unavailable", "", 0, "YARA unavailable on this host")]
        out: list[Finding] = []
        for path, data in files.files.items():
            for match in self._rules.match(data=data):
                sev = str(match.meta.get("severity", "medium"))
                out.append(
                    Finding(
                        sev,
                        f"yara.{match.rule}",
                        path,
                        0,
                        str(match.meta.get("description", match.rule)),
                    )
                )
        return out
