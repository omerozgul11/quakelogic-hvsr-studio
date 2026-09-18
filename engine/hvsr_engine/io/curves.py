"""Import/export of H/V curves as Geopsy ``.hv`` text files and plain delimited tables."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np

_NUM = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def write_hv(path: str | Path, frequency, average, lower=None, upper=None, name: str = "", header_lines=None) -> str:
    """Write a Geopsy-compatible ``.hv`` file: ``#`` comment header, then ``frequency average min max``."""
    path = Path(path)
    freq = np.asarray(frequency, dtype=np.float64)
    avg = np.asarray([np.nan if v is None else v for v in average], dtype=np.float64)
    lo = None if lower is None else np.asarray([np.nan if v is None else v for v in lower], dtype=np.float64)
    hi = None if upper is None else np.asarray([np.nan if v is None else v for v in upper], dtype=np.float64)
    lines = ["# GEOPSY output version 1.1 (written by QuakeLogic HVSR Studio)"]
    if name:
        lines.append(f"# {name}")
    for h in header_lines or []:
        lines.append(f"# {h}")
    lines.append("# min and max columns are the dispersion band of the window curves (not a confidence interval)")
    lines.append("# Frequency\tAverage\tMin\tMax")
    for i, f in enumerate(freq):
        a = avg[i]
        if not np.isfinite(a):
            continue
        l_ = lo[i] if lo is not None and np.isfinite(lo[i]) else a
        u_ = hi[i] if hi is not None and np.isfinite(hi[i]) else a
        lines.append(f"{f:.6g}\t{a:.6g}\t{l_:.6g}\t{u_:.6g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def read_curve_file(path: str | Path) -> dict:
    """Read a Geopsy ``.hv`` file or a 2–4 column delimited table (frequency, value[, lower, upper])."""
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    rows = []
    fmt = "geopsy_hv" if p.suffix.lower() == ".hv" or "GEOPSY" in text[:200].upper() else "csv"
    name = p.stem
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith("%"):
            if fmt == "geopsy_hv" and "GEOPSY" not in s.upper() and len(rows) == 0 and name == p.stem:
                cand = s.lstrip("#% ").strip()
                if cand and not cand.lower().startswith(("frequency", "min and max", "number", "f0", "peak")):
                    name = cand[:80]
            continue
        toks = [t for t in re.split(r"[,\t; ]+", s) if t != ""]
        if len(toks) < 2:
            continue
        if not all(_NUM.match(t) for t in toks[:2]):
            continue  # header row
        vals = [float(t) for t in toks[:4] if _NUM.match(t)]
        rows.append(vals)
    if len(rows) < 2:
        raise ValueError(f"{p.name}: no numeric frequency/value rows were found.")
    ncol = min(len(r) for r in rows)
    arr = np.array([r[:ncol] for r in rows], dtype=np.float64)
    order = np.argsort(arr[:, 0])
    arr = arr[order]
    out = {"frequency": arr[:, 0].tolist(), "values": arr[:, 1].tolist(), "lower": None, "upper": None,
           "name": name, "format": fmt, "n_points": int(arr.shape[0]), "source": p.name}
    if ncol >= 4:
        out["lower"], out["upper"] = arr[:, 2].tolist(), arr[:, 3].tolist()
    return out
