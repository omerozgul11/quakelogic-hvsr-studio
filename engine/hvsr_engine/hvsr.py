"""HVSR analysis engine: windows → spectra → smoothing → combination → statistics → peaks.

The full algorithm is documented in docs/hvsr-algorithms.md. Summary of the fixed choices:

1. Each accepted window: linear detrend → Tukey taper (per-side percent) → rfft → |X|·dt.
2. Konno–Ohmachi smoothing of EACH component spectrum onto a log-spaced axis.
3. Horizontal combination AFTER smoothing (default; ``combination_stage`` may be set to
   ``before_smoothing``): geometric_mean √(|N||E|), rms √((|N|²+|E|²)/2), directional |N|,|E|.
4. Vertical masking: bins where the smoothed vertical is below a floor are NaN; bins with
   fewer than ``min_valid_windows`` valid windows are invalid in the aggregate curves.
5. Aggregates: geometric (log) mean with log-std band, arithmetic mean ± std, median with
   16–84 % band. These are dispersion bands, not confidence intervals.
6. Peaks, window-level peak distribution, seeded bootstrap percentile interval, SESAME
   (2004) criteria, optional azimuthal analysis.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import peaks as peaks_mod
from . import sesame as sesame_mod
from .azimuthal import azimuthal_matrix
from .errors import CancelledError
from .io.canonical import Recording
from .smoothing import konno_ohmachi_matrix, log_frequency_axis, smooth
from .spectra import prepare_window
from .statistics import aggregate, summarize_values
from .version import ENGINE_VERSION, versions
from .windows import screen_windows

DEFAULT_PARAMS = {
    "window_length_s": 60.0,
    "overlap": 0.5,
    "windows": {"mode": "fixed", "length_s": None, "overlap": None, "min_length_s": 30.0, "max_length_s": 60.0,
                "levels": {"enabled": False, "mode": "absolute", "n": 0.0, "e": 0.0, "z": 0.0, "ratio": 5.0},
                "custom": []},
    "screening": {
        "enabled": True,
        "sta_lta": {"enabled": True, "sta_s": 2.0, "lta_s": 30.0, "min_ratio": 0.2, "max_ratio": 2.5},
        "amplitude": {"enabled": False, "max_ratio_to_rms": 5.0},
    },
    "detrend": "linear",
    "taper_percent": 5.0,
    "smoothing": {"type": "konno_ohmachi", "bandwidth": 40.0},
    "freq_min": 0.2,
    "freq_max": 30.0,
    "n_freq": 300,
    "horizontal_method": "geometric_mean",
    "combination_stage": "after_smoothing",
    "mean_method": "geometric",
    "peak": {"search_min": 0.5, "search_max": 20.0, "min_prominence": 0.0},
    "vertical_floor": {"relative": 1e-6, "absolute": 1e-12},
    "min_valid_windows": 3,
    "bootstrap": {"enabled": True, "n_resamples": 200},
    "azimuthal": {"enabled": False, "step_deg": 10.0},
    "sesame": True,
}

INTERPRETATION_NOTES = [
    "The HVSR amplitude is a spectral ratio of ambient-vibration components. It is NOT a direct "
    "measurement of site amplification and must not be used as one.",
    "The peak frequency f0 is an estimate of the fundamental resonance frequency of the site under "
    "the assumptions of the HVSR technique (SESAME, 2004). No unique subsurface velocity profile can "
    "be inferred from an HVSR curve alone.",
    "Dispersion bands describe the spread of the individual window curves; they are not confidence "
    "intervals. The bootstrap interval is a percentile interval of the resampled mean-curve peak.",
    "Results depend on the processing choices recorded in this file (window length, smoothing, "
    "horizontal combination, screening).",
]


def merge_params(params: dict | None) -> dict:
    out = copy.deepcopy(DEFAULT_PARAMS)

    def _merge(dst, src):
        for k, v in (src or {}).items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                _merge(dst[k], v)
            else:
                dst[k] = v

    _merge(out, params)
    return out


@dataclass
class HvsrResult:
    data: dict
    window_curves: np.ndarray
    frequency: np.ndarray
    accepted: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    azimuthal_matrix: np.ndarray | None = None

    def to_dict(self) -> dict:
        return _sanitize(self.data)


def _sanitize(obj):
    """Convert numpy types and non-finite floats (→ None) so the result is strict JSON."""
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def _file_sha256(path: str | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise CancelledError()


def _combine(n_amp: np.ndarray, e_amp: np.ndarray, method: str) -> np.ndarray:
    if method == "rms":
        return np.sqrt((n_amp ** 2 + e_amp ** 2) / 2.0)
    return np.sqrt(n_amp * e_amp)  # geometric_mean and directional (main curve)


def analyze(rec: Recording, params: dict | None = None, window_overrides: dict | None = None,
            manual_peak: dict | float | None = None, random_seed: int | None = None,
            progress=None, cancel=None, input_path: str | None = None) -> HvsrResult:
    t_begin = time.time()
    p = merge_params(params)
    notify = progress or (lambda frac, msg=None: None)

    def report(frac, msg):
        try:
            notify(float(frac), msg)
        except TypeError:
            notify(float(frac))

    fs = rec.fs
    nyq = fs / 2.0
    flags: list[dict] = []

    # ---- windows and screening -------------------------------------------
    report(0.02, "Selecting windows")
    screening = screen_windows(rec, p, window_overrides)
    items = screening["windows"]
    windows = [(int(round(it["start_s"] * fs)), int(round(it["end_s"] * fs))) for it in items]
    accepted_mask = np.array([it["accepted"] for it in items], dtype=bool)
    n_total, n_acc = len(items), int(accepted_mask.sum())
    win_mode = screening.get("mode", "fixed")
    lw = float(screening.get("window_length_s") or p["window_length_s"])  # fixed length, or the longest window
    if n_total == 0:
        if win_mode == "fixed":
            raise ValueError(f"The record ({rec.duration_s:.1f} s) is shorter than one window ({lw:g} s).")
        raise ValueError("No windows were selected (no quiet segment long enough, or an empty custom list).")
    acc_lengths = [it["length_s"] for it in items if it["accepted"]]
    mean_len = float(np.mean(acc_lengths)) if acc_lengths else lw
    shortest = min((it["length_s"] for it in items), default=lw)

    # ---- frequency axis --------------------------------------------------
    fmin, fmax = float(p["freq_min"]), float(p["freq_max"])
    if fmax > nyq:
        flags.append({"code": "freq_max_clamped", "severity": "warning",
                      "message": f"freq_max {fmax:g} Hz exceeds the Nyquist frequency {nyq:g} Hz and was clamped."})
        fmax = nyq
        p["freq_max"] = fmax
    if fmin < 1.0 / shortest:
        flags.append({"code": "low_frequency_resolution", "severity": "warning",
                      "message": f"freq_min {fmin:g} Hz is below the spectral resolution 1/window length = {1 / shortest:.3g} Hz; "
                                 "the lowest bins are poorly resolved."})
    freq_out = log_frequency_axis(fmin, fmax, int(p["n_freq"]))

    if rec.duration_s < 3 * lw:
        flags.append({"code": "short_record", "severity": "warning",
                      "message": f"Record length {rec.duration_s:.0f} s is shorter than three windows of {lw:g} s."})
    if n_total and (n_total - n_acc) / n_total > 0.5:
        flags.append({"code": "many_windows_rejected", "severity": "warning",
                      "message": f"{n_total - n_acc} of {n_total} windows ({100 * (n_total - n_acc) / n_total:.0f} %) were rejected."})
    min_valid = int(p["min_valid_windows"])
    if n_acc < min_valid:
        flags.append({"code": "insufficient_windows", "severity": "error",
                      "message": f"Only {n_acc} accepted window(s); at least {min_valid} are required."})
    _check_cancel(cancel)

    # ---- per-window spectra (one FFT grid / smoothing matrix per distinct window length) ----
    bandwidth = float(p["smoothing"].get("bandwidth", 40.0))
    use_ko = p["smoothing"].get("type", "konno_ohmachi") == "konno_ohmachi"
    grids: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    def grid_for(nwin_: int) -> tuple[np.ndarray, np.ndarray]:
        if nwin_ not in grids:
            f_in_ = np.fft.rfftfreq(nwin_, d=1.0 / fs)
            if use_ko:
                m_ = konno_ohmachi_matrix(f_in_, freq_out, bandwidth)
            else:
                idx = np.clip(np.searchsorted(f_in_, freq_out), 0, len(f_in_) - 1)
                m_ = np.zeros((len(freq_out), len(f_in_)))
                m_[np.arange(len(freq_out)), idx] = 1.0
            grids[nwin_] = (f_in_, m_)
        return grids[nwin_]

    acc_idx = np.flatnonzero(accepted_mask)
    n_out = len(freq_out)
    stage = p.get("combination_stage", "after_smoothing")
    method = p.get("horizontal_method", "geometric_mean")
    want_complex = bool(p["azimuthal"].get("enabled"))
    n_cplx: list[np.ndarray] = []
    e_cplx: list[np.ndarray] = []
    matrices: list[np.ndarray] = []
    ns = np.empty((len(acc_idx), n_out))
    es = np.empty((len(acc_idx), n_out))
    zs = np.empty((len(acc_idx), n_out))
    hs_before = np.empty((len(acc_idx), n_out))
    taper = float(p["taper_percent"])
    detrend = p.get("detrend", "linear")
    nwin = int(round(lw * fs))
    for k, wi in enumerate(acc_idx):
        _check_cancel(cancel)
        s, e = windows[wi]
        _, matrix = grid_for(e - s)
        specs = {}
        for name in ("n", "e", "z"):
            x = prepare_window(rec.component(name)[s:e], detrend, taper)
            specs[name] = np.fft.rfft(x) / fs
        if want_complex:
            n_cplx.append(specs["n"])
            e_cplx.append(specs["e"])
            matrices.append(matrix)
        an, ae, az = np.abs(specs["n"]), np.abs(specs["e"]), np.abs(specs["z"])
        ns[k], es[k], zs[k] = smooth(an, matrix), smooth(ae, matrix), smooth(az, matrix)
        hs_before[k] = smooth(_combine(an, ae, method), matrix)
        if k % 5 == 0:
            report(0.05 + 0.45 * (k + 1) / max(1, len(acc_idx)), f"Window {k + 1}/{len(acc_idx)}")

    # ---- vertical masking ------------------------------------------------
    floor_rel = float(p["vertical_floor"].get("relative", 1e-6))
    floor_abs = float(p["vertical_floor"].get("absolute", 1e-12))
    z_masked = zs.copy()
    masked_bins = np.zeros(n_out, dtype=int)
    if len(acc_idx):
        band_max = np.nanmax(zs, axis=1, keepdims=True)
        floor = np.maximum(floor_abs, floor_rel * band_max)
        mask = ~(zs > floor)
        z_masked[mask] = np.nan
        masked_bins = mask.sum(axis=0)
    with np.errstate(all="ignore"):
        if stage == "before_smoothing":
            h_used = hs_before
        else:
            h_used = _combine(ns, es, method)
        hv = h_used / z_masked
        n_over_z = ns / z_masked
        e_over_z = es / z_masked

    # ---- aggregates --------------------------------------------------------
    report(0.55, "Aggregating window curves")
    curves = {}
    if len(acc_idx):
        for m in ("geometric", "arithmetic", "median"):
            curves[m] = aggregate(hv, m, min_valid)
    else:
        nan = np.full(n_out, np.nan)
        for m in ("geometric", "arithmetic", "median"):
            curves[m] = {"values": nan, "lower": nan, "upper": nan, "band": "", "n_valid": [0] * n_out}
        curves["geometric"]["sigma_ln"] = nan
    selected_method = p.get("mean_method", "geometric")
    if selected_method not in curves:
        raise ValueError(f"Unknown mean_method {selected_method}")
    main = curves[selected_method]["values"]
    invalid_bins = np.flatnonzero(~np.isfinite(curves["geometric"]["values"])).tolist() if len(acc_idx) else list(range(n_out))
    if masked_bins.sum() > 0:
        flags.append({"code": "vertical_masked_bins", "severity": "warning",
                      "message": f"{int(masked_bins.sum())} frequency bin(s) across windows were masked because the smoothed "
                                 "vertical amplitude was below the floor; they are excluded, not clipped."})
    if invalid_bins and len(acc_idx) >= min_valid:
        flags.append({"code": "invalid_bins", "severity": "warning",
                      "message": f"{len(invalid_bins)} frequency bin(s) have fewer than {min_valid} valid windows and are "
                                 "reported as invalid (null)."})

    # ---- peaks -----------------------------------------------------------
    report(0.65, "Detecting peaks")
    manual_freq = None
    if isinstance(manual_peak, dict):
        manual_freq = manual_peak.get("frequency")
    elif isinstance(manual_peak, (int, float)):
        manual_freq = float(manual_peak)
    pk = peaks_mod.peaks_block(freq_out, main, p, n_acc, min_valid, manual_freq)
    if pk.get("maximum_at_search_edge"):
        flags.append({"code": "peak_at_search_edge", "severity": "warning",
                      "message": "The maximum of the mean curve lies at the edge of the peak search range; widen the range."})
    sr = tuple(pk["search_range"])
    window_f0, window_a0 = [], []
    for k in range(len(acc_idx)):
        f, a = peaks_mod.highest_peak(freq_out, hv[k], *sr)
        window_f0.append(f)
        window_a0.append(a)
    for it in items:
        it["f0"], it["a0"] = None, None
    for k, wi in enumerate(acc_idx):
        items[wi]["f0"] = None if not np.isfinite(window_f0[k]) else float(window_f0[k])
        items[wi]["a0"] = None if not np.isfinite(window_a0[k]) else float(window_a0[k])
    variability = summarize_values(np.array(window_f0)) if window_f0 else summarize_values(np.array([]))
    variability = {"window_f0": window_f0, "window_a0": window_a0, **variability,
                   "definition": "Peak frequency of each accepted window curve inside the search range (highest local "
                                 "maximum). std = sample standard deviation (ddof=1) of these frequencies (SESAME σ_f); "
                                 "std_ln = standard deviation of ln f0; p16/p84 = percentiles.",
                   "bootstrap": None}

    # ---- bootstrap ----------------------------------------------------------
    seed = random_seed
    if seed is None:
        seed = secrets.randbits(32)
    seed = int(seed)
    bs = p.get("bootstrap") or {}
    if bs.get("enabled", True) and n_acc >= min_valid and n_acc >= 2:
        report(0.7, "Bootstrapping peak frequency")
        n_res = int(bs.get("n_resamples", 200))
        rng = np.random.default_rng(seed)
        bf, ba = [], []
        for r in range(n_res):
            if r % 20 == 0:
                _check_cancel(cancel)
            pick = rng.integers(0, len(acc_idx), size=len(acc_idx))
            agg = aggregate(hv[pick], selected_method, min_valid)
            f, a = peaks_mod.highest_peak(freq_out, agg["values"], *sr)
            bf.append(f)
            ba.append(a)
        bf, ba = np.array(bf), np.array(ba)
        ok = np.isfinite(bf)
        if ok.sum() >= 2:
            variability["bootstrap"] = {
                "n_resamples": n_res, "seed": seed, "n_with_peak": int(ok.sum()),
                "f0_p2_5": float(np.percentile(bf[ok], 2.5)), "f0_p50": float(np.percentile(bf[ok], 50)),
                "f0_p97_5": float(np.percentile(bf[ok], 97.5)),
                "a0_p2_5": float(np.percentile(ba[ok], 2.5)), "a0_p50": float(np.percentile(ba[ok], 50)),
                "a0_p97_5": float(np.percentile(ba[ok], 97.5)),
                "definition": "Bootstrap percentile interval (2.5–97.5 %) of the peak of the mean curve obtained by "
                              f"resampling the accepted windows with replacement {n_res} times (numpy default_rng, seed {seed}).",
            }

    # ---- SESAME --------------------------------------------------------------
    ses = None
    if p.get("sesame", True):
        report(0.8, "Evaluating SESAME criteria")
        f0 = pk["selected"]["frequency"] if pk["selected"] else None
        geo = curves["geometric"]
        a0 = None
        if f0 is not None:
            i0 = int(np.argmin(np.abs(freq_out - f0)))
            a0 = float(geo["values"][i0]) if np.isfinite(geo["values"][i0]) else None
        ses = sesame_mod.evaluate(freq_out, geo["values"], geo["sigma_ln"], f0, a0, mean_len, n_acc,
                                  np.array(window_f0), sr)
    if len(acc_idx) >= min_valid:
        sig = curves["geometric"]["sigma_ln"]
        band = (freq_out >= sr[0]) & (freq_out <= sr[1]) & np.isfinite(sig)
        if band.any() and float(np.nanmedian(np.exp(sig[band]))) > 2.0:
            flags.append({"code": "high_dispersion", "severity": "warning",
                          "message": "The median multiplicative dispersion σ_A inside the search range exceeds 2; "
                                     "the curve is poorly constrained."})

    # ---- directional & azimuthal ---------------------------------------------
    directional = None
    if method == "directional" and len(acc_idx):
        directional = {"n_over_z": _curve_dict(aggregate(n_over_z, selected_method, min_valid)),
                       "e_over_z": _curve_dict(aggregate(e_over_z, selected_method, min_valid))}
    azimuthal = None
    az_matrix = None
    if want_complex and len(acc_idx):
        report(0.85, "Azimuthal analysis")
        az = azimuthal_matrix(n_cplx, e_cplx, z_masked, matrices, freq_out, float(p["azimuthal"].get("step_deg", 10.0)),
                              selected_method, min_valid, sr,
                              progress=lambda fr: report(0.85 + 0.12 * fr, "Azimuthal analysis"), cancel=cancel)
        az_matrix = az.pop("matrix")
        az["matrix"] = az_matrix
        azimuthal = az

    # ---- component spectra ---------------------------------------------------
    comps = {}
    if len(acc_idx):
        with np.errstate(all="ignore"):
            comps = {"n": np.nanmean(ns, axis=0), "e": np.nanmean(es, axis=0), "z": np.nanmean(zs, axis=0),
                     "h": np.nanmean(h_used, axis=0)}
    else:
        comps = {k: np.full(n_out, np.nan) for k in ("n", "e", "z", "h")}

    combo_desc = {
        "geometric_mean": "H = sqrt(|N|·|E|)", "rms": "H = sqrt((|N|² + |E|²)/2)",
        "directional": "main curve H = sqrt(|N|·|E|); directional ratios |N|/|Z| and |E|/|Z| reported separately",
    }.get(method, method)

    data = {
        "engine_version": ENGINE_VERSION, "versions": versions(),
        "computed_at": datetime.now(timezone.utc).isoformat(), "elapsed_s": None,
        "random_seed": seed,
        "params": p,
        "input": {"path": input_path, "sha256": _file_sha256(input_path), "fs": fs, "n_samples": rec.n_samples,
                  "duration_s": rec.duration_s, "start_time": rec.start_time,
                  "station": rec.meta.get("station", ""), "network": rec.meta.get("network", ""),
                  "channels": rec.meta.get("channels"), "units": rec.meta.get("units", "counts"),
                  "is_synthetic": bool(rec.meta.get("is_synthetic", False)),
                  "processing_steps": rec.meta.get("steps", [])},
        "frequency": freq_out,
        "windows": {"mode": win_mode, "length_s": lw, "overlap": float(screening.get("overlap", p["overlap"])),
                    "samples_per_window": nwin, "min_length_s": screening.get("min_length_s"),
                    "max_length_s": screening.get("max_length_s"), "mean_accepted_length_s": mean_len,
                    "count_total": n_total, "count_accepted": n_acc, "count_rejected": n_total - n_acc,
                    "screening_applied": screening["screening_applied"], "windows_params": screening.get("windows_params"),
                    "items": items},
        "t10_hz": 10.0 / lw,
        "method": {"horizontal_method": method, "horizontal_definition": combo_desc,
                   "combination_stage": stage, "mean_method": selected_method,
                   "smoothing": p["smoothing"], "spectrum_definition": "|rfft(detrended, Tukey-tapered window)|·dt",
                   "frequency_axis": f"{n_out} log-spaced points between {fmin:g} and {fmax:g} Hz",
                   "frequency_resolution_hz": 1.0 / lw,
                   "window_mode": win_mode},
        "curves": {"selected": selected_method, **{m: _curve_dict(c) for m, c in curves.items()}},
        "components": comps,
        "directional": directional,
        "masking": {"policy": "Per window, bins where the smoothed vertical amplitude |Z| is below "
                              f"max({floor_abs:g}, {floor_rel:g} × max|Z| over the analysis band) are excluded (reported as null); "
                              f"bins with fewer than {min_valid} valid windows are invalid in the aggregate curves. Ratios are never clipped.",
                    "relative_floor": floor_rel, "absolute_floor": floor_abs,
                    "bins_masked_any_window": int(np.count_nonzero(masked_bins)),
                    "masked_count_per_bin": masked_bins, "invalid_bins": invalid_bins, "min_valid_windows": min_valid},
        "peaks": pk,
        "peak_variability": variability,
        "sesame": ses,
        "quality_flags": flags,
        "interpretation_notes": INTERPRETATION_NOTES,
        "azimuthal": azimuthal,
    }
    full_curves = np.full((n_total, n_out), np.nan, dtype=np.float32)
    if len(acc_idx):
        full_curves[acc_idx] = hv.astype(np.float32)
    data["time_frequency"] = {
        "times_s": [it["start_s"] for it in items], "end_times_s": [it["end_s"] for it in items],
        "accepted": [bool(it["accepted"]) for it in items], "frequency": freq_out,
        "matrix": full_curves.astype(np.float64),
        "definition": "Per-window H/V curves in time order (rows = windows, start time in seconds from the record "
                      "start; rejected windows are null). Drawn as the H/V-versus-time graph.",
    }
    data["elapsed_s"] = round(time.time() - t_begin, 3)
    report(1.0, "Done")
    return HvsrResult(data=data, window_curves=full_curves, frequency=freq_out, accepted=accepted_mask,
                      azimuthal_matrix=az_matrix)


def _curve_dict(agg: dict) -> dict:
    out = {"values": agg["values"], "lower": agg["lower"], "upper": agg["upper"], "band": agg.get("band", ""),
           "n_valid": agg.get("n_valid")}
    if "sigma_ln" in agg:
        out["sigma_ln"] = agg["sigma_ln"]
    return out


# --------------------------------------------------------------------------------------
# Persistence & exports
# --------------------------------------------------------------------------------------

def write_result(result: HvsrResult, output_dir: str | Path) -> dict:
    out = Path(output_dir)
    (out / "exports").mkdir(parents=True, exist_ok=True)
    data = result.to_dict()
    with open(out / "result.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, allow_nan=False)
    np.savez_compressed(out / "curves.npz", frequency=result.frequency, curves=result.window_curves,
                        accepted=result.accepted,
                        azimuthal=result.azimuthal_matrix if result.azimuthal_matrix is not None else np.zeros((0, 0)))
    write_exports(data, out)
    return data


def load_result(output_dir: str | Path) -> dict:
    with open(Path(output_dir) / "result.json", encoding="utf-8") as fh:
        return json.load(fh)


def window_curves(output_dir: str | Path) -> dict:
    with np.load(Path(output_dir) / "curves.npz", allow_pickle=False) as d:
        curves = d["curves"].astype(np.float64)
        return _sanitize({"frequency": d["frequency"], "curves": curves, "accepted": d["accepted"].astype(bool)})


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def write_exports(data: dict, out: Path) -> list[str]:
    exp = out / "exports"
    exp.mkdir(parents=True, exist_ok=True)
    written = []
    freq = data["frequency"]
    c = data["curves"]
    with open(exp / "hvsr_mean.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["# QuakeLogic HVSR Studio — mean HVSR curves. Bands are dispersion bands, not confidence intervals."])
        w.writerow([f"# {m}: {c[m]['band']}" for m in ("geometric", "arithmetic", "median")])
        w.writerow(["frequency_hz", "hvsr_geometric", "geometric_lower", "geometric_upper", "sigma_ln",
                    "hvsr_arithmetic", "arithmetic_lower", "arithmetic_upper",
                    "hvsr_median", "median_p16", "median_p84", "n_valid_windows"])
        for i, f in enumerate(freq):
            w.writerow([_fmt(f), _fmt(c["geometric"]["values"][i]), _fmt(c["geometric"]["lower"][i]), _fmt(c["geometric"]["upper"][i]),
                        _fmt(c["geometric"].get("sigma_ln", [None] * len(freq))[i]),
                        _fmt(c["arithmetic"]["values"][i]), _fmt(c["arithmetic"]["lower"][i]), _fmt(c["arithmetic"]["upper"][i]),
                        _fmt(c["median"]["values"][i]), _fmt(c["median"]["lower"][i]), _fmt(c["median"]["upper"][i]),
                        _fmt((c["geometric"].get("n_valid") or [None] * len(freq))[i])])
    written.append("hvsr_mean.csv")

    curves_path = out / "curves.npz"
    if curves_path.exists():
        with np.load(curves_path, allow_pickle=False) as d:
            wc = d["curves"]
        with open(exp / "hvsr_windows.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["# Per-window HVSR curves (rejected windows are empty)."])
            items = data["windows"]["items"]
            w.writerow(["frequency_hz"] + [f"window_{it['index']}_{'acc' if it['accepted'] else 'rej'}" for it in items])
            for i, f in enumerate(freq):
                row = [_fmt(f)]
                for k in range(wc.shape[0]):
                    v = float(wc[k, i])
                    row.append("" if not np.isfinite(v) else f"{v:.6g}")
                w.writerow(row)
        written.append("hvsr_windows.csv")

    with open(exp / "component_spectra.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"# Mean smoothed Fourier amplitude spectra over accepted windows; units {data['input'].get('units', 'counts')}*s"])
        w.writerow(["frequency_hz", "north", "east", "vertical", "horizontal_combined"])
        comps = data["components"]
        for i, f in enumerate(freq):
            w.writerow([_fmt(f), _fmt(comps["n"][i]), _fmt(comps["e"][i]), _fmt(comps["z"][i]), _fmt(comps["h"][i])])
    written.append("component_spectra.csv")

    sel = c.get("selected", "geometric")
    from .io.curves import write_hv
    write_hv(exp / "hvsr_mean.hv", freq, c[sel]["values"], c[sel]["lower"], c[sel]["upper"],
             name=f"QuakeLogic HVSR Studio — {sel} mean H/V of {data['input'].get('station') or 'recording'}",
             header_lines=[f"Number of windows = {data['windows']['count_accepted']}",
                           f"f0 = {(data['peaks'].get('selected') or {}).get('frequency')}"])
    written.append("hvsr_mean.hv")

    summary = summary_dict(data)
    with open(exp / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, allow_nan=False)
    with open(exp / "summary.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        flat = _flatten(summary)
        w.writerow(flat.keys())
        w.writerow([_fmt(v) for v in flat.values()])
    written += ["summary.json", "summary.csv"]

    with open(exp / "config.json", "w", encoding="utf-8") as fh:
        json.dump({"engine_version": data["engine_version"], "versions": data["versions"], "random_seed": data["random_seed"],
                   "params": data["params"], "input": data["input"], "processing_steps": data["input"].get("processing_steps", []),
                   "window_overrides": {str(it["index"]): {"accepted": it["accepted"], "reason": it["reason"]}
                                        for it in data["windows"]["items"] if it.get("reason") == "manual"}},
                  fh, indent=1, allow_nan=False)
    written.append("config.json")

    if data.get("azimuthal"):
        az = data["azimuthal"]
        with open(exp / "azimuthal.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["# Azimuthal HVSR: rows = azimuth (deg clockwise from north), columns = frequency (Hz)"])
            w.writerow(["azimuth_deg"] + [_fmt(f) for f in az["frequency"]])
            for a, row in zip(az["azimuths"], az["matrix"]):
                w.writerow([_fmt(a)] + [_fmt(v) for v in row])
        written.append("azimuthal.csv")
    return written


def summary_dict(data: dict) -> dict:
    pk = data["peaks"]
    sel = pk.get("selected") or {}
    pv = data.get("peak_variability") or {}
    bs = pv.get("bootstrap") or {}
    ses = data.get("sesame") or {}
    return {
        "engine_version": data["engine_version"],
        "computed_at": data["computed_at"],
        "station": data["input"].get("station"),
        "is_synthetic": data["input"].get("is_synthetic"),
        "input_sha256": data["input"].get("sha256"),
        "fs_hz": data["input"].get("fs"),
        "duration_s": data["input"].get("duration_s"),
        "window_length_s": data["windows"]["length_s"],
        "overlap": data["windows"]["overlap"],
        "windows_total": data["windows"]["count_total"],
        "windows_accepted": data["windows"]["count_accepted"],
        "horizontal_method": data["method"]["horizontal_method"],
        "combination_stage": data["method"]["combination_stage"],
        "mean_method": data["method"]["mean_method"],
        "smoothing_bandwidth": (data["method"]["smoothing"] or {}).get("bandwidth"),
        "peak_status": pk.get("status"),
        "peak_source": sel.get("source"),
        "f0_hz": sel.get("frequency"),
        "a0": sel.get("amplitude"),
        "window_f0_median_hz": pv.get("median"),
        "window_f0_p16_hz": pv.get("p16"),
        "window_f0_p84_hz": pv.get("p84"),
        "window_f0_std_hz": pv.get("std"),
        "window_f0_std_ln": pv.get("std_ln"),
        "bootstrap_f0_p2_5_hz": bs.get("f0_p2_5"),
        "bootstrap_f0_p97_5_hz": bs.get("f0_p97_5"),
        "bootstrap_seed": bs.get("seed"),
        "sesame_reliability_passed": ses.get("reliability_passed"),
        "sesame_clarity_passed_count": ses.get("clarity_passed_count"),
        "sesame_clarity_passed": ses.get("clarity_passed"),
        "quality_flags": ";".join(f["code"] for f in data.get("quality_flags", [])),
    }


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def select_peak(output_dir: str | Path, frequency: float | None) -> dict:
    """Re-evaluate the peak block (and SESAME criteria) for a manual or automatic selection."""
    out = Path(output_dir)
    data = load_result(out)
    freq = np.array(data["frequency"], dtype=np.float64)
    sel_method = data["curves"]["selected"]
    main = np.array([np.nan if v is None else v for v in data["curves"][sel_method]["values"]], dtype=np.float64)
    geo_vals = np.array([np.nan if v is None else v for v in data["curves"]["geometric"]["values"]], dtype=np.float64)
    geo_sig = np.array([np.nan if v is None else v for v in data["curves"]["geometric"].get("sigma_ln", [None] * len(freq))],
                       dtype=np.float64)
    n_acc = data["windows"]["count_accepted"]
    min_valid = int(data["params"].get("min_valid_windows", 3))
    pk = peaks_mod.peaks_block(freq, main, data["params"], n_acc, min_valid, frequency)
    data["peaks"] = pk
    if data["params"].get("sesame", True):
        f0 = pk["selected"]["frequency"] if pk["selected"] else None
        a0 = None
        if f0 is not None:
            i0 = int(np.argmin(np.abs(freq - f0)))
            a0 = float(geo_vals[i0]) if np.isfinite(geo_vals[i0]) else None
        wf = np.array([np.nan if v is None else v for v in data["peak_variability"].get("window_f0", [])], dtype=np.float64)
        lw_eff = data["windows"].get("mean_accepted_length_s") or data["windows"]["length_s"]
        data["sesame"] = sesame_mod.evaluate(freq, geo_vals, geo_sig, f0, a0, lw_eff, n_acc, wf,
                                             tuple(pk["search_range"]))
    data = _sanitize(data)
    with open(out / "result.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, allow_nan=False)
    write_exports(data, out)
    return data
