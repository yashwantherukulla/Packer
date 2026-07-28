# syntax=docker/dockerfile:1
# CPU-only worker image. Same runtime as docker/worker.Dockerfile, but built WITHOUT
# CUDA (see docker/api.cpu.Dockerfile for the how/why — non-torch deps from the frozen
# lock, then torch from the CPU index). No nvidia-*/cuda-*/triton wheels, no NVIDIA
# driver needed. pyproject.toml/uv.lock are untouched; the `gpu` profile still uses the
# CUDA worker.Dockerfile. Selected via docker/compose.cpu.yml, which also overrides the
# command so this worker drains BOTH the default and gpu queues.
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
 && uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/req.txt \
 && grep -vE '^(cuda-|nvidia-|triton==|torch==)' /tmp/req.txt > /tmp/req.cpu.txt \
 && uv pip install -r /tmp/req.cpu.txt \
 && TORCH_SPEC="$(grep -E '^torch==' /tmp/req.txt)" \
 && uv pip install "$TORCH_SPEC" --torch-backend=cpu

# Editable install (-e) so `packer` resolves to /app/src/packer and config_schema.py's
# Path(__file__).parents[4] lands on /app (where conf/ is copied). See api.cpu.Dockerfile.
COPY src ./src
COPY conf ./conf
COPY README.md ./
RUN --mount=type=cache,id=packer-worker-uv,target=/root/.cache/uv,sharing=locked uv pip install --no-deps -e .

# -Q is overridden by compose.cpu.yml (default,gpu). Celery app lives in packer.workers.celery_app.
CMD ["celery", "-A", "packer.workers.celery_app", "worker", "-Q", "default", "--loglevel=info"]
