import os

from fastapi import APIRouter

from .. import engine_api
from ..schemas import DirRequest
from ..summary import summarize

router = APIRouter(prefix="/analyses")


def _check(d: str) -> None:
    if not os.path.isfile(os.path.join(d, "result.json")):
        raise FileNotFoundError(f"No result.json in analysis directory: {d}")


@router.post("/load", status_code=200)
def load(req: DirRequest):
    _check(req.dir)
    return engine_api.load_result(req.dir)


@router.post("/window-curves", status_code=200)
def window_curves(req: DirRequest):
    _check(req.dir)
    return engine_api.window_curves(req.dir)


@router.post("/summary", status_code=200)
def summary(req: DirRequest):
    _check(req.dir)
    return summarize(engine_api.load_result(req.dir))
