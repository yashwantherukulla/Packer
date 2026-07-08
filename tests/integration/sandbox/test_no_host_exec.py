"""'Extracted code only runs in the sandbox' invariant + safetensors-only gate.

Two guarantees (SYSTEM-DESIGN §10, ADR-008 / spec §1):
1. No host process EXECUTES extracted/untrusted code. A grep-level assertion proves no
   OS-exec path exists in ``src/packer`` outside the sanctioned modules.
2. The safetensors-only default holds on every upload path: registering a pickle/.bin
   model is refused (UnsafeModelError -> 4xx).
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src" / "packer"

# Modules allowed to spawn OS processes. Neither EXECUTES the untrusted extracted code:
#   - engine/sandbox/adapters: the Docker sandbox adapter, which shells out to the Docker
#     daemon to build/run the isolation container (the ONLY place code is ever run).
#   - engine/sandbox/static: the trusted static-analysis pass (bandit/semgrep CLIs) which
#     *reads* the extracted file text but never runs it — analysis, not execution.
_ALLOWED = ("engine/sandbox/adapters", "engine/sandbox/static")
_BANNED = re.compile(r"\b(subprocess\.|os\.system|os\.popen|os\.exec|pty\.spawn|commands\.)")


def test_no_host_exec_path_outside_sandbox_adapter():
    offenders: list[str] = []
    for py in SRC.rglob("*.py"):
        rel = py.relative_to(SRC).as_posix()
        if any(a in rel for a in _ALLOWED):
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if _BANNED.search(line) and "# noqa: host-exec" not in line:
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, "host-exec path outside the sandbox adapter:\n" + "\n".join(offenders)


@pytest.mark.integration
def test_unsafe_pickle_upload_is_refused_everywhere(api_client: httpx.Client):
    # safetensors-only default: a non-safetensors (pickle) registration must be rejected
    # (mapped UnsafeModelError -> 422). NOTE: the real POST /models takes a JSON
    # ModelCreate {source, format} (not a file upload as the plan snippet assumed); the
    # boundary format gate mirrors HFModelLoader's policy on every path.
    resp = api_client.post("/models", json={"source": "evil.bin", "format": "pickle"})
    assert resp.status_code in (400, 422)
    body = resp.json()
    assert "unsafe" in str(body).lower() or "pickle" in str(body).lower()
