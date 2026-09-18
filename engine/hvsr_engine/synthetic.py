"""Synthetic three-component recordings with a KNOWN HVSR shape (for tests and examples).

Model
-----
Horizontal components are independent Gaussian white-noise sequences passed (in the
frequency domain) through the absolute-transmissibility response of a damped 1-DOF
oscillator:

    H(f) = (1 + 2iξr) / (1 − r² + 2iξr),   r = f / f0

so |H| → 1 at low frequency, |H(f0)| = sqrt(1 + 4ξ²) / (2ξ) at resonance and |H| → 0 above.
The vertical component is independent white noise with the same variance. Because the
expected Fourier amplitude of each white-noise realisation is flat, the expected
horizontal-to-vertical ratio is |H(f)|; ``expected_hvsr`` returns it for comparison.
For a requested peak amplitude A0 the damping is ξ = 1 / (2·sqrt(A0² − 1)).

Everything produced here is SYNTHETIC. It is not a field measurement.
"""
from __future__ import annotations

import numpy as np

from .io.canonical import Recording, format_time
from datetime import datetime, timezone


def damping_for_amplification(a0: float) -> float:
    if a0 <= 1.0:
        raise ValueError("Amplification must exceed 1")
    return 1.0 / (2.0 * np.sqrt(a0 ** 2 - 1.0))


def transfer_function(f: np.ndarray, f0: float, damping: float) -> np.ndarray:
    r = np.asarray(f, dtype=np.float64) / f0
    return (1.0 + 2j * damping * r) / (1.0 - r ** 2 + 2j * damping * r)


def expected_hvsr(f: np.ndarray, f0: float, damping: float) -> np.ndarray:
    return np.abs(transfer_function(f, f0, damping))


def synthetic_recording(fs: float = 100.0, duration_s: float = 1200.0, f0: float = 2.5,
                        amplification: float = 5.0, damping: float | None = None, seed: int = 0,
                        transients: list[dict] | None = None, noise_std: float = 100.0,
                        station: str = "SYN", start_time: str | None = None,
                        horizontal_ratio_ne: float = 1.0) -> Recording:
    """Return a synthetic Recording.

    ``transients``: list of ``{"time_s": t, "amplitude": a, "duration_s": d}`` — decaying
    bursts added to all components (to exercise STA/LTA screening).
    ``horizontal_ratio_ne``: scale applied to N relative to E (directional tests).
    """
    if damping is None:
        damping = damping_for_amplification(amplification)
    rng = np.random.default_rng(seed)
    n = int(round(duration_s * fs))
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    h = transfer_function(freqs, f0, damping)

    def shaped_noise():
        white = rng.normal(0.0, noise_std, n)
        return np.fft.irfft(np.fft.rfft(white) * h, n=n)

    north = shaped_noise() * horizontal_ratio_ne
    east = shaped_noise()
    vert = rng.normal(0.0, noise_std, n)
    t = np.arange(n) / fs
    for tr in transients or []:
        t0, amp, dur = float(tr["time_s"]), float(tr["amplitude"]), float(tr.get("duration_s", 2.0))
        mask = (t >= t0) & (t < t0 + dur)
        burst = amp * noise_std * np.exp(-(t[mask] - t0) / (dur / 4.0)) * np.sin(2 * np.pi * 8.0 * (t[mask] - t0))
        north[mask] += burst
        east[mask] += burst
        vert[mask] += burst
    start = start_time or format_time(datetime(2025, 1, 1, tzinfo=timezone.utc))
    meta = {
        "station": station, "network": "XX", "location": "",
        "channels": {"n": "HHN", "e": "HHE", "z": "HHZ"},
        "units": "counts", "unit_kind": "raw", "orientation_deg": 0.0, "is_synthetic": True,
        "synthetic_model": {"f0": f0, "damping": damping, "amplification": float(np.abs(transfer_function(np.array([f0]), f0, damping))[0]),
                            "seed": seed, "noise_std": noise_std, "horizontal_ratio_ne": horizontal_ratio_ne},
    }
    return Recording(north, east, vert, fs, start, meta)
