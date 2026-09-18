import os

from fastapi import APIRouter, Request

from .. import engine_api
from ..jobs import Job
from ..schemas import AnalyzeRequest, SelectPeakRequest, WindowsRequest
from ..summary import summarize

router = APIRouter(prefix="/hvsr")


@router.post("/windows", status_code=200)
def windows(req: WindowsRequest, request: Request):
    rec = request.app.state.cache.load(req.input_path)
    return engine_api.screen_windows(rec, req.params, req.window_overrides)


@router.post("/analyze", status_code=200)
def analyze(req: AnalyzeRequest, request: Request):
    cache = request.app.state.cache
    cache.load(req.input_path)
    body = req.model_dump()

    def work(job: Job):
        rec = cache.load(body["input_path"])
        job.report(0.01, "loaded recording")
        result = engine_api.analyze(
            rec, body["params"], window_overrides=body.get("window_overrides"),
            manual_peak=body.get("manual_peak"), random_seed=body.get("random_seed"),
            progress=lambda f, m=None: job.report(0.01 + 0.9 * float(f), m), cancel=job.cancel_event,
            input_path=body["input_path"],
        )
        job.report(0.93, "writing results")
        os.makedirs(body["output_dir"], exist_ok=True)
        engine_api.write_result(result, body["output_dir"])
        result_dict = result.to_dict() if hasattr(result, "to_dict") else result
        return {"output_dir": body["output_dir"], "summary": summarize(result_dict)}

    job = request.app.state.jobs.submit("hvsr", work, {"input_path": req.input_path, "output_dir": req.output_dir})
    return job.to_dict()


@router.post("/select-peak", status_code=200)
def select_peak(req: SelectPeakRequest):
    if not os.path.isdir(req.analysis_dir):
        raise FileNotFoundError(f"Analysis directory not found: {req.analysis_dir}")
    result = engine_api.select_peak(req.analysis_dir, req.frequency)
    return {"result": result, "summary": summarize(result)}
