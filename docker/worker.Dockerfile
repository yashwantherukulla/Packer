# syntax=docker/dockerfile:1
FROM python:3.10-slim AS runtime
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
# docker CLI so the worker can drive the sandbox via the mounted /var/run/docker.sock
RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=packer-worker-uv,target=/root/.cache/uv,sharing=locked \
    uv venv "$VIRTUAL_ENV" \
 && uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY conf ./conf
COPY README.md ./
RUN --mount=type=cache,id=packer-worker-uv,target=/root/.cache/uv,sharing=locked uv pip install --no-deps -e .
# -Q is overridden per service in compose (default vs gpu).
# NB: the Celery app instance lives in packer.workers.celery_app (not packer.workers.app).
CMD ["celery", "-A", "packer.workers.celery_app", "worker", "-Q", "default", "--loglevel=info"]
