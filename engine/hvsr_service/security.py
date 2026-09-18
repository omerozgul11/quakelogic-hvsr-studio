"""HTTP middleware: optional shared-secret check (X-Engine-Token) and error envelope."""

from __future__ import annotations

import os

from fastapi import Request

from .errors import ServiceError, translate_exception

EXEMPT_PATHS = {"/health"}


def configured_token(explicit: str | None = None) -> str | None:
    token = explicit if explicit is not None else os.environ.get("HVSR_ENGINE_TOKEN", "")
    token = (token or "").strip()
    return token or None


async def token_middleware(request: Request, call_next):
    token = request.app.state.token
    if token and request.url.path not in EXEMPT_PATHS:
        supplied = request.headers.get("x-engine-token", "")
        if supplied != token:
            return ServiceError("unauthorized", "Missing or invalid X-Engine-Token header.", status=401).response()
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 - always answer with the error envelope
        return translate_exception(exc).response()
