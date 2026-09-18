"""Display helpers: min/max envelope downsampling for plotting.

Downsampling is ONLY used for the browser display; every scientific computation runs on
the full-resolution data. Responses always say whether they were downsampled.
"""
from __future__ import annotations

import numpy as np

from .io.canonical import Recording


def downsample_minmax(t: np.ndarray, v: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    """Keep the min and max sample of each bucket (in time order) so peaks are preserved."""
    t = np.asarray(t)
    v = np.asarray(v, dtype=np.float64)
    n = len(v)
    if max_points < 4 or n <= max_points:
        return t, v
    n_buckets = max_points // 2
    size = int(np.ceil(n / n_buckets))
    n_buckets = int(np.ceil(n / size))
    padded = np.full(n_buckets * size, np.nan)
    padded[:n] = v
    grid = padded.reshape(n_buckets, size)
    all_nan = np.all(np.isnan(grid), axis=1)
    grid_safe = np.where(np.isnan(grid), 0.0, grid)
    imin = np.argmin(np.where(np.isnan(grid), np.inf, grid_safe), axis=1)
    imax = np.argmax(np.where(np.isnan(grid), -np.inf, grid_safe), axis=1)
    base = np.arange(n_buckets) * size
    lo = np.minimum(imin, imax) + base
    hi = np.maximum(imin, imax) + base
    idx = np.empty(2 * n_buckets, dtype=np.int64)
    idx[0::2], idx[1::2] = lo, hi
    keep = np.repeat(~all_nan, 2)
    idx = np.clip(idx[keep], 0, n - 1)
    return t[idx], v[idx]


def recording_display(rec: Recording, t_start: float | None = None, t_end: float | None = None,
                      max_points: int = 4000, components=("n", "e", "z")) -> dict:
    t_start = 0.0 if t_start is None else max(0.0, float(t_start))
    t_end = rec.duration_s if t_end is None else min(rec.duration_s, float(t_end))
    i0 = int(np.floor(t_start * rec.fs))
    i1 = int(np.ceil(t_end * rec.fs)) + 1
    i0, i1 = max(0, i0), min(rec.n_samples, max(i0 + 1, i1))
    t = np.arange(i0, i1) / rec.fs
    n_source = i1 - i0
    out = {}
    n_display = 0
    downsampled = False
    for name in components:
        v = rec.component(name)[i0:i1]
        td, vd = downsample_minmax(t, v, int(max_points))
        downsampled = downsampled or len(vd) < len(v)
        n_display = max(n_display, len(vd))
        out[name] = {"t": np.round(td, 6).tolist(), "v": [None if np.isnan(x) else float(x) for x in vd]}
    return {
        "fs": rec.fs, "start_time": rec.start_time, "duration_s": rec.duration_s, "n_samples": rec.n_samples,
        "t_start": t_start, "t_end": t_end, "n_source": int(n_source),
        "downsampled": bool(downsampled), "n_display": int(n_display), "method": "minmax",
        "units": rec.meta.get("units", "counts"),
        "components": out,
    }
