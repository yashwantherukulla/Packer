from __future__ import annotations

import json
import subprocess
from pathlib import Path

BENCHES = ["bench_pack", "bench_detect", "bench_scan", "bench_concurrency"]


def main() -> None:
    for b in BENCHES:
        subprocess.run(["uv", "run", "python", f"scripts/perf/{b}.py"], check=False)
    rows = {}
    for f in sorted(Path("outputs/perf").glob("*.json")):
        rows[f.stem] = json.loads(f.read_text())
    lines = [
        "# Performance Baselines",
        "",
        "> Recorded on the reference host; re-run via `uv run python scripts/perf/record_baselines.py`.",
        "",
    ]
    for name, data in rows.items():
        lines.append(f"## {name}")
        lines.append("")
        for k, v in data.items():
            lines.append(f"- `{k}`: {v}")
        lines.append("")
    Path("docs/PERFORMANCE.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
