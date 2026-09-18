"""Signal-processing toolbox: an ordered list of explicit, recorded operations.

Nothing here is applied automatically. Every step and its effective parameters are
returned in ``applied`` so the processing history is reproducible.
"""
from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy import signal

from .errors import ProcessingError
from .io.canonical import Recording
from .spectra import tukey_taper

VALID_OPS = ("demean", "detrend", "polynomial", "filter", "notch", "taper", "crop", "resample", "rotate",
             "remove_response")


def _warn(warnings: list, idx: int, code: str, message: str) -> None:
    warnings.append({"step_index": idx, "code": code, "message": message})


# ---------------------------------------------------------------------------
# Filter design
# ---------------------------------------------------------------------------

def _design_filter(fs: float, params: dict, warnings: list | None = None, idx: int = -1) -> np.ndarray:
    """Butterworth design in second-order sections; raises ProcessingError for impossible designs."""
    nyq = fs / 2.0
    kind = params.get("kind", "bandpass")
    order = int(params.get("order", 4))
    if order < 1:
        raise ProcessingError("Filter order must be at least 1", "invalid_filter")
    if order > 8 and warnings is not None:
        _warn(warnings, idx, "high_order", f"Filter order {order} is high; the response may be numerically sensitive near the cutoffs.")
    lo = params.get("freq_low")
    hi = params.get("freq_high")
    if kind == "highpass":
        cut = float(lo if lo is not None else params.get("freq", 0))
        _check_cut(cut, nyq)
        wn = cut
        btype = "highpass"
    elif kind == "lowpass":
        cut = float(hi if hi is not None else params.get("freq", 0))
        _check_cut(cut, nyq)
        wn = cut
        btype = "lowpass"
    elif kind in ("bandpass", "bandstop"):
        if lo is None or hi is None:
            raise ProcessingError("Band filters need freq_low and freq_high", "invalid_filter")
        lo, hi = float(lo), float(hi)
        _check_cut(lo, nyq)
        _check_cut(hi, nyq)
        if lo >= hi:
            raise ProcessingError(f"freq_low ({lo:g} Hz) must be below freq_high ({hi:g} Hz)", "band_inverted")
        wn = [lo, hi]
        btype = kind
    else:
        raise ProcessingError(f"Unknown filter kind {kind}", "invalid_filter")
    if warnings is not None:
        top = wn[1] if isinstance(wn, list) else wn
        if top > 0.9 * nyq:
            _warn(warnings, idx, "cutoff_near_nyquist", f"Cutoff {top:g} Hz is within 10 % of the Nyquist frequency ({nyq:g} Hz).")
    return signal.butter(order, wn, btype=btype, fs=fs, output="sos")


def _check_cut(cut: float, nyq: float) -> None:
    if not np.isfinite(cut) or cut <= 0:
        raise ProcessingError(f"Cutoff frequency must be positive (got {cut!r})", "cutoff_not_positive")
    if cut >= nyq:
        raise ProcessingError(f"Cutoff {cut:g} Hz must be below the Nyquist frequency {nyq:g} Hz", "cutoff_above_nyquist")


def _design_notch(fs: float, params: dict, warnings: list | None = None, idx: int = -1) -> np.ndarray:
    nyq = fs / 2.0
    f0 = float(params.get("frequency", 50.0))
    q = float(params.get("quality", 30.0))
    harmonics = max(1, int(params.get("harmonics", 1)))
    if f0 <= 0:
        raise ProcessingError("Notch frequency must be positive", "cutoff_not_positive")
    if f0 >= nyq:
        raise ProcessingError(f"Notch frequency {f0:g} Hz must be below the Nyquist frequency {nyq:g} Hz", "cutoff_above_nyquist")
    if q <= 0:
        raise ProcessingError("Notch quality factor must be positive", "invalid_filter")
    sos_list = []
    for k in range(1, harmonics + 1):
        fk = k * f0
        if fk >= nyq:
            if warnings is not None:
                _warn(warnings, idx, "cutoff_above_nyquist", f"Harmonic {k} ({fk:g} Hz) is above Nyquist and was skipped.")
            break
        b, a = signal.iirnotch(fk, q, fs=fs)
        sos_list.append(signal.tf2sos(b, a))
    return np.vstack(sos_list)


