from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from packer.engine.sandbox.fileset import FileSet


@contextmanager
def materialize(files: FileSet) -> Iterator[Path]:
    """Write a FileSet to a scratch dir for CLI-based scanners. Static analysis
    only — these files are NEVER executed on the host (that is the sandbox's job)."""
    with tempfile.TemporaryDirectory(prefix="packer-scan-") as d:
        root = Path(d)
        for rel, data in files.files.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        yield root
