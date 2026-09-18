"""Time windowing and transient screening (STA/LTA, amplitude and level criteria).

Window modes (``params["windows"]["mode"]``):

* ``fixed``         — equal windows of ``length_s`` with fractional ``overlap`` (default).
* ``auto_variable`` — the record is split into "quiet" runs (every component below its level
                      threshold and, when enabled, the STA/LTA ratio inside [min, max]); windows as
                      long as possible (≤ ``max_length_s``, ≥ ``min_length_s``) are packed into those runs.
* ``custom``        — the user-supplied list ``custom = [[start_s, end_s], ...]`` (free selection /
                      repositioned windows). In every mode ``custom`` windows are appended.

Screening (STA/LTA anti-trigger, amplitude ratio, NaN) then decides ``accepted`` for each window and
``window_overrides`` always win. Every window carries ``length_s`` and ``color_index`` (position in
time order) so the interface can colour windows and their curves consistently.
"""
from __future__ import annotations

import copy

import numpy as np

from .io.canonical import Recording

DEFAULT_SCREENING = {
    "enabled": True,
    "sta_lta": {"enabled": True, "sta_s": 2.0, "lta_s": 30.0, "min_ratio": 0.2, "max_ratio": 2.5},
    "amplitude": {"enabled": False, "max_ratio_to_rms": 5.0},
}

DEFAULT_WINDOWS = {
    "mode": "fixed",
    "length_s": 60.0,
    "overlap": 0.5,
    "min_length_s": 30.0,
    "max_length_s": 60.0,
    "levels": {"enabled": False, "mode": "absolute", "n": 0.0, "e": 0.0, "z": 0.0, "ratio": 5.0},
    "custom": [],
}

WINDOW_MODES = ("fixed", "auto_variable", "custom")


def make_windows(n_samples: int, fs: float, length_s: float, overlap: float) -> list[tuple[int, int]]:
    """Fixed-length windows ``[start, end)`` in samples, starting at sample 0.

    ``overlap`` is the fraction (0 ≤ overlap < 1) shared by consecutive windows. Only
    complete windows are returned; the trailing remainder is not used.
    """
    if length_s <= 0:
        raise ValueError("Window length must be positive")
    if not (0 <= overlap < 1):
        raise ValueError("Overlap must be in [0, 1)")
    nwin = int(round(length_s * fs))
    if nwin < 2:
        raise ValueError("Window length is shorter than two samples")
    step = max(1, int(round(nwin * (1.0 - overlap))))
    out = []
    start = 0
    while start + nwin <= n_samples:
        out.append((start, start + nwin))
        start += step
    return out


def resolve_window_params(params: dict | None) -> dict:
    """Normalise the window configuration.

    Accepts the ``windows`` block of the contract and the legacy top-level aliases
    ``window_length_s`` / ``overlap`` (which keep working for old presets and callers).
    """
    params = params or {}
    out = copy.deepcopy(DEFAULT_WINDOWS)
    if "window_length_s" in params and params["window_length_s"] is not None:
        out["length_s"] = float(params["window_length_s"])
        out["max_length_s"] = max(out["max_length_s"], out["length_s"])
    if "overlap" in params and params["overlap"] is not None:
        out["overlap"] = float(params["overlap"])
    block = params.get("windows") or {}
    if isinstance(block, dict):
        for key, value in block.items():
            if key == "levels" and isinstance(value, dict):
                out["levels"].update(value)
            elif key == "custom":
                out["custom"] = [list(map(float, w)) for w in (value or []) if w is not None and len(w) == 2]
            elif value is not None:
                out[key] = value
    out["mode"] = str(out.get("mode") or "fixed")
    if out["mode"] not in WINDOW_MODES:
        raise ValueError(f"Unknown window mode {out['mode']!r}; expected one of {WINDOW_MODES}")
    out["length_s"] = float(out["length_s"])
    out["overlap"] = float(out["overlap"])
    out["min_length_s"] = float(out["min_length_s"])
    out["max_length_s"] = float(out["max_length_s"])
    if out["mode"] == "auto_variable":
        if out["min_length_s"] <= 0 or out["max_length_s"] < out["min_length_s"]:
            raise ValueError("auto_variable windows need 0 < min_length_s ≤ max_length_s")
    return out


