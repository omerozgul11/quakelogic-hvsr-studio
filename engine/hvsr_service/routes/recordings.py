from fastapi import APIRouter, Request

from .. import engine_api
from ..schemas import DataRequest, ImportRequest, SpectraRequest

router = APIRouter(prefix="/recordings")


@router.post("/import", status_code=200)
def import_recording(req: ImportRequest, request: Request):
    result = engine_api.import_recording(req.model_dump())
    request.app.state.cache.clear()
    return result


@router.post("/data", status_code=200)
def data(req: DataRequest, request: Request):
    rec = request.app.state.cache.load(req.path)
    return engine_api.recording_display(rec, t_start=req.t_start, t_end=req.t_end,
                                        max_points=req.max_points, components=tuple(req.components))


@router.post("/spectra", status_code=200)
def spectra(req: SpectraRequest, request: Request):
    rec = request.app.state.cache.load(req.path)
    params = req.model_dump()
    params.pop("path", None)
    return engine_api.compute_spectra(rec, params)
