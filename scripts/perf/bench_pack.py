from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.e2e.fixtures.build_toy_repo import build_toy_repo

from scripts.perf._client import client, timed_job


def main() -> None:
    zip_path = build_toy_repo(Path("outputs/perf/toy_repo.zip"))
    out: dict[str, float] = {}
    with client() as c:
        for device in ("cpu", "cuda"):
            with zip_path.open("rb") as fh:
                try:
                    resp = c.post(
                        "/pack",
                        files={"repo": ("toy_repo.zip", fh, "application/zip")},
                        data={"overrides": f"engine/pack=e2e_tiny engine/pack.device={device}"},
                    )
                    out[f"pack_{device}_s"] = round(timed_job(c, resp), 3)
                except Exception as exc:  # cuda absent on CI runners — record and continue
                    out[f"pack_{device}_s"] = -1.0
                    print(f"pack {device} skipped: {exc}")
    Path("outputs/perf").mkdir(parents=True, exist_ok=True)
    Path("outputs/perf/pack.json").write_text(json.dumps(out, indent=2))
    print(out)


if __name__ == "__main__":
    main()
