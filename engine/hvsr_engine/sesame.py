"""SESAME (2004) reliability and clear-peak criteria.

Reference: SESAME European research project (2004). Guidelines for the implementation of
the H/V spectral ratio technique on ambient vibrations — measurements, processing and
interpretation. WP12 – Deliverable D23.12, European Commission – Research General
Directorate, Project No. EVG1-CT-2000-00026 SESAME, December 2004, Appendix A ("Criteria
for a reliable H/V curve" and "Criteria for a clear H/V peak").

Notation: f0 = peak frequency, A0 = H/V amplitude at f0, l_w = window length (s),
n_w = number of windows used, n_c = l_w · n_w · f0 = number of significant cycles,
σ_A(f) = multiplicative standard deviation = exp(σ_ln HV(f)) (the factor by which the
mean curve is multiplied or divided), σ_f = standard deviation of the window peak
frequencies, ε(f0) and θ(f0) = threshold values from Table 1 of the guidelines.

All criteria are evaluated on the geometric (log) mean curve and its log standard
deviation, independent of the display mean selected by the user.
"""
from __future__ import annotations

import numpy as np

from .peaks import find_candidates

REFERENCE = ("SESAME (2004). Guidelines for the implementation of the H/V spectral ratio technique on "
             "ambient vibrations: measurements, processing and interpretation. SESAME European research "
             "project, WP12 – Deliverable D23.12, Project No. EVG1-CT-2000-00026, December 2004.")

# (upper bound of f0 range [Hz], ε factor, θ (multiplicative), log10 θ)
THRESHOLD_TABLE = [
    (0.2, 0.25, 3.0, 0.48),
    (0.5, 0.20, 2.5, 0.40),
    (1.0, 0.15, 2.0, 0.30),
    (2.0, 0.10, 1.78, 0.25),
    (np.inf, 0.05, 1.58, 0.20),
]


def thresholds(f0: float) -> dict:
    for upper, eps, theta, log_theta in THRESHOLD_TABLE:
        if f0 < upper or upper is np.inf:
            return {"epsilon_factor": eps, "theta": theta, "log10_theta": log_theta}
    return {"epsilon_factor": 0.05, "theta": 1.58, "log10_theta": 0.20}


def _nearest_local_max(freq: np.ndarray, curve: np.ndarray, f0: float, fmin: float, fmax: float) -> float:
    """Frequency of the local maximum of ``curve`` closest (in log f) to f0 within [fmin, fmax]."""
    cands = find_candidates(freq, curve, fmin, fmax)
    if not cands:
        return np.nan
    return min(cands, key=lambda c: abs(np.log(c["frequency"] / f0)))["frequency"]


