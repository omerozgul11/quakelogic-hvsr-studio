"""Nan-aware aggregation of per-window curves (dispersion bands, never confidence intervals)."""
from __future__ import annotations

import numpy as np


def _valid_count(curves: np.ndarray) -> np.ndarray:
    return np.sum(np.isfinite(curves), axis=0)


def aggregate(curves: np.ndarray, method: str, min_valid: int = 1) -> dict:
    """Aggregate an (n_windows, n_freq) array along the window axis.

    Returns ``values``, ``lower``, ``upper`` (NaN where fewer than ``min_valid`` windows are
    valid), the ``band`` definition string and, for the geometric method, ``sigma_ln``.
    """
    curves = np.asarray(curves, dtype=np.float64)
    if curves.ndim != 2:
        raise ValueError("curves must be 2-D (windows × frequency)")
    count = _valid_count(curves)
    enough = count >= max(1, min_valid)
    out = {"n_valid": count.astype(int).tolist()}
    with np.errstate(all="ignore"):
        if method == "geometric":
            logs = np.log(np.where(curves > 0, curves, np.nan))
            mu = np.nanmean(logs, axis=0)
            sd = _nanstd(logs)
            values, lower, upper = np.exp(mu), np.exp(mu - sd), np.exp(mu + sd)
            out["sigma_ln"] = sd
            out["band"] = "exp(mean(ln HV) ± std(ln HV, ddof=1)) — log-normal ±1σ dispersion band"
        elif method == "arithmetic":
            values = np.nanmean(curves, axis=0)
            sd = _nanstd(curves)
            lower, upper = values - sd, values + sd
            out["band"] = "mean(HV) ± std(HV, ddof=1) — ±1σ dispersion band"
        elif method == "median":
            values = np.nanmedian(curves, axis=0)
            lower = np.nanpercentile(curves, 16, axis=0)
            upper = np.nanpercentile(curves, 84, axis=0)
            out["band"] = "16th–84th percentile of the window curves"
        else:
            raise ValueError(f"Unknown mean method: {method}")
    for key, arr in (("values", values), ("lower", lower), ("upper", upper)):
        arr = np.array(arr, dtype=np.float64)
        arr[~enough] = np.nan
        out[key] = arr
    if "sigma_ln" in out:
        s = np.array(out["sigma_ln"], dtype=np.float64)
        s[~enough] = np.nan
        out["sigma_ln"] = s
    return out


def _nanstd(a: np.ndarray) -> np.ndarray:
    """Sample standard deviation (ddof=1) ignoring NaN; NaN where < 2 valid values."""
    count = np.sum(np.isfinite(a), axis=0)
    with np.errstate(all="ignore"):
        sd = np.nanstd(a, axis=0, ddof=1)
    sd = np.where(count >= 2, sd, np.nan)
    return sd


def summarize_values(values: np.ndarray) -> dict:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return {"n": 0, "median": None, "p16": None, "p84": None, "std": None, "std_ln": None, "mean": None}
    out = {
        "n": int(len(v)), "mean": float(np.mean(v)), "median": float(np.median(v)),
        "p16": float(np.percentile(v, 16)), "p84": float(np.percentile(v, 84)),
        "std": float(np.std(v, ddof=1)) if len(v) > 1 else None,
        "std_ln": float(np.std(np.log(v[v > 0]), ddof=1)) if np.sum(v > 0) > 1 else None,
    }
    return out
