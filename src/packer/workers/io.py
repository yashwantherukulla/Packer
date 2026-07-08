from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Any


def materialize_repo(store: Any, ref: str) -> Path:
    """Turn an uploaded zip blob (by store key) into a temp repo dir for Packer.pack.

    Adapter-level IO — no ML/analysis logic lives here.
    """
    dest = Path(tempfile.mkdtemp(prefix="packer-repo-"))
    with store.open_blob(ref) as fh, zipfile.ZipFile(fh) as zf:
        zf.extractall(dest)
    return dest
