import platform

from fastapi import APIRouter, Request

from .. import SERVICE_VERSION
from .. import engine_api

router = APIRouter()


@router.get("/health")
def health(request: Request):
    try:
        versions = engine_api.versions()
        engine_version = engine_api.engine_version()
        status = "ok"
    except Exception as exc:  # engine not importable
        versions, engine_version, status = {"error": str(exc)}, None, "degraded"
    jm = request.app.state.jobs
    return {
        "status": status,
        "service_version": SERVICE_VERSION,
        "engine_version": engine_version,
        "python": platform.python_version(),
        "versions": versions,
        "workers": jm.max_workers,
        "jobs_running": jm.running,
    }
