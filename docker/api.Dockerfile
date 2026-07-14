# syntax=docker/dockerfile:1
FROM python:3.10-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
WORKDIR /app

# 1) deps only (cache layer) — no project, no dev group
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv "$VIRTUAL_ENV" \
 && uv sync --frozen --no-dev --no-install-project

# 2) project source + config + migrations
# Editable install keeps `packer` rooted at /app/src/packer so config loading
# still resolves the copied /app/conf tree inside the container.
COPY src ./src
COPY conf ./conf
COPY alembic ./alembic
COPY alembic.ini ./
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --no-deps -e .

EXPOSE 8000
# migrate-on-startup (ADR-014), then serve.
# NB: packer.api.main exposes a create_app() factory (not a module-level `app`),
# so uvicorn is invoked with --factory rather than the plan's `main:app`.
CMD ["sh", "-c", "alembic upgrade head && uvicorn packer.api.main:create_app --factory --host 0.0.0.0 --port 8000"]
