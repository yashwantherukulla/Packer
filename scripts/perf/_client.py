from __future__ import annotations

import os
import time

import httpx

API_BASE = os.environ.get("PACKER_PERF_BASE_URL", "http://localhost:8000")


def client() -> httpx.Client:
    return httpx.Client(base_url=API_BASE, timeout=60)


def timed_job(c: httpx.Client, submit: httpx.Response) -> float:
    """Submit-to-succeeded wall time (seconds)."""
    job_id = submit.raise_for_status().json()["id"]
    start = time.monotonic()
    while True:
        status = c.get(f"/jobs/{job_id}").raise_for_status().json()["status"]
        if status in ("succeeded", "failed", "cancelled"):
            assert status == "succeeded", f"job {job_id} -> {status}"
            return time.monotonic() - start
        time.sleep(0.5)
