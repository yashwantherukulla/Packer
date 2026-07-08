from __future__ import annotations

import json
import subprocess
from pathlib import Path

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding
from packer.engine.sandbox.static._util import materialize

_SEV = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}


@SCANNER_REGISTRY.register("bandit_scan")
class BanditScanner:
    """Bandit (Python) security linter, run as a subprocess over the extracted files."""

    name = "bandit_scan"

    def scan(self, files: FileSet) -> list[Finding]:
        with materialize(files) as root:
            try:
                proc = subprocess.run(
                    ["bandit", "-r", str(root), "-f", "json", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                return [Finding("info", "bandit.unavailable", "", 0, f"bandit not run: {exc}")]
            try:
                report = json.loads(proc.stdout or "{}")
            except json.JSONDecodeError:
                return [Finding("info", "bandit.unavailable", "", 0, "bandit produced no JSON")]
            out: list[Finding] = []
            for item in report.get("results", []):
                rel = _relativize(item.get("filename", ""), str(root))
                out.append(
                    Finding(
                        _SEV.get(item.get("issue_severity", "LOW"), "low"),
                        f"bandit.{item.get('test_id', 'B000')}",
                        rel,
                        int(item.get("line_number", 0)),
                        item.get("issue_text", "")[:200],
                    )
                )
            return out


def _relativize(abs_path: str, root: str) -> str:
    try:
        return str(Path(abs_path).relative_to(root)).replace("\\", "/")
    except ValueError:
        return abs_path