def filter_response(fs: float, step: dict, n_points: int = 1024) -> dict:
    """Magnitude/phase response of a filter or notch step on a log-spaced frequency axis."""
    warnings: list = []
    params = step.get("params", {})
    op = step.get("op", "filter")
    if op == "filter":
        sos = _design_filter(fs, params, warnings, 0)
    elif op == "notch":
        sos = _design_notch(fs, params, warnings, 0)
    else:
        raise ProcessingError(f"No frequency response for op {op}", "invalid_filter")
    nyq = fs / 2.0
    freqs = np.logspace(np.log10(max(1e-3, nyq / 1e4)), np.log10(nyq * 0.999), int(n_points))
    _, h = signal.sosfreqz(sos, worN=freqs, fs=fs)
    mag = np.abs(h)
    zero_phase = bool(params.get("zero_phase", True))
    if zero_phase:
        mag = mag ** 2  # forward-backward application squares the magnitude response
        phase = np.zeros_like(mag)
    else:
        phase = np.degrees(np.unwrap(np.angle(h)))
    with np.errstate(divide="ignore"):
        mag_db = 20.0 * np.log10(np.maximum(mag, 1e-12))
    return {"frequency": freqs.tolist(), "magnitude_db": mag_db.tolist(), "phase_deg": phase.tolist(),
            "zero_phase": zero_phase, "nyquist": nyq, "warnings": warnings}


# ---------------------------------------------------------------------------
# Individual operations
# ---------------------------------------------------------------------------

def _apply_each(rec: Recording, fn) -> None:
    rec.n, rec.e, rec.z = fn(rec.n), fn(rec.e), fn(rec.z)


def op_demean(rec, params, warnings, idx):
    _apply_each(rec, lambda x: x - np.mean(x))
    return {}


def op_detrend(rec, params, warnings, idx):
    _apply_each(rec, lambda x: signal.detrend(x, type="linear"))
    return {}


def op_polynomial(rec, params, warnings, idx):
    order = int(params.get("order", 2))
    if not 1 <= order <= 10:
        raise ProcessingError("Polynomial order must be between 1 and 10", "invalid_parameter")
    if order > 5:
        _warn(warnings, idx, "polynomial_high_order", f"A degree-{order} baseline removes low-frequency signal; use with care.")
    t = np.linspace(-1.0, 1.0, rec.n_samples)

    def fit(x):
        poly = np.polynomial.Polynomial.fit(t, x, order)
        return x - poly(t)
    _apply_each(rec, fit)
    return {"order": order}


def op_filter(rec, params, warnings, idx):
    sos = _design_filter(rec.fs, params, warnings, idx)
    zero_phase = bool(params.get("zero_phase", True))
    lowest = params.get("freq_low") if params.get("kind") in ("highpass", "bandpass", "bandstop") else None
    if lowest:
        transient = int(params.get("order", 4)) / float(lowest)
        if rec.duration_s < 10.0 / float(lowest):
            _warn(warnings, idx, "record_short_for_filter",
                  f"The record ({rec.duration_s:.0f} s) holds fewer than 10 periods of the {float(lowest):g} Hz cutoff.")
        if 2 * transient > 0.05 * rec.duration_s:
            _warn(warnings, idx, "edge_effects",
                  f"Filter transients (~{transient:.0f} s at each end) exceed 5 % of the record; consider tapering or cropping the ends.")
    if zero_phase:
        _apply_each(rec, lambda x: signal.sosfiltfilt(sos, x))
    else:
        _apply_each(rec, lambda x: signal.sosfilt(sos, x))
    return {"kind": params.get("kind"), "freq_low": params.get("freq_low"), "freq_high": params.get("freq_high"),
            "order": int(params.get("order", 4)), "zero_phase": zero_phase, "design": "Butterworth (SOS)"}


def op_notch(rec, params, warnings, idx):
    sos = _design_notch(rec.fs, params, warnings, idx)
    zero_phase = bool(params.get("zero_phase", True))
    if zero_phase:
        _apply_each(rec, lambda x: signal.sosfiltfilt(sos, x))
    else:
        _apply_each(rec, lambda x: signal.sosfilt(sos, x))
    return {"frequency": float(params.get("frequency", 50.0)), "quality": float(params.get("quality", 30.0)),
            "harmonics": int(params.get("harmonics", 1)), "zero_phase": zero_phase, "sections": int(sos.shape[0])}


def op_taper(rec, params, warnings, idx):
    percent = float(params.get("percent", 5.0))
    if not 0 <= percent <= 50:
        raise ProcessingError("Taper percent must be between 0 and 50 (per side)", "invalid_parameter")
    w = tukey_taper(rec.n_samples, percent)
    _apply_each(rec, lambda x: x * w)
    return {"percent": percent, "type": "cosine (Tukey), per side"}


