from __future__ import annotations

from fastapi import FastAPI


def include_routers(app: FastAPI) -> None:
    from packer.api.routers import (  # lazy import avoids api<->workers cycles
        artifacts,
        detect,
        extract,
        jobs,
        models,
        pack,
        reports,
        scan,
        ws,
    )

    for module in (pack, detect, extract, scan, jobs, models, artifacts, reports, ws):
        app.include_router(module.router)
