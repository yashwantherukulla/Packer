from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.perf._client import client, timed_job


def main() -> None:
    """Time a full scan (extract -> sandbox each unit) and the single-unit startup overhead.

    ``scan_per_file_s`` is the wall time of scanning the reference fixture (chains
    extract -> scan). ``sandbox_startup_s`` scans a minimal one-line-benign reference so
    the delta over a no-op approximates per-unit sandbox spin-up (ADR-008 container).
    """
    scan_ref = os.environ.get("PACKER_PERF_SCAN_REF", "fixture:memorized-1")
    startup_ref = os.environ.get("PACKER_PERF_SANDBOX_REF", "fixture:one-line-benign")
    out: dict[str, float] = {}
    with client() as c:
        try:
            resp = c.post("/scan", json={"model_ref": scan_ref})
            out["scan_per_file_s"] = round(timed_job(c, resp), 3)
        except Exception as exc:  # missing ref on this stack — record and continue
            out["scan_per_file_s"] = -1.0
            print(f"scan skipped: {exc}")
        try:
            resp = c.post("/scan", json={"model_ref": startup_ref})
            out["sandbox_startup_s"] = round(timed_job(c, resp), 3)
        except Exception as exc:
            out["sandbox_startup_s"] = -1.0
            print(f"sandbox startup skipped: {exc}")
    Path("outputs/perf").mkdir(parents=True, exist_ok=True)
    Path("outputs/perf/scan.json").write_text(json.dumps(out, indent=2))
    print(out)


if __name__ == "__main__":
    main()
