# Performance Baselines

> **Status: baselines pending.** The numbers below are placeholders. Baselines must be
> **recorded in a stack-equipped environment** (a host with a running Docker daemon +
> the full compose stack, or the nightly `e2e-nightly` CI job). Regenerate with:
>
> ```bash
> docker compose -f docker/compose.yml up -d --build      # bring the stack online
> uv run python scripts/perf/record_baselines.py          # runs every bench, rewrites this file
> ```
>
> `record_baselines.py` runs `bench_pack`, `bench_detect`, `bench_scan`, and
> `bench_concurrency`, collects `outputs/perf/*.json`, and overwrites this table with the
> measured values. It could not be run on the authoring host (Docker daemon down), so the
> figures are deferred to the first stack-equipped run.

## bench_pack — pack timing (submit → succeeded), by device

| metric | value |
|--------|-------|
| `pack_cpu_s` | — (pending) |
| `pack_cuda_s` | — (pending; `-1.0` when CUDA absent) |

## bench_detect — detect timing, by model size

| metric | value |
|--------|-------|
| `detect_tiny_s` | — (pending) |
| `detect_<size>_s` | — (pending; one row per `PACKER_PERF_DETECT_REFS` entry) |

## bench_scan — scan timing + sandbox startup overhead

| metric | value |
|--------|-------|
| `scan_per_file_s` | — (pending) |
| `sandbox_startup_s` | — (pending; single-unit container spin-up) |

## bench_concurrency — N concurrent jobs + WS fan-out

| metric | value |
|--------|-------|
| `n_jobs` | 4 (default) |
| `subscribers_per_job` | 5 (default) |
| `total_events_received` | — (pending) |
| `wall_s` | — (pending) |

The concurrency bench proves the `gpu` queue serializes `pack` while `detect`/`scan`
proceed on the `default` queue, and that WebSocket progress fans out to many subscribers
per job without loss.
