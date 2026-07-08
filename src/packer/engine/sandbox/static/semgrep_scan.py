from __future__ import annotations

import json
import subprocess
from pathlib import Path

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.static._util import materialize

_RULES = Path(__file__).resolve().parent / "resources" / "semgrep_dangerous.yml"
_SEV = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}


@SCANNER_REGISTRY.register("semgrep_scan")
class SemgrepScanner:
    """Multi-language Semgrep, bundled ruleset (no network). Degrades if the
    binary is unavailable on the host (e.g., Windows-native dev, ADR-004)."""

    name = "semgrep_scan"

    def scan(self, files: FileSet) -> list[Finding]:
        with materialize(files) as root:
            try:
                proc = subprocess.run(
                    [
                        "semgrep",
                        "scan",
                        "--quiet",
                        "--json",
                        "--no-git-ignore",
                        "--config",
                        str(_RULES),
                        str(root),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                return [Finding("info", "semgrep.unavailable", "", 0, f"semgrep not run: {exc}")]
            try:
                report = json.loads(proc.stdout or "{}")
            except json.JSONDecodeError:
                return [Finding("info", "semgrep.unavailable", "", 0, "semgrep produced no JSON")]
            out: list[Finding] = []
            for item in report.get("results", []):
                rel = _rel(item.get("path", ""), str(root))
                sev = item.get("extra", {}).get("severity", "INFO")
                out.append(
                    Finding(
                        _SEV.get(sev, "low"),
                        f"semgrep.{item.get('check_id', 'rule').split('.')[-1]}",
                        rel,
                        int(item.get("start", {}).get("line", 0)),
                        item.get("extra", {}).get("message", "")[:200],
                    )
                )
            return out


def _rel(abs_path: str, root: str) -> str:
    try:
        return str(Path(abs_path).relative_to(root)).replace("\\", "/")
    except ValueError:
        return abs_path