def _merge_screening(params: dict | None) -> dict:
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_SCREENING.items()}
    if params:
        for key, value in params.items():
            if isinstance(value, dict) and isinstance(p.get(key), dict):
                p[key].update(value)
            else:
                p[key] = value
    return p


def sta_lta_ratio(x: np.ndarray, fs: float, sta_s: float, lta_s: float) -> tuple[np.ndarray, int]:
    """STA/LTA of the mean ABSOLUTE amplitude (anti-trigger style, as used for ambient-noise
    window selection), computed with cumulative sums.

    The characteristic function is |x| (not x², which ObsPy's ``classic_sta_lta`` uses and
    which is far spikier for narrow-band noise). STA and LTA are trailing averages ending
    at each sample. Returns the ratio array (NaN where the LTA is not yet defined) and the
    number of leading undefined samples."""
    x = np.abs(np.asarray(x, dtype=np.float64))
    nsta = max(1, int(round(sta_s * fs)))
    nlta = max(nsta + 1, int(round(lta_s * fs)))
    n = len(x)
    ratio = np.full(n, np.nan)
    if nlta >= n:
        return ratio, n
    cs = np.concatenate([[0.0], np.cumsum(x)])
    i = np.arange(nlta, n + 1)
    sta = (cs[i] - cs[i - nsta]) / nsta
    lta = (cs[i] - cs[i - nlta]) / nlta
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio[i - 1] = np.where(lta > 0, sta / lta, np.nan)
    return ratio, nlta


def quiet_mask(comps: dict[str, np.ndarray], fs: float, wp: dict, screening: dict,
               ratios: dict[str, np.ndarray] | None = None) -> np.ndarray:
    """Boolean mask of samples considered quiet for automatic variable-length selection."""
    n = len(next(iter(comps.values())))
    quiet = np.ones(n, dtype=bool)
    levels = wp.get("levels") or {}
    for name, x in comps.items():
        quiet &= np.isfinite(x)
        if levels.get("enabled"):
            ax = np.abs(x)
            if levels.get("mode", "absolute") == "ratio_rms":
                rms = float(np.sqrt(np.nanmean(x ** 2))) if np.isfinite(x).any() else 0.0
                thr = float(levels.get("ratio", 5.0)) * rms
            else:
                thr = float(levels.get(name, 0.0) or 0.0)
            if thr > 0:
                quiet &= ~(ax > thr)
    if ratios:
        lo, hi = screening["sta_lta"]["min_ratio"], screening["sta_lta"]["max_ratio"]
        for r in ratios.values():
            defined = np.isfinite(r)
            quiet &= ~(defined & ((r > hi) | (r < lo)))
    return quiet


def pack_windows(quiet: np.ndarray, fs: float, min_length_s: float, max_length_s: float) -> list[tuple[int, int]]:
    """Greedily fill every quiet run with the longest possible windows (≤ max, ≥ min), no overlap."""
    n_min = max(2, int(round(min_length_s * fs)))
    n_max = max(n_min, int(round(max_length_s * fs)))
    out = []
    n = len(quiet)
    i = 0
    while i < n:
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j < n and quiet[j]:
            j += 1
        start = i
        while j - start >= n_min:
            w = min(n_max, j - start)
            out.append((start, start + w))
            start += w
        i = j
    return out


def custom_windows(custom: list, n_samples: int, fs: float) -> list[tuple[int, int]]:
    out = []
    for w in custom or []:
        try:
            a, b = float(w[0]), float(w[1])
        except (TypeError, ValueError, IndexError):
            continue
        s = max(0, int(round(a * fs)))
        e = min(n_samples, int(round(b * fs)))
        if e - s >= 2:
            out.append((s, e))
    return out


