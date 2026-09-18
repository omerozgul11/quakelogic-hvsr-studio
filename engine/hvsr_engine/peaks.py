"""Peak detection on HVSR curves."""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

CLEAR_AMPLITUDE = 2.0      # SESAME clarity criterion C3 threshold (A0 > 2)
CLEAR_DOMINANCE = 1.5      # top candidate must exceed the runner-up by this factor


def find_candidates(freq: np.ndarray, curve: np.ndarray, search_min: float, search_max: float,
                    min_prominence: float = 0.0) -> list[dict]:
    """Local maxima of ``curve`` inside the search range, ranked by amplitude."""
    freq = np.asarray(freq, dtype=np.float64)
    curve = np.asarray(curve, dtype=np.float64)
    sel = (freq >= search_min) & (freq <= search_max)
    if sel.sum() < 3:
        return []
    idx = np.flatnonzero(sel)
    y = curve[idx]
    valid = np.isfinite(y)
    if valid.sum() < 3:
        return []
    fill = np.nanmin(y) - 1.0
    y_filled = np.where(valid, y, fill)
    peaks, props = find_peaks(y_filled, prominence=max(0.0, float(min_prominence)))
    out = []
    for p, prom in zip(peaks, props.get("prominences", [])):
        if not valid[p]:
            continue
        adjacent_masked = (p > 0 and not valid[p - 1]) or (p < len(y) - 1 and not valid[p + 1])
        out.append({
            "index": int(idx[p]), "frequency": float(freq[idx[p]]), "amplitude": float(y[p]),
            "prominence": float(prom), "adjacent_to_masked_bin": bool(adjacent_masked),
        })
    out.sort(key=lambda c: c["amplitude"], reverse=True)
    for rank, c in enumerate(out, start=1):
        c["rank"] = rank
    return out


def highest_peak(freq, curve, search_min, search_max) -> tuple[float, float]:
    cands = find_candidates(freq, curve, search_min, search_max)
    if not cands:
        return np.nan, np.nan
    return cands[0]["frequency"], cands[0]["amplitude"]


def classify(candidates: list[dict], n_accepted: int, min_valid_windows: int) -> tuple[str, str]:
    if n_accepted < max(1, min_valid_windows):
        return "insufficient_data", (f"Only {n_accepted} accepted window(s); at least {min_valid_windows} are "
                                     "required for a usable HVSR curve. No peak is reported.")
    strong = [c for c in candidates if c["amplitude"] >= CLEAR_AMPLITUDE]
    if not strong:
        if candidates:
            return "none", (f"No clear peak: the highest local maximum ({candidates[0]['frequency']:.3g} Hz, "
                            f"A = {candidates[0]['amplitude']:.2f}) is below the amplitude threshold of {CLEAR_AMPLITUDE:.1f}.")
        return "none", "No local maximum found inside the search range."
    top = strong[0]
    if len(strong) == 1 or top["amplitude"] >= CLEAR_DOMINANCE * strong[1]["amplitude"]:
        return "clear", (f"Single dominant peak at {top['frequency']:.3g} Hz (A = {top['amplitude']:.2f}).")
    others = ", ".join(f"{c['frequency']:.3g} Hz (A = {c['amplitude']:.2f})" for c in strong[1:4])
    return "multiple", (f"Multiple peaks of comparable amplitude: {top['frequency']:.3g} Hz "
                        f"(A = {top['amplitude']:.2f}) and {others}. The highest is reported as the "
                        "automatic selection; verify it or select a peak manually.")


def peaks_block(freq: np.ndarray, curve: np.ndarray, params: dict, n_accepted: int, min_valid_windows: int,
                manual_frequency: float | None = None) -> dict:
    p = params.get("peak") or {}
    search_min = float(p.get("search_min", freq[0]))
    search_max = float(p.get("search_max", freq[-1]))
    search_min, search_max = max(search_min, float(freq[0])), min(search_max, float(freq[-1]))
    cands = find_candidates(freq, curve, search_min, search_max, float(p.get("min_prominence", 0.0)))
    status, message = classify(cands, n_accepted, min_valid_windows)
    selected = None
    if manual_frequency is not None and status != "insufficient_data":
        i = int(np.argmin(np.abs(np.asarray(freq) - float(manual_frequency))))
        amp = float(curve[i]) if np.isfinite(curve[i]) else None
        selected = {"frequency": float(freq[i]), "amplitude": amp, "source": "manual", "index": i}
        message += f" Manual selection: {freq[i]:.3g} Hz."
    elif cands and status in ("clear", "multiple"):
        top = cands[0]
        selected = {"frequency": top["frequency"], "amplitude": top["amplitude"], "source": "automatic", "index": top["index"]}
    edge = False
    sel = (freq >= search_min) & (freq <= search_max)
    if sel.any() and np.isfinite(curve[sel]).any():
        seg = np.where(np.isfinite(curve), curve, -np.inf)[sel]
        imax = int(np.argmax(seg))
        if imax in (0, len(seg) - 1) and (not cands or seg[imax] > cands[0]["amplitude"]):
            edge = True
    return {
        "search_range": [search_min, search_max],
        "candidates": [{k: v for k, v in c.items() if k != "index"} | {"index": c["index"]} for c in cands[:10]],
        "selected": selected, "status": status, "message": message,
        "maximum_at_search_edge": bool(edge),
    }
