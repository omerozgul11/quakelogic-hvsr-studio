"""Recording validation. Issues are reported, never silently repaired.

Severity: ``error`` blocks analysis, ``warning`` is shown to the user, ``info`` is advisory.
"""
from __future__ import annotations

import numpy as np

from .io.canonical import Recording

SHORT_RECORD_S = 180.0


def issue(code: str, severity: str, message: str, details: dict | None = None) -> dict:
    return {"code": code, "severity": severity, "message": message, "details": details or {}}


def is_blocking(issues: list[dict]) -> bool:
    return any(i["severity"] == "error" for i in issues)


def check_nan(name: str, x: np.ndarray) -> dict | None:
    bad = ~np.isfinite(x)
    if bad.any():
        first = int(np.flatnonzero(bad)[0])
        return issue("nan_values", "error",
                     f"Component {name.upper()} contains {int(bad.sum())} NaN/Inf sample(s) (first at index {first}). "
                     "Gaps are never interpolated; fix the source or crop the record.",
                     {"component": name, "count": int(bad.sum()), "first_index": first})
    return None


def check_constant(name: str, x: np.ndarray) -> dict | None:
    finite = x[np.isfinite(x)]
    if len(finite) == 0:
        return None
    if np.nanstd(finite) == 0:
        return issue("constant_channel", "error",
                     f"Component {name.upper()} is constant (value {finite[0]:g}); it carries no signal.",
                     {"component": name, "value": float(finite[0])})
    return None


def check_clipping(name: str, x: np.ndarray) -> dict | None:
    finite = x[np.isfinite(x)]
    if len(finite) < 100:
        return None
    m = float(np.max(np.abs(finite)))
    if m == 0:
        return None
    near = np.abs(finite) >= 0.999 * m
    count = int(near.sum())
    # clipping: many samples pinned at the extreme AND at least a short run of consecutive pinned samples
    runs = np.diff(np.flatnonzero(near))
    has_run = bool(len(runs) and np.any(runs == 1))
    if count >= max(10, 0.0005 * len(finite)) and has_run:
        return issue("clipping_suspected", "warning",
                     f"Component {name.upper()} has {count} samples pinned at ±{m:g}; the sensor or digitiser may have clipped.",
                     {"component": name, "count": count, "level": m, "fraction": count / len(finite)})
    return None


def validate_recording(rec: Recording) -> list[dict]:
    issues: list[dict] = []
    for name, x in rec.components().items():
        for check in (check_nan, check_constant, check_clipping):
            res = check(name, x)
            if res:
                issues.append(res)
    lengths = {len(rec.n), len(rec.e), len(rec.z)}
    if len(lengths) != 1:
        issues.append(issue("length_mismatch", "error", f"Component lengths differ: {sorted(lengths)} samples.",
                            {"lengths": {"n": len(rec.n), "e": len(rec.e), "z": len(rec.z)}}))
    if rec.fs <= 0 or not np.isfinite(rec.fs):
        issues.append(issue("no_timing_information", "error", "The sample rate is missing or invalid."))
    elif rec.duration_s < SHORT_RECORD_S:
        issues.append(issue("short_record", "warning",
                            f"The record is only {rec.duration_s:.0f} s long; ambient-noise HVSR normally needs ≥ {SHORT_RECORD_S:.0f} s "
                            "(SESAME recommends many windows of 10–60 s).", {"duration_s": rec.duration_s}))
    if rec.meta.get("unit_kind", "unknown") in ("unknown", None) or not rec.meta.get("units"):
        issues.append(issue("unit_unknown", "info", "Amplitude units are unknown; HVSR is unit-independent but spectra are shown in raw units."))
    if rec.meta.get("start_time_assumed"):
        issues.append(issue("start_time_assumed", "info", "No start time was supplied; 1970-01-01T00:00:00Z is used as a placeholder."))
    return issues


def check_regular_sampling(t_seconds: np.ndarray, rel_tol: float = 1e-3) -> tuple[float | None, list[dict]]:
    """Validate a time column. Returns (sample_rate or None, issues)."""
    issues: list[dict] = []
    t = np.asarray(t_seconds, dtype=np.float64)
    if len(t) < 2:
        return None, [issue("no_timing_information", "error", "Fewer than two time samples.")]
    if not np.all(np.isfinite(t)):
        return None, [issue("no_timing_information", "error", "The time column contains non-numeric values.")]
    dt = np.diff(t)
    dup = int(np.sum(dt == 0))
    if dup:
        first = int(np.flatnonzero(dt == 0)[0])
        issues.append(issue("duplicate_timestamps", "error", f"{dup} duplicate timestamp(s) (first at row {first + 1}).",
                            {"count": dup, "first_index": first}))
    if np.any(dt < 0):
        issues.append(issue("irregular_sampling", "error", "Timestamps are not monotonically increasing."))
        return None, issues
    med = float(np.median(dt))
    if med <= 0:
        return None, issues or [issue("no_timing_information", "error", "Cannot determine the sample interval.")]
    dev = np.abs(dt - med) / med
    bad = dev > rel_tol
    if bad.any():
        big = dt[bad]
        n_gaps = int(np.sum(big > med * 1.5))
        first = int(np.flatnonzero(bad)[0])
        code = "gaps" if n_gaps else "irregular_sampling"
        issues.append(issue(code, "error",
                            f"The time column is not regularly sampled: {int(bad.sum())} interval(s) deviate from the median "
                            f"{med:g} s by more than {rel_tol * 100:g} % (first at row {first + 1}, Δt = {dt[first]:g} s). "
                            "Gaps are never interpolated.",
                            {"count": int(bad.sum()), "first_index": first, "median_dt": med, "n_gaps": n_gaps}))
    return 1.0 / med, issues
