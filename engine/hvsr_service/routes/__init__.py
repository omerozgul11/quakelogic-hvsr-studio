from fastapi import FastAPI

from . import analyses, curves, exports, files, health, hvsr, jobs, modelling, processing, recordings


def register(app: FastAPI) -> None:
    for module in (health, files, recordings, processing, hvsr, analyses, exports, jobs, modelling, curves):
        app.include_router(module.router)