def screen_windows(rec: Recording, params: dict, window_overrides: dict | None = None) -> dict:
    """Return the window table of a recording with screening decisions.

    ``params`` holds the ``windows`` block (or the ``window_length_s``/``overlap`` aliases) and
    ``screening`` (see DEFAULT_SCREENING). ``window_overrides`` maps window index (int or str)
    to ``{"accepted": bool, "reason": str}``; overrides always win.
    """
    wp = resolve_window_params(params)
    screening = _merge_screening(params.get("screening"))
    overrides = {int(k): v for k, v in (window_overrides or {}).items()}

    comps = rec.components()
    use_sta = screening["enabled"] and screening["sta_lta"]["enabled"]
    use_amp = screening["enabled"] and screening["amplitude"]["enabled"]
    ratios, nlta = {}, 0
    if use_sta:
        for name, x in comps.items():
            ratios[name], nlta = sta_lta_ratio(x, rec.fs, screening["sta_lta"]["sta_s"], screening["sta_lta"]["lta_s"])
    rms = {name: float(np.sqrt(np.nanmean(x ** 2))) if len(x) else 0.0 for name, x in comps.items()}

    mode = wp["mode"]
    if mode == "fixed":
        windows = make_windows(rec.n_samples, rec.fs, wp["length_s"], wp["overlap"])
    elif mode == "auto_variable":
        quiet = quiet_mask(comps, rec.fs, wp, screening, ratios if use_sta else None)
        windows = pack_windows(quiet, rec.fs, wp["min_length_s"], wp["max_length_s"])
    else:
        windows = []
    windows = windows + custom_windows(wp["custom"], rec.n_samples, rec.fs)
    windows = sorted(set(windows))

    items = []
    for idx, (s, e) in enumerate(windows):
        item = {
            "index": idx, "start_s": s / rec.fs, "end_s": e / rec.fs, "length_s": (e - s) / rec.fs,
            "color_index": idx,
            "accepted": True, "reason": None,
            "sta_lta_max": None, "sta_lta_min": None, "amp_ratio": None, "has_nan": False,
        }
        has_nan = any(np.isnan(x[s:e]).any() for x in comps.values())
        item["has_nan"] = bool(has_nan)
        if use_sta:
            lo = max(s, nlta)
            if lo < e:
                segs = [r[lo:e] for r in ratios.values() if np.isfinite(r[lo:e]).any()]
                if segs:
                    item["sta_lta_max"] = max(float(np.nanmax(sg)) for sg in segs)
                    item["sta_lta_min"] = min(float(np.nanmin(sg)) for sg in segs)
        if use_amp:
            amp = max(float(np.nanmax(np.abs(x[s:e]))) / rms[name] if rms[name] > 0 else np.inf
                      for name, x in comps.items())
            item["amp_ratio"] = None if not np.isfinite(amp) else amp

        if has_nan:
            item["accepted"], item["reason"] = False, "nan"
        elif use_sta and item["sta_lta_max"] is not None and (
                item["sta_lta_max"] > screening["sta_lta"]["max_ratio"]
                or item["sta_lta_min"] < screening["sta_lta"]["min_ratio"]):
            item["accepted"], item["reason"] = False, "sta_lta"
        elif use_amp and item["amp_ratio"] is not None and item["amp_ratio"] > screening["amplitude"]["max_ratio_to_rms"]:
            item["accepted"], item["reason"] = False, "amplitude"

        if idx in overrides:
            ov = overrides[idx]
            accepted = bool(ov.get("accepted", True)) if isinstance(ov, dict) else bool(ov)
            if has_nan and accepted:
                accepted = False  # a window containing NaN can never be used
                item["reason"] = "nan"
            else:
                item["reason"] = "manual"
            item["accepted"] = accepted
        items.append(item)

    accepted = sum(1 for it in items if it["accepted"])
    lengths = [it["length_s"] for it in items]
    longest = max(lengths) if lengths else (wp["length_s"] if mode == "fixed" else wp["max_length_s"])
    return {
        "windows": items,
        "counts": {"total": len(items), "accepted": accepted, "rejected": len(items) - accepted},
        "screening_applied": screening,
        "mode": mode,
        "window_length_s": wp["length_s"] if mode == "fixed" else longest,
        "overlap": wp["overlap"] if mode == "fixed" else 0.0,
        "min_length_s": (min(lengths) if lengths else None),
        "max_length_s": (longest if lengths else None),
        "samples_per_window": int(round((wp["length_s"] if mode == "fixed" else longest) * rec.fs)),
        "t10_hz": (10.0 / longest) if longest else None,
        "windows_params": wp,
    }
