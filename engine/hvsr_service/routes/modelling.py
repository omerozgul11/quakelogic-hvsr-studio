from fastapi import APIRouter

from .. import engine_api
from ..schemas import ModelRequest

router = APIRouter(prefix="/model")


@router.post("/hvsr", status_code=200)
def model_hvsr(req: ModelRequest):
    return engine_api.model_hvsr(req.layers, req.freq_min, req.freq_max, req.n_freq, req.vs30_offset_m)
