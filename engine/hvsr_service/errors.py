"""Error envelope shared by every route: {"error": {"code", "message", "details"}}."""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("hvsr_service")


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}

    def response(self) -> JSONResponse:
        return JSONResponse(status_code=self.status,
                            content={"error": {"code": self.code, "message": self.message, "details": self.details}})


def translate_exception(exc: BaseException) -> ServiceError:
    """Map engine / builtin exceptions to the error envelope."""
    if isinstance(exc, ServiceError):
        return exc
    try:
        from hvsr_engine.errors import CancelledError, EngineError
    except Exception:  # pragma: no cover - engine missing
        CancelledError = EngineError = ()  # type: ignore
    if EngineError and isinstance(exc, CancelledError):
        return ServiceError("cancelled", str(exc), 409)
    if isinstance(exc, FileNotFoundError):
        return ServiceError("not_found", str(exc), 404)
    if EngineError and isinstance(exc, EngineError):
        # any engine rejection (import, processing, filter design, parameters) is a 422
        return ServiceError(getattr(exc, "code", "engine_error"), getattr(exc, "message", str(exc)), 422,
                            getattr(exc, "details", None))
    if isinstance(exc, (ValueError, KeyError, TypeError)):
        return ServiceError("invalid_parameters", str(exc), 422)
    if isinstance(exc, ImportError):
        return ServiceError("engine_unavailable", f"Engine module missing: {exc}", 500)
    log.error("Unhandled error: %s\n%s", exc, traceback.format_exc())
    return ServiceError("internal_error", f"{type(exc).__name__}: {exc}", 500)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError):
        return exc.response()

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return ServiceError("invalid_request", "Request body failed validation.", 422,
                            {"errors": exc.errors()}).response()

    @app.exception_handler(Exception)
    async def _any(_: Request, exc: Exception):
        return translate_exception(exc).response()