def op_crop(rec, params, warnings, idx):
    start = float(params.get("start_s") or 0.0)
    end = params.get("end_s")
    end = rec.duration_s if end is None else float(end)
    if start < 0 or end <= start or start >= rec.duration_s:
        raise ProcessingError("Invalid crop range", "invalid_parameter")
    i0 = int(round(start * rec.fs))
    i1 = min(rec.n_samples, int(round(end * rec.fs)))
    if i1 - i0 < 2:
        raise ProcessingError("Crop range is too short", "invalid_parameter")
    from datetime import timedelta
    from .io.canonical import format_time
    rec.start_time = format_time(rec.start_datetime() + timedelta(seconds=i0 / rec.fs))
    rec.n, rec.e, rec.z = rec.n[i0:i1].copy(), rec.e[i0:i1].copy(), rec.z[i0:i1].copy()
    return {"start_s": i0 / rec.fs, "end_s": i1 / rec.fs}


def op_resample(rec, params, warnings, idx):
    target = float(params.get("target_rate", 0))
    method = params.get("method", "decimate")
    if target <= 0:
        raise ProcessingError("Target sample rate must be positive", "invalid_parameter")
    if abs(target - rec.fs) < 1e-9:
        return {"target_rate": target, "method": method, "note": "no change"}
    if target > rec.fs:
        _warn(warnings, idx, "resample_upsampling", f"Upsampling from {rec.fs:g} to {target:g} Hz adds no information.")
    if method == "decimate":
        ratio = rec.fs / target
        if abs(ratio - round(ratio)) > 1e-9 or ratio < 1:
            raise ProcessingError(f"Decimation needs an integer factor ({rec.fs:g}/{target:g} is not); use the polyphase method",
                                  "resample_not_integer")
        q = int(round(ratio))
        _apply_each(rec, lambda x: signal.resample_poly(x, 1, q))
        detail = {"factor": q, "anti_alias": "Kaiser-windowed FIR low-pass at the new Nyquist frequency "
                                             "(scipy.signal.resample_poly, up=1), zero-phase"}
    elif method == "polyphase":
        frac = Fraction(target / rec.fs).limit_denominator(10000)
        up, down = frac.numerator, frac.denominator
        _apply_each(rec, lambda x: signal.resample_poly(x, up, down))
        detail = {"up": up, "down": down, "anti_alias": "Kaiser-windowed FIR low-pass (scipy.signal.resample_poly), zero-phase"}
    else:
        raise ProcessingError(f"Unknown resample method {method}", "invalid_parameter")
    rec.fs = target
    return {"target_rate": target, "method": method, **detail}




