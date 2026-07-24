from __future__ import annotations

import base64
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from packer.engine.extract.model import Extraction

_EXTRACTION_PREFIX = "extractions/"


def materialize_repo(store: Any, ref: str) -> Path:
    """Turn an uploaded zip blob (by store key) into a temp repo dir for Packer.pack.

    Adapter-level IO — no ML/analysis logic lives here.
    """
    dest = Path(tempfile.mkdtemp(prefix="packer-repo-"))
    with store.open_blob(ref) as fh, zipfile.ZipFile(fh) as zf:
        zf.extractall(dest)
    return dest


def persist_extraction(store: Any, job_id: str, extraction: Extraction) -> str:
    if not hasattr(store, "put_blob"):
        raise TypeError("store does not support blob persistence for extractions")
    payload = {
        "files": {
            path: base64.b64encode(data).decode("ascii") for path, data in extraction.files.items()
        },
        "confidence": extraction.confidence,
        "confidence_class": extraction.confidence_class,
        "notes": list(extraction.notes),
    }
    store.put_blob(_EXTRACTION_PREFIX + f"{job_id}.json", json.dumps(payload).encode("utf-8"))
    return job_id


def load_extraction(store: Any, extraction_id: str) -> Extraction:
    raw_id = (
        extraction_id.split("extraction:", 1)[1]
        if extraction_id.startswith("extraction:")
        else extraction_id
    )
    key = _EXTRACTION_PREFIX + f"{raw_id}.json"
    with store.open_blob(key) as fh:
        payload = json.loads(fh.read().decode("utf-8"))
    files = {
        path: base64.b64decode(data.encode("ascii"))
        for path, data in payload.get("files", {}).items()
    }
    return Extraction(
        files=files,
        confidence=float(payload["confidence"]),
        confidence_class=str(payload["confidence_class"]),
        notes=tuple(str(n) for n in payload.get("notes", [])),
    )
