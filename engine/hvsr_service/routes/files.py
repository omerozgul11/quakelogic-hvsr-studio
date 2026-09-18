import os

from fastapi import APIRouter

from .. import engine_api
from ..schemas import InspectRequest

router = APIRouter(prefix="/files")


@router.post("/inspect", status_code=200)
def inspect(req: InspectRequest):
    if not os.path.isfile(req.path):
        raise FileNotFoundError(f"File not found: {req.path}")
    return engine_api.inspect_file(req.path)
