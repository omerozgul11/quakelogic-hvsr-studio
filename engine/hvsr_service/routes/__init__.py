from fastapi import FastAPI

from . import analyses, curves, exports, files, health, hvsr, jobs, license, modelling, processing, recordings


def register(app: FastAPI) -> None:
    for module in (health, files, recordings, processing, hvsr, analyses, exports, jobs, modelling, curves, license):
        app.include_router(module.router)