def rotate_horizontals(n: np.ndarray, e: np.ndarray, azimuth_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Rotate recorded horizontals to true north/east.

    ``azimuth_deg`` is the azimuth of the sensor's N axis measured clockwise from true
    north. With N' and E' the recorded components:
        N_true = N'·cos α − E'·sin α
        E_true = N'·sin α + E'·cos α
    """
    a = np.deg2rad(float(azimuth_deg))
    return n * np.cos(a) - e * np.sin(a), n * np.sin(a) + e * np.cos(a)


def op_rotate(rec, params, warnings, idx):
    az = float(params.get("azimuth_deg", 0.0))
    rec.n, rec.e = rotate_horizontals(rec.n, rec.e, az)
    prev = float(rec.meta.get("orientation_deg", 0.0) or 0.0)
    rec.meta["orientation_deg"] = prev - az
    return {"azimuth_deg": az, "convention": "sensor N-axis azimuth clockwise from true north; output is true N/E"}


def op_remove_response(rec, params, warnings, idx):
    import obspy
    from obspy import UTCDateTime

    source = params.get("source", "stationxml")
    output = params.get("output", "VEL").upper()
    if output not in ("DISP", "VEL", "ACC"):
        raise ProcessingError("output must be DISP, VEL or ACC", "invalid_parameter")
    water_level = params.get("water_level", 60)
    pre_filt = params.get("pre_filt")
    chans = rec.meta.get("channels", {"n": "HHN", "e": "HHE", "z": "HHZ"})
    if not (rec.meta.get("steps") and any(st.get("op") == "taper" for st in rec.meta["steps"])):
        _warn(warnings, idx, "edge_effects", "Response removal is a frequency-domain deconvolution; without a preceding "
                                             "taper step the record ends may ring. No taper is applied automatically.")
    stats = {"network": rec.meta.get("network", ""), "station": rec.meta.get("station", ""),
             "location": rec.meta.get("location", ""), "sampling_rate": rec.fs,
             "starttime": UTCDateTime(rec.start_time)}
    stream = obspy.Stream()
    for name in ("n", "e", "z"):
        tr = obspy.Trace(rec.component(name).copy(), header={**stats, "channel": chans.get(name, name.upper())})
        stream.append(tr)
    if source == "stationxml":
        path = params.get("path")
        if not path:
            raise ProcessingError("A StationXML file path is required", "response_missing")
        inv = obspy.read_inventory(path)
        for tr in stream:
            try:
                tr.remove_response(inventory=inv, output=output, water_level=water_level,
                                   pre_filt=tuple(pre_filt) if pre_filt else None, taper=False)
            except Exception as exc:  # no matching response
                raise ProcessingError(f"No response found for {tr.id} at {tr.stats.starttime}: {exc}", "response_missing")
        detail = {"source": "stationxml", "path": path}
    elif source == "paz":
        paz_in = params.get("paz") or {}
        if not paz_in or (not paz_in.get("poles") and not paz_in.get("zeros") and not paz_in.get("sensitivity")):
            raise ProcessingError("PAZ must include poles/zeros and a sensitivity", "response_missing")
        paz = {"poles": [complex(*p) if isinstance(p, (list, tuple)) else complex(p) for p in paz_in.get("poles", [])],
               "zeros": [complex(*z) if isinstance(z, (list, tuple)) else complex(z) for z in paz_in.get("zeros", [])],
               "gain": float(paz_in.get("gain", 1.0)), "sensitivity": float(paz_in.get("sensitivity", 1.0))}
        paz_units = paz_in.get("units", "VEL").upper()
        for tr in stream:
            tr.simulate(paz_remove=paz, water_level=water_level, pre_filt=tuple(pre_filt) if pre_filt else None,
                        taper=False, pitsasim=False)
            _convert_units(tr, paz_units, output)
        detail = {"source": "paz", "paz_units": paz_units, "n_poles": len(paz["poles"]), "n_zeros": len(paz["zeros"])}
    else:
        raise ProcessingError(f"Unknown response source {source}", "invalid_parameter")
    for name, tr in zip(("n", "e", "z"), stream):
        setattr(rec, name, np.asarray(tr.data, dtype=np.float64))
    rec.meta["units"] = {"DISP": "m", "VEL": "m/s", "ACC": "m/s^2"}[output]
    rec.meta["unit_kind"] = {"DISP": "displacement", "VEL": "velocity", "ACC": "acceleration"}[output]
    return {"output": output, "water_level": water_level, "pre_filt": pre_filt, **detail}


def _convert_units(tr, have: str, want: str) -> None:
    order = {"DISP": 0, "VEL": 1, "ACC": 2}
    diff = order[want] - order[have]
    for _ in range(diff):
        tr.differentiate()
    for _ in range(-diff):
        tr.integrate()


OPS = {
    "demean": op_demean, "detrend": op_detrend, "polynomial": op_polynomial, "filter": op_filter, "notch": op_notch,
    "taper": op_taper, "crop": op_crop, "resample": op_resample, "rotate": op_rotate, "remove_response": op_remove_response,
}


def apply_steps(rec: Recording, steps: list[dict], progress=None) -> tuple[Recording, list, list]:
    """Apply ``steps`` in order to a COPY of ``rec``. Returns (recording, warnings, applied)."""
    out = rec.copy()
    warnings: list = []
    applied: list = []
    active = [s for s in (steps or []) if s.get("enabled", True)]
    n_filters = sum(1 for s in active if s.get("op") in ("filter", "notch"))
    if len(active) > 8 or n_filters > 2:
        _warn(warnings, -1, "excessive_processing",
              f"{len(active)} operations including {n_filters} filters: heavy processing can bias the spectral ratio.")
    if any(s.get("op") == "polynomial" for s in active) and any(s.get("op") == "detrend" for s in active):
        _warn(warnings, -1, "redundant_detrend", "Both linear detrend and polynomial baseline correction are enabled.")
    for i, step in enumerate(steps or []):
        if not step.get("enabled", True):
            continue
        op = step.get("op")
        if op not in OPS:
            raise ProcessingError(f"Unknown operation {op!r}", "invalid_step")
        params = dict(step.get("params") or {})
        if np.isnan(out.n).any() or np.isnan(out.e).any() or np.isnan(out.z).any():
            raise ProcessingError("The recording contains NaN values; processing refuses to run (no interpolation is performed).",
                                  "nan_values")
        effective = OPS[op](out, params, warnings, i)
        applied.append({"index": i, "op": op, "params": params, "effective": effective, "fs_after": out.fs,
                        "n_samples_after": out.n_samples})
        if progress:
            progress((i + 1) / max(1, len(steps)), f"{op}")
    out.meta["steps"] = applied
    out.meta["parent"] = rec.meta.get("source_path")
    return out, warnings, applied
