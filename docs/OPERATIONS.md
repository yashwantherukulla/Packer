# Operations

## Run the stack
- Full: `docker compose -f docker/compose.yml up --build` (add `--profile gpu` for the GPU worker).
- Dev: `docker compose -f docker/compose.yml -f docker/compose.dev.yml up --build`.
- API + OpenAPI docs: http://localhost:8000/docs · Frontend: http://localhost:5173.

## Configure (Hydra + env)
- All settings compose from `conf/` (ADR-012). Override at run time with env interpolation:
  `PACKER_DB_DSN`, `PACKER_REDIS_URL`, `PACKER_STORE_ROOT` (object-store root), `PACKER_RUN_DIR`.
- Engine/training knobs via Hydra groups, e.g. `engine/pack=e2e_tiny engine/pack.device=cuda`.

## Migrations
- The api container runs `alembic upgrade head` on startup (ADR-014). To migrate manually:
  `docker compose exec api alembic upgrade head`.

## Back up the object store
- Artifacts live in the `artifacts` volume (`/data/artifacts`). Back up with
  `docker run --rm -v packer_artifacts:/data -v "$PWD:/backup" busybox tar czf /backup/artifacts.tgz /data`.
- Postgres: `docker compose exec postgres pg_dump -U packer packer > backup.sql`.

## Read logs (correlation ids)
- Structured JSON logs carry a `correlation_id` = job id (SYSTEM-DESIGN §7). Trace one job:
  `docker compose logs api worker-default | grep <job-id>`.
