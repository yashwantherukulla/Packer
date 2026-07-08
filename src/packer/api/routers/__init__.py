from __future__ import annotations

from fastapi import FastAPI


def include_routers(app: FastAPI) -> None:
    """Import routers lazily here (not at package import time) to avoid api<->workers import cycles."""
    return None