def evaluate(freq: np.ndarray, mean_curve: np.ndarray, sigma_ln: np.ndarray, f0: float | None, a0: float | None,
             window_length_s: float, n_windows: int, window_f0: np.ndarray, search_range: tuple[float, float]) -> dict:
    freq = np.asarray(freq, dtype=np.float64)
    mean_curve = np.asarray(mean_curve, dtype=np.float64)
    sigma_ln = np.asarray(sigma_ln, dtype=np.float64)
    out = {"reference": REFERENCE, "f0": f0, "a0": a0, "window_length_s": window_length_s, "n_windows": n_windows,
           "reliability": [], "clarity": [], "reliability_passed": False, "clarity_passed_count": 0,
           "clarity_passed": False, "evaluated": False,
           "note": "Evaluated on the geometric (log) mean curve; σ_A(f) = exp(std(ln HV))."}
    if f0 is None or a0 is None or not np.isfinite(f0) or not np.isfinite(a0) or n_windows < 1:
        out["message"] = "Not evaluated: no selected peak or no accepted windows."
        return out
    th = thresholds(f0)
    out["thresholds"] = th
    with np.errstate(all="ignore"):
        sigma_a = np.exp(sigma_ln)
    i0 = int(np.argmin(np.abs(freq - f0)))

    # ---- reliability -------------------------------------------------------
    r1_thr = 10.0 / window_length_s
    out["reliability"].append({
        "id": "R1", "label": "f0 > 10 / l_w", "value": f0, "threshold": r1_thr, "passed": bool(f0 > r1_thr),
        "detail": f"f0 = {f0:.3g} Hz vs 10 / {window_length_s:g} s = {r1_thr:.3g} Hz"})
    nc = window_length_s * n_windows * f0
    out["reliability"].append({
        "id": "R2", "label": "n_c(f0) = l_w · n_w · f0 > 200", "value": nc, "threshold": 200.0, "passed": bool(nc > 200),
        "detail": f"{window_length_s:.4g} s (mean window length) × {n_windows} windows × {f0:.3g} Hz = {nc:.0f} cycles"})
    band = (freq > 0.5 * f0) & (freq < 2.0 * f0) & np.isfinite(sigma_a)
    r3_thr = 2.0 if f0 > 0.5 else 3.0
    r3_val = float(np.max(sigma_a[band])) if band.any() else np.nan
    out["reliability"].append({
        "id": "R3", "label": "σ_A(f) < 2 for 0.5f0 < f < 2f0 if f0 > 0.5 Hz (σ_A(f) < 3 if f0 < 0.5 Hz)",
        "value": r3_val, "threshold": r3_thr, "passed": bool(np.isfinite(r3_val) and r3_val < r3_thr),
        "detail": f"max σ_A over [{0.5 * f0:.3g}, {2 * f0:.3g}] Hz = {r3_val:.3g}" if np.isfinite(r3_val)
        else "σ_A not defined in the band (too few valid windows)"})

    # ---- clarity -----------------------------------------------------------
    left = (freq >= f0 / 4.0) & (freq < f0) & np.isfinite(mean_curve)
    c1_val = float(np.min(mean_curve[left])) if left.any() else np.nan
    out["clarity"].append({
        "id": "C1", "label": "∃ f⁻ ∈ [f0/4, f0] : A_H/V(f⁻) < A0/2", "value": c1_val, "threshold": a0 / 2.0,
        "passed": bool(np.isfinite(c1_val) and c1_val < a0 / 2.0),
        "detail": f"min A over [{f0 / 4:.3g}, {f0:.3g}] Hz = {c1_val:.3g} vs A0/2 = {a0 / 2:.3g}"})
    right = (freq > f0) & (freq <= 4.0 * f0) & np.isfinite(mean_curve)
    c2_val = float(np.min(mean_curve[right])) if right.any() else np.nan
    out["clarity"].append({
        "id": "C2", "label": "∃ f⁺ ∈ [f0, 4f0] : A_H/V(f⁺) < A0/2", "value": c2_val, "threshold": a0 / 2.0,
        "passed": bool(np.isfinite(c2_val) and c2_val < a0 / 2.0),
        "detail": f"min A over [{f0:.3g}, {4 * f0:.3g}] Hz = {c2_val:.3g} vs A0/2 = {a0 / 2:.3g}"
        + ("" if right.any() else " (band exceeds the analysed range)")})
    out["clarity"].append({
        "id": "C3", "label": "A0 > 2", "value": a0, "threshold": 2.0, "passed": bool(a0 > 2.0),
        "detail": f"A0 = {a0:.3g}"})
    with np.errstate(all="ignore"):
        upper_curve = mean_curve * sigma_a
        lower_curve = mean_curve / sigma_a
    fmin_c4, fmax_c4 = max(search_range[0], f0 / 2.0), min(search_range[1], f0 * 2.0)
    f_up = _nearest_local_max(freq, upper_curve, f0, fmin_c4, fmax_c4)
    f_lo = _nearest_local_max(freq, lower_curve, f0, fmin_c4, fmax_c4)
    dev = max(abs(f_up - f0), abs(f_lo - f0)) / f0 if np.isfinite(f_up) and np.isfinite(f_lo) else np.nan
    out["clarity"].append({
        "id": "C4", "label": "f_peak[A_H/V(f) ± σ_A(f)] = f0 ± 5 %", "value": dev, "threshold": 0.05,
        "passed": bool(np.isfinite(dev) and dev <= 0.05),
        "detail": (f"peak of mean×σ_A at {f_up:.3g} Hz, of mean/σ_A at {f_lo:.3g} Hz; max deviation {100 * dev:.1f} %"
                   if np.isfinite(dev) else "no local maximum of the ±σ_A curves near f0")})
    wf = np.asarray(window_f0, dtype=np.float64)
    wf = wf[np.isfinite(wf)]
    sigma_f = float(np.std(wf, ddof=1)) if len(wf) > 1 else np.nan
    eps = th["epsilon_factor"] * f0
    out["clarity"].append({
        "id": "C5", "label": "σ_f < ε(f0)", "value": sigma_f, "threshold": eps,
        "passed": bool(np.isfinite(sigma_f) and sigma_f < eps),
        "detail": f"σ_f = std of {len(wf)} window peak frequencies = {sigma_f:.3g} Hz vs ε(f0) = {th['epsilon_factor']:g}·f0 = {eps:.3g} Hz"
        if np.isfinite(sigma_f) else "σ_f undefined (fewer than two windows with a peak)"})
    sa0 = float(sigma_a[i0]) if np.isfinite(sigma_a[i0]) else np.nan
    out["clarity"].append({
        "id": "C6", "label": "σ_A(f0) < θ(f0)", "value": sa0, "threshold": th["theta"],
        "passed": bool(np.isfinite(sa0) and sa0 < th["theta"]),
        "detail": f"σ_A(f0) = exp(σ_ln) = {sa0:.3g} vs θ(f0) = {th['theta']:g} (log10 θ = {th['log10_theta']:g})"
        if np.isfinite(sa0) else "σ_A(f0) undefined"})

    out["reliability_passed"] = all(c["passed"] for c in out["reliability"])
    out["clarity_passed_count"] = int(sum(1 for c in out["clarity"] if c["passed"]))
    out["clarity_passed"] = out["clarity_passed_count"] >= 5
    out["evaluated"] = True
    out["message"] = (f"Reliability: {'passed' if out['reliability_passed'] else 'NOT passed'} "
                      f"({sum(c['passed'] for c in out['reliability'])}/3). Clear peak: "
                      f"{out['clarity_passed_count']}/6 criteria fulfilled "
                      f"({'clear' if out['clarity_passed'] else 'not clear'}; at least 5 of 6 required).")
    return out
