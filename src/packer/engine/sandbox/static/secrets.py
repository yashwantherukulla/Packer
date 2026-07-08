from __future__ import annotations

import re

from packer.engine.common.registries import SCANNER_REGISTRY
from packer.engine.sandbox.fileset import FileSet
from packer.engine.sandbox.findings import Finding

_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "secrets.private-key",
        "high",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    ("secrets.aws-access-key", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "secrets.generic-token",
        "medium",
        re.compile(
            r"(?i)(?:api|secret|token|passwd|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"
        ),
    ),
]


@SCANNER_REGISTRY.register("secrets")
class SecretsScanner:
    """Regex secrets sweep over extracted text files (spec §2)."""

    name = "secrets"

    def scan(self, files: FileSet) -> list[Finding]:
        out: list[Finding] = []
        for path, data in files.files.items():
            text = data.decode("utf-8", "replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for rule, sev, pat in _PATTERNS:
                    if pat.search(line):
                        out.append(Finding(sev, rule, path, lineno, "possible hardcoded secret"))
        return out
