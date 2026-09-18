"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import SERVICE_VERSION
from .cache import RecordingCache
from .errors import install_handlers
from .jobs import JobManager
from .routes import register
from .security import configured_token, token_middleware


def create_app(workers: int | None = None, token: str | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.jobs.shutdown()

    app = FastAPI(title="QuakeLogic HVSR Studio engine service", version=SERVICE_VERSION,
                  docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.state.jobs = JobManager(max_workers=workers)
    app.state.cache = RecordingCache()
    app.state.token = configured_token(token)
    app.middleware("http")(token_middleware)
    install_handlers(app)
    register(app)
    return app
