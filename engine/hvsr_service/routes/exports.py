import os

from fastapi import APIRouter, Request

from .. import engine_api
from ..jobs import Job
from ..schemas import FigureRequest, ReportRequest

router = APIRouter(prefix="/exports")


def _recording_for(request: Request, analysis_dir: str, explicit: str | None):
    """Resolve the waveform used by an analysis: explicit path, else result.input.path."""
    path = explicit
    if not path:
        try:
            path = (engine_api.load_result(analysis_dir).get("input") or {}).get("path")
        except Exception:
            path = None
    if path and os.path.isfile(path):
        return request.app.state.cache.load(path)
    return None


@router.post("/figure", status_code=200)
def figure(req: FigureRequest, request: Request):
    if not os.path.isfile(os.path.join(req.analysis_dir, "result.json")):
        raise FileNotFoundError(f"No result.json in analysis directory: {req.analysis_dir}")
    result = engine_api.load_result(req.analysis_dir)
    rec = _recording_for(request, req.analysis_dir, req.recording_path) if req.figure == "windows" else None
    window_curves = None
    if req.figure == "hvsr":
        try:
            window_curves = engine_api.window_curves(req.analysis_dir)
        except Exception:
            window_curves = None
    path = engine_api.figure(result, req.figure, req.format, req.output_path, recording=rec, theme=req.theme,
                             window_curves=window_curves)
    return {"output_path": path}


@router.post("/report", status_code=200)
def report(req: ReportRequest, request: Request):
    if not os.path.isfile(os.path.join(req.analysis_dir, "result.json")):
        raise FileNotFoundError(f"No result.json in analysis directory: {req.analysis_dir}")
    body = req.model_dump()

    def work(job: Job):
        result = engine_api.load_result(body["analysis_dir"])
        rec = _recording_for(request, body["analysis_dir"], body.get("recording_path"))
        job.report(0.05, "building report")
        path = engine_api.build_report(result, body["context"], body["output_path"], body["analysis_dir"],
                                       recording=rec, progress=lambda f, m=None: job.report(0.05 + 0.9 * float(f), m))
        return {"output_path": path}

    job = request.app.state.jobs.submit("report", work, {"analysis_dir": req.analysis_dir, "output_path": req.output_path})
    return job.to_dict()
