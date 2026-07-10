# syntax=docker/dockerfile:1
# CPU-only API image. Same runtime as docker/api.Dockerfile, but the environment is
# built WITHOUT CUDA: every non-torch dependency is installed from the frozen uv.lock
# pins (via `uv export`), then PyTorch is installed from the CPU index
# (`--torch-backend=cpu`). No nvidia-*/cuda-*/triton wheels are ever downloaded, so the
# image is a few GB smaller and needs no NVIDIA driver.
#
# This does NOT touch pyproject.toml or uv.lock — the default (CUDA) images and the
# `gpu` profile are unchanged. Selected via docker/compose.cpu.yml; see its header.
FROM python:3.10-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/
WORKDIR /app

# 1) deps only (cache layer): all locked pins EXCEPT torch + CUDA, then CPU-only torch.
#    The grep drops torch and every nvidia-*/cuda-*/triton wheel; `--torch-backend=cpu`
#    then pulls torch==<locked>+cpu (a ~10-package tree, no CUDA) from the PyTorch index.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv "$VIRTUAL_ENV" \
 && uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/req.txt \
 && grep -vE '^(cuda-|nvidia-|triton==|torch==)' /tmp/req.txt > /tmp/req.cpu.txt \
 && uv pip install -r /tmp/req.cpu.txt \
 && TORCH_SPEC="$(grep -E '^torch==' /tmp/req.txt)" \
 && uv pip install "$TORCH_SPEC" --torch-backend=cpu

# 2) project source + config + migrations (README needed for the wheel metadata build)
# Editable install (-e) so `packer` resolves to /app/src/packer: config_schema.py locates
# conf/ via Path(__file__).parents[4], which must land on /app (where conf/ is copied).
# A non-editable wheel would anchor that path inside .venv and break Hydra config loading.
COPY src ./src
COPY conf ./conf
COPY alembic ./alembic
COPY alembic.ini ./
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --no-deps -e .

EXPOSE 8000
# migrate-on-startup (ADR-014), then serve (create_app factory — see docker/api.Dockerfile).
CMD ["sh", "-c", "alembic upgrade head && uvicorn packer.api.main:create_app --factory --host 0.0.0.0 --port 8000"]
