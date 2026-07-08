from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.perf._client import client, timed_job


def _refs() -> dict[str, str]:
    """Model refs to time, keyed by a size label.

    Override with PACKER_PERF_DETECT_REFS="small=fixture:memorized-1,large=hf:some/model";
    defaults hit the Phase-1/2 memorized fixture so the bench runs on any stack.
    """
    raw = os.environ.get("PACKER_PERF_DETECT_REFS")
    if raw:
        pairs = [kv.split("=", 1) for kv in raw.split(",")]
        return {p[0]: p[1] for p in pairs}
    return {"tiny": "fixture:memorized-1"}


def main() -> None:
    out: dict[str, float] = {}
    with client() as c:
        for label, ref in _refs().items():
            try:
                resp = c.post("/detect", json={"model_ref": ref})
                out[f"detect_{label}_s"] = round(timed_job(c, resp), 3)
            except Exception as exc:  # missing ref on this stack — record and continue
                out[f"detect_{label}_s"] = -1.0
                print(f"detect {label} skipped: {exc}")
    Path("outputs/perf").mkdir(parents=True, exist_ok=True)
    Path("outputs/perf/detect.json").write_text(json.dumps(out, indent=2))
    print(out)


if __name__ == "__main__":
    main()
