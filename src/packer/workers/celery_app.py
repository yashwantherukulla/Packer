from __future__ import annotations

from celery import Celery
from omegaconf import DictConfig

from packer.engine.common.config_schema import compose_config


def make_celery(cfg: DictConfig | None = None) -> Celery:
    cfg = cfg if cfg is not None else compose_config()
    app = Celery("packer", broker=cfg.broker.url, backend=cfg.broker.result_backend)
    app.conf.task_default_queue = "default"
    app.conf.task_routes = {
        "pack.run": {"queue": "gpu"},  # GPU-pinned training (spec §4)
        "detect.run": {"queue": "default"},
        "extract.run": {"queue": "default"},
        "scan.run": {"queue": "default"},
    }
    app.conf.task_always_eager = bool(cfg.broker.get("eager", False))
    app.conf.worker_pool = "solo"  # Windows-safe local dev (spec §9); Linux workers override
    return app


app = make_celery()
