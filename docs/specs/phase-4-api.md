# Phase 4 — API Service

> **Goal:** expose all three engines as asynchronous, observable jobs over a typed REST API with live progress.
> **Depends on:** Phases 1–3. **Blocks:** Phase 5 (UI).
> **Part mapping:** service layer for Parts 1–3; orchestration = ADR-011 (Celery + Redis + Postgres + WebSockets).

---

## 1. Scope

**In scope**
- FastAPI app; Pydantic v2 wire schemas.
- PostgreSQL schema + Alembic migrations for jobs, models, artifacts, reports.
- Celery workers (`pack.run`, `detect.run`, `extract.run`, `scan.run`) with **queue routing** (GPU-heavy `pack` vs. light `detect`/`scan`).
- Redis broker/result backend + **progress pub/sub**.
- **WebSocket** progress hub (fans out Redis events to subscribed clients).
- Object storage for uploaded models + `.pak` artifacts (filesystem volume in dev).
- OpenAPI spec (drives the frontend's generated client).

**Out of scope**
- Auth/RBAC beyond a dependency stub (non-goal). Any UI (Phase 5). Horizontal autoscaling / prod deploy (Phase 6 covers compose).

---

## 2. Endpoints (wire contract)

| Method | Path | Body / params | Returns |
|---|---|---|---|
| POST | `/pack` | repo upload (zip) + pack config overrides | `job` |
| POST | `/detect` | `model_ref` (hf-id \| uploaded-id \| artifact-id) | `job` |
| POST | `/extract` | `model_ref` (+ optional artifact-id for manifest) | `job` |
| POST | `/scan` | `extraction-id` \| `model_ref` (chains extract→scan) | `job` |
| GET | `/jobs/{id}` | — | job status + result refs |
| GET | `/jobs` | filters (status, type) | list |
| WS | `/ws/jobs/{id}` | — | progress event stream |
| GET | `/models` / `/models/{id}` | — | registered models |
| POST | `/models` | model upload | model record |
| GET | `/artifacts/{id}` | — | `.pak` metadata / download |
| GET | `/reports/{id}` | — | detect or scan report (shared `Report` model) |

All request/response bodies are Pydantic models in `packer.api.schemas`. Long operations always return a `job` immediately; results are fetched via `/jobs/{id}` or streamed via WS.

---

## 3. Data model (Postgres)

```
jobs(id, type, status, created_at, started_at, finished_at, correlation_id,
     input_ref, result_ref, error, progress_pct, progress_step)
models(id, source, format, sha256, path, meta_json, created_at)
artifacts(id, job_id, pak_path, manifest_json, metrics_json, created_at)
reports(id, job_id, kind, report_json, created_at)   -- kind: detect | scan
```
Status: `queued → running → succeeded | failed | cancelled`. Migrations via Alembic.

---

## 4. Job & progress flow

```
POST /pack ─▶ validate ─▶ insert jobs(row, queued) ─▶ celery.send_task(pack.run, job_id)
                                                        │ (routed to GPU queue)
worker pack.run: load inputs ─▶ progress_cb publishes to Redis "progress:{job_id}"
                              ─▶ engine.pack.pack_repo(...) ─▶ store artifact
                              ─▶ update jobs(succeeded, result_ref)
client: WS /ws/jobs/{id} ─▶ api subscribes Redis "progress:{job_id}" ─▶ pushes events
```

- **Progress callback bridge:** workers construct a `ProgressCallback` (Phase 0 protocol) that publishes JSON to Redis; the WS hub relays. The engine stays Redis-agnostic.
- **Queue routing:** `pack` → `gpu` queue (worker pinned to a CUDA host); `detect`/`extract`/`scan` → `default`. Configured in Hydra `broker/redis.yaml` + Celery route config.
- **Idempotency/dedup:** identical inputs (by hash) may reuse an existing succeeded job (optional, config-gated).

---

## 5. Integration points

- **Workers import the engine directly** (`engine.pack/detect/sandbox`); no logic duplicated in the API.
- **Reports use the shared `engine/report/` model** so `/reports/{id}` serves both detect and scan uniformly.
- **Settings loaded via Hydra** at startup (compose API); DB/redis URLs via env interpolation (ADR-012). Pydantic is only the wire contract.
- Uploaded models flow through Phase-0 `load_model` (safetensors-first) before any analysis.

---

## 6. Testing plan

- **Unit:** schema validation; job state transitions; queue-routing selection; the Redis→WS relay (with a fake broker).
- **Integration (`integration` marker, testcontainers):** real Postgres + Redis; submit each job type, poll to completion, assert persisted job/report/artifact; WS receives progress events end-to-end. Uses tiny Phase-1 fixtures so `pack` completes fast on CPU.
- **API E2E (httpx):** `POST /pack` → poll `/jobs` → `GET /artifacts` → `POST /detect` on that artifact → `GET /reports`. Full happy path without the browser.
- **Failure paths:** unsafe-pickle upload → 4xx with mapped `UnsafeModelError`; engine exception → job `failed` with error recorded, not a 500 crash.

---

## 7. Development steps (ordered)

1. App factory + Hydra settings load + lifespan (DB/Redis pools).
2. SQLAlchemy models + Alembic baseline migration.
3. Pydantic schemas + `jobs` service (create/query/transition).
4. Celery app + broker config + the four tasks (thin wrappers over the engine) + queue routing.
5. Progress bridge (worker → Redis) + WebSocket hub (Redis → clients).
6. Routers: pack/detect/extract/scan → jobs; models/artifacts/reports.
7. Object storage adapter (filesystem volume; interface allows S3 later).
8. Error mapping (`PackerError` taxonomy → HTTP problem responses).
9. Integration + API-E2E suites.

---

## 8. Acceptance criteria (milestone gate)

- [ ] Each engine runs end-to-end via its REST endpoint as a background Celery job.
- [ ] Progress streams over WebSocket for a live job.
- [ ] Jobs, models, artifacts, and reports persist in Postgres and are queryable.
- [ ] `pack` routes to the GPU queue; `detect`/`scan` to default.
- [ ] Integration tests pass against real Postgres/Redis (testcontainers); the API-E2E happy path passes.
- [ ] Engine errors surface as failed jobs with recorded reasons, never uncaught 500s.

---

## 9. Risks

- **Long training jobs blocking a worker** → dedicated `gpu` queue + concurrency limits; progress + cancellation.
- **WS/Redis fan-out complexity** → keep the hub small; test the relay with a fake broker; reconnect logic on the client (Phase 5).
- **Windows worker quirks** (Celery pool) → use a Windows-compatible pool (e.g., `solo`/`threads`) for local dev; Linux workers in compose/CI.
