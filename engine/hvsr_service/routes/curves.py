import os

from fastapi import APIRouter

from .. import engine_api
from ..schemas import CurveImportRequest

router = APIRouter(prefix="/curves")


@router.post("/import", status_code=200)
def import_curve(req: CurveImportRequest):
    if not os.path.isfile(req.path):
        raise FileNotFoundError(f"File not found: {req.path}")
    return engine_api.read_curve_file(req.path)
