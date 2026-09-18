"""Fourier amplitude spectra, Welch PSD and spectrograms.

Definitions
-----------
* Fourier amplitude spectrum (FAS): |X(f)|·dt where X = rfft(x). Units: signal units × s.
  This is the (one-sided) continuous-Fourier-transform estimate; scaling cancels in a
  ratio but is kept consistent for all components.
* PSD: Welch estimate (scipy.signal.welch, density scaling) in units² / Hz.
* Spectrogram: 10·log10 of the short-time PSD.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

from .io.canonical import Recording
from .smoothing import konno_ohmachi_matrix, log_frequency_axis, smooth
from .windows import make_windows


def tukey_taper(n: int, percent: float) -> np.ndarray:
    """Cosine (Tukey) taper; ``percent`` is the tapered fraction at EACH end (ObsPy style)."""
    alpha = min(1.0, max(0.0, 2.0 * float(percent) / 100.0))
    return signal.windows.tukey(n, alpha=alpha, sym=True)


def prepare_window(x: np.ndarray, detrend: str = "linear", taper_percent: float = 5.0) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if detrend == "linear":
        x = signal.detrend(x, type="linear")
    elif detrend in ("constant", "mean"):
        x = x - np.mean(x)
    return x * tukey_taper(len(x), taper_percent)


def fourier_amplitude(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """(frequencies, |X(f)|·dt) of a real signal."""
    x = np.asarray(x, dtype=np.float64)
    spec = np.fft.rfft(x)
    return np.fft.rfftfreq(len(x), d=1.0 / fs), np.abs(spec) / fs


def fourier_complex(x: np.ndarray, fs: float) -> np.ndarray:
    return np.fft.rfft(np.asarray(x, dtype=np.float64)) / fs


def _select(rec: Recording, t_start, t_end) -> Recording:
    if t_start is None and t_end is None:
        return rec
    i0 = 0 if t_start is None else max(0, int(np.floor(float(t_start) * rec.fs)))
    i1 = rec.n_samples if t_end is None else min(rec.n_samples, int(np.ceil(float(t_end) * rec.fs)))
    if i1 - i0 < 2:
        raise ValueError("Selected time range is too short")
    return Recording(rec.n[i0:i1], rec.e[i0:i1], rec.z[i0:i1], rec.fs, rec.start_time, rec.meta)


def window_amplitude_spectra(x: np.ndarray, fs: float, windows: list[tuple[int, int]],
                             detrend: str = "linear", taper_percent: float = 5.0) -> tuple[np.ndarray, np.ndarray]:
    """Per-window FAS: returns (frequencies, array (n_windows, n_freq))."""
    if not windows:
        raise ValueError("Record is shorter than one window")
    nwin = windows[0][1] - windows[0][0]
    freqs = np.fft.rfftfreq(nwin, d=1.0 / fs)
    out = np.empty((len(windows), len(freqs)))
    for i, (s, e) in enumerate(windows):
        out[i] = np.abs(np.fft.rfft(prepare_window(x[s:e], detrend, taper_percent))) / fs
    return freqs, out


def compute_spectra(rec: Recording, params: dict) -> dict:
    kind = params.get("kind", "fas")
    comps = list(params.get("components") or ["n", "e", "z"])
    rec = _select(rec, params.get("t_start"), params.get("t_end"))
    length_s = float(params.get("window_length_s", 60.0))
    overlap = float(params.get("overlap", 0.5))
    taper_percent = float(params.get("taper_percent", 5.0))
    detrend = params.get("detrend", "linear")
    units = rec.meta.get("units", "counts")
    nyq = rec.fs / 2.0
    fmin = float(params.get("freq_min", max(1.0 / length_s, 0.05)))
    fmax = min(float(params.get("freq_max", nyq)), nyq)
    n_freq = int(params.get("n_freq", 300))
    if length_s * rec.fs > rec.n_samples:
        length_s = rec.duration_s
    windows = make_windows(rec.n_samples, rec.fs, length_s, overlap)

    if kind == "fas":
        smoothing = params.get("smoothing") or {"type": "konno_ohmachi", "bandwidth": 40}
        result = {"kind": "fas", "units": f"{units}*s", "window_length_s": length_s, "overlap": overlap,
                  "n_windows": len(windows), "components": {},
                  "definition": "mean over windows of |rfft(detrended, tapered window)|·dt"}
        freqs = None
        comp_mean = {}
        for name in comps:
            freqs, spec = window_amplitude_spectra(rec.component(name), rec.fs, windows, detrend, taper_percent)
            comp_mean[name] = spec.mean(axis=0)
        if smoothing.get("type") == "konno_ohmachi":
            f_out = log_frequency_axis(max(fmin, freqs[1]), fmax, n_freq)
            matrix = konno_ohmachi_matrix(freqs, f_out, float(smoothing.get("bandwidth", 40)))
            for name in comps:
                result["components"][name] = smooth(comp_mean[name], matrix).tolist()
            result["frequency"] = f_out.tolist()
            result["smoothing"] = {"type": "konno_ohmachi", "bandwidth": float(smoothing.get("bandwidth", 40))}
        else:
            sel = (freqs >= fmin) & (freqs <= fmax)
            result["frequency"] = freqs[sel].tolist()
            for name in comps:
                result["components"][name] = comp_mean[name][sel].tolist()
            result["smoothing"] = {"type": "none"}
        return result

    nperseg = int(round(length_s * rec.fs))
    noverlap = int(round(nperseg * overlap))
    if kind == "psd":
        result = {"kind": "psd", "units": f"{units}^2/Hz", "window_length_s": length_s, "overlap": overlap,
                  "components": {}, "definition": "Welch PSD (density scaling, Tukey taper, linear detrend)"}
        for name in comps:
            f, pxx = signal.welch(rec.component(name), fs=rec.fs, window=tukey_taper(nperseg, taper_percent),
                                  nperseg=nperseg, noverlap=noverlap, detrend=detrend if detrend else False,
                                  scaling="density")
            sel = (f >= fmin) & (f <= fmax)
            result["frequency"] = f[sel].tolist()
            result["components"][name] = pxx[sel].tolist()
        return result

    if kind == "spectrogram":
        seg_s = float(params.get("segment_length_s", min(length_s, 20.0)))
        nperseg = max(16, int(round(seg_s * rec.fs)))
        noverlap = int(round(nperseg * overlap))
        max_t = int(params.get("max_time_bins", 600))
        result = {"kind": "spectrogram", "units": f"dB rel. 1 ({units})^2/Hz", "segment_length_s": nperseg / rec.fs,
                  "components": {}, "definition": "10·log10 of the short-time Welch PSD"}
        for name in comps:
            f, t, sxx = signal.spectrogram(rec.component(name), fs=rec.fs, window=tukey_taper(nperseg, taper_percent),
                                           nperseg=nperseg, noverlap=noverlap, detrend=detrend if detrend else False,
                                           scaling="density", mode="psd")
            sel = (f >= fmin) & (f <= fmax)
            sxx = sxx[sel]
            f = f[sel]
            if len(t) > max_t:
                step = int(np.ceil(len(t) / max_t))
                t = t[::step]
                sxx = sxx[:, ::step]
            db = 10.0 * np.log10(np.maximum(sxx, np.finfo(float).tiny))
            result["components"][name] = {"t": t.tolist(), "f": f.tolist(), "db": np.round(db, 2).tolist()}
        return result
    raise ValueError(f"Unknown spectra kind: {kind}")
