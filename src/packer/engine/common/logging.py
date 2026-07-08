from __future__ import annotations

import logging
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def bind_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


class _CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_correlation_id() or "-"
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(f, _CorrelationFilter) for f in logger.filters):
        logger.addFilter(_CorrelationFilter())
    return logger
