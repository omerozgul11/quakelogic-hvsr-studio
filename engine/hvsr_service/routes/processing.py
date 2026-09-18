from fastapi import APIRouter, Request

from .. import engine_api
from ..jobs import Job
from ..schemas import FilterResponseRequest, PreviewRequest, RunRequest

router = APIRouter(prefix="/processing")


@router.post("/preview", status_code=200)
def preview(req: PreviewRequest, request: Request):
    rec = request.app.state.cache.load(req.input_path)
    processed, warnings, applied = engine_api.apply_steps(rec, req.steps)
    kwargs = dict(t_start=req.t_start, t_end=req.t_end, max_points=req.max_points)
    return {
        "raw": engine_api.recording_display(rec, **kwargs),
        "processed": engine_api.recording_display(processed, **kwargs),
        "warnings": warnings,
        "applied": applied,
        "fs_out": float(processed.fs),
    }


@router.post("/run", status_code=200)
def run(req: RunRequest, request: Request):
    cache = request.app.state.cache
    input_path, output_path, steps = req.input_path, req.output_path, req.steps
    cache.load(input_path)  # raises 404 early if missing

    def work(job: Job):
        rec = cache.load(input_path)
        job.report(0.02, "loading")

        def progress(frac, msg=None):
            if job.cancel_event.is_set():
                from hvsr_engine.errors import CancelledError

                raise CancelledError()
            job.report(0.02 + 0.9 * float(frac), msg)

        processed, warnings, applied = engine_api.apply_steps(rec, steps, progress=progress)
        if job.cancel_event.is_set():
            from hvsr_engine.errors import CancelledError

            raise CancelledError()
        processed.meta = dict(processed.meta or {})
        processed.meta["steps"] = applied
        processed.meta["parent"] = input_path
        meta = engine_api.save_recording(processed, output_path)
        job.report(1.0, "written")
        return {"output_path": output_path, "meta": meta, "warnings": warnings, "applied": applied}

    job = request.app.state.jobs.submit("processing", work, {"input_path": input_path, "output_path": output_path})
    return job.to_dict()


@router.post("/filter-response", status_code=200)
def filter_response(req: FilterResponseRequest):
    return engine_api.filter_response(req.fs, req.step, n_points=req.n_points)
