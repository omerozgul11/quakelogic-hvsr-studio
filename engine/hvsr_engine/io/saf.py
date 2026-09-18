"""SESAME ASCII Format (SAF) reader.

Layout (SESAME deliverable, ``saf`` v. 1)::

    SESAME ASCII data format (saf) v. 1
    # free comments
    STA_CODE = ABC
    START_TIME = 2004 03 25 10 12 30.000
    SAMP_FREQ = 200
    NDAT = 120000
    CH0_ID = V
    CH1_ID = N
    CH2_ID = E
    UNITS = counts
    ####-------------------------------------------------------
      v0 n0 e0
      v1 n1 e1
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MAGIC = "SESAME ASCII DATA FORMAT"
SEPARATOR = "####"


def is_saf(path: str | Path) -> bool:
    try:
        with open(path, "rb") as fh:
            head = fh.read(200)
        return MAGIC in head.decode("latin-1", errors="replace").upper()
    except OSError:
        return False


def _parse_start(value: str | None) -> datetime | None:
    if not value:
        return None
    toks = re.split(r"[\s:/T-]+", value.strip())
    try:
        nums = [float(t) for t in toks if t != ""]
    except ValueError:
        return None
    if len(nums) < 6:
        return None
    y, mo, d, h, mi = (int(v) for v in nums[:5])
    sec = float(nums[5])
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc).replace(second=0) + __import__("datetime").timedelta(seconds=sec)


def read_saf(path: str | Path, header_only: bool = False) -> dict:
    p = Path(path)
    header: dict[str, str] = {}
    comments: list[str] = []
    data_start = None
    with open(p, "r", encoding="latin-1", errors="replace") as fh:
        lines = fh.readlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if i == 0 and MAGIC in s.upper():
            header["FORMAT"] = s
            continue
        if s.startswith(SEPARATOR):
            data_start = i + 1
            break
        if not s:
            continue
        if s.startswith("#"):
            comments.append(s.lstrip("# ").strip())
            continue
        if "=" in s:
            k, _, v = s.partition("=")
            header[k.strip().upper()] = v.strip()
    if data_start is None:
        raise ValueError("Not a SAF file: the '####' header separator was not found.")
    fs = float(header.get("SAMP_FREQ", 0) or 0)
    ndat = int(float(header.get("NDAT", 0) or 0))
    channels = [header.get(f"CH{i}_ID", "") for i in range(3)]
    start = _parse_start(header.get("START_TIME"))
    out = {"header": header, "comments": comments, "sample_rate": fs, "n_samples_declared": ndat,
           "start_time": start.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z" if start else None,
           "channels": channels, "station": header.get("STA_CODE", ""), "units": header.get("UNITS", "counts"),
           "data_start_line": data_start}
    if header_only:
        return out
    body = "".join(lines[data_start:])
    arr = np.loadtxt(__import__("io").StringIO(body), dtype=np.float64, ndmin=2)
    if arr.shape[1] < 3:
        raise ValueError(f"SAF data block has {arr.shape[1]} column(s); three channels are required.")
    out["data"] = arr[:, :3]
    out["n_samples"] = int(arr.shape[0])
    return out


def component_columns(channels: list[str]) -> dict[str, int]:
    """Map n/e/z to the SAF column index from the CHx_ID letters (V/Z → z, N → n, E → e)."""
    mapping: dict[str, int] = {}
    for idx, cid in enumerate(channels):
        c = (cid or "").strip().upper()
        if not c:
            continue
        last = c[-1]
        if last in ("Z", "V") and "z" not in mapping:
            mapping["z"] = idx
        elif last == "N" and "n" not in mapping:
            mapping["n"] = idx
        elif last == "E" and "e" not in mapping:
            mapping["e"] = idx
    if len(mapping) < 3 and len(channels) >= 3:
        # SESAME default order is V, N, E
        mapping = {"z": 0, "n": 1, "e": 2}
    return mapping
