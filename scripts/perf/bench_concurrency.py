from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.perf._client import API_BASE

WS_BASE = API_BASE.replace("http", "ws", 1)


async def _subscribe(job_id: str, seen: list[int]) -> None:
    async with websockets.connect(f"{WS_BASE}/ws/jobs/{job_id}") as ws:
        try:
            while True:
                await asyncio.wait_for(ws.recv(), timeout=30)
                seen.append(1)
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            return


async def main(n_jobs: int = 4, subscribers_per_job: int = 5) -> None:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=60) as c:
        # submit N light detect jobs (default queue) + assert they proceed concurrently
        submitted = [
            (await c.post("/detect", json={"model_ref": "fixture:memorized-1"})).json()["id"]
            for _ in range(n_jobs)
        ]
        seen: list[int] = []
        start = time.monotonic()
        # fan out: many WS subscribers per job
        await asyncio.gather(
            *[_subscribe(jid, seen) for jid in submitted for _ in range(subscribers_per_job)]
        )
        result = {
            "n_jobs": n_jobs,
            "subscribers_per_job": subscribers_per_job,
            "total_events_received": len(seen),
            "wall_s": round(time.monotonic() - start, 3),
        }
    Path("outputs/perf").mkdir(parents=True, exist_ok=True)
    Path("outputs/perf/concurrency.json").write_text(json.dumps(result, indent=2))
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
