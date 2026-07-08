from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from omegaconf import DictConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packer.api.errors import register_error_handlers
from packer.api.routers import include_routers
from packer.api.settings import load_settings
from packer.api.ws.hub import ProgressHub


def create_app(settings: DictConfig | None = None) -> FastAPI:
    settings = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.db.dsn, pool_size=settings.db.pool_size, future=True)
        app.state.session_factory = sessionmaker(engine, expire_on_commit=False, future=True)
        app.state.redis = aioredis.from_url(settings.broker.url, decode_responses=True)
        app.state.hub = ProgressHub(app.state.redis, prefix=settings.broker.progress_prefix)
        try:
            yield
        finally:
            await app.state.redis.aclose()
            engine.dispose()

    app = FastAPI(title="Packer API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    register_error_handlers(app)
    include_routers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
