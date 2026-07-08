from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from packer.engine.common.errors import PackerError

_STATUS_BY_CODE = {
    "unsafe_model": 422,
    "config_error": 400,
    "load_error": 422,
}


def code_to_status(code: str) -> int:
    return _STATUS_BY_CODE.get(code, 500)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PackerError)
    async def _handle_packer_error(_: Request, exc: PackerError) -> JSONResponse:
        status = code_to_status(exc.code)
        return JSONResponse(
            status_code=status,
            content={
                "type": f"https://packer.dev/errors/{exc.code}",
                "title": exc.__class__.__name__,
                "status": status,
                "code": exc.code,
                "detail": str(exc),
            },
            media_type="application/problem+json",
        )
