"""Licence status and installation (offline, signed .qlicense files)."""

from fastapi import APIRouter, File, Request, UploadFile

from ..errors import ServiceError
from ..licensing import MAX_FILE

router = APIRouter(prefix="/license")


@router.get("", status_code=200)
def status(request: Request):
    return request.app.state.licensing.status()


@router.post("", status_code=200)
def install(request: Request, file: UploadFile = File(...)):
    content = file.file.read(MAX_FILE + 1)
    try:
        return request.app.state.licensing.install(content)
    except ValueError as exc:
        raise ServiceError("invalid_license", str(exc), 422) from None
