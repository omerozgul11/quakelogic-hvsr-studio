from fastapi import APIRouter, Request

from ..errors import ServiceError

router = APIRouter(prefix="/jobs")


@router.get("")
def list_jobs(request: Request, limit: int = 50):
    return {"jobs": request.app.state.jobs.list(limit=limit)}


@router.get("/{job_id}")
def get_job(job_id: str, request: Request):
    job = request.app.state.jobs.get(job_id)
    if job is None:
        raise ServiceError("not_found", f"Unknown job {job_id}", 404)
    return job.to_dict()


@router.post("/{job_id}/cancel", status_code=200)
def cancel_job(job_id: str, request: Request):
    job = request.app.state.jobs.cancel(job_id)
    if job is None:
        raise ServiceError("not_found", f"Unknown job {job_id}", 404)
    return job.to_dict()
