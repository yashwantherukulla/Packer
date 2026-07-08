# syntax=docker/dockerfile:1
FROM python:3.10-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
WORKDIR /app

# 1) deps only (cache layer) — no project, no dev group
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2) project source + config + migrations
COPY src ./src
COPY conf ./conf
COPY alembic ./alembic
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

EXPOSE 8000
# migrate-on-startup (ADR-014), then serve.
# NB: packer.api.main exposes a create_app() factory (not a module-level `app`),
# so uvicorn is invoked with --factory rather than the plan's `main:app`.
CMD ["sh", "-c", "alembic upgrade head && uvicorn packer.api.main:create_app --factory --host 0.0.0.0 --port 8000"]
