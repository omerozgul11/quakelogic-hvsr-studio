"""Azimuthal (rotational) HVSR: H_θ(f) = N(f)·cos θ + E(f)·sin θ on the per-window complex spectra."""
from __future__ import annotations

import numpy as np

from .peaks import highest_peak
from .smoothing import smooth
from .statistics import aggregate


def azimuthal_matrix(n_spec, e_spec, z_smooth: np.ndarray, matrix,
                     freq_out: np.ndarray, step_deg: float, mean_method: str, min_valid: int,
                     search_range: tuple[float, float], progress=None, cancel=None) -> dict:
    """``n_spec``/``e_spec``: complex spectra (already ·dt) of the accepted windows — either 2-D arrays
    (n_windows, n_fft) with one smoothing ``matrix``, or lists of 1-D arrays with a list of matrices
    (one per window) when the windows have different lengths; ``z_smooth``: smoothed vertical
    amplitude (n_windows, n_out) with NaN where masked."""
    from .errors import CancelledError

    step = float(step_deg)
    if step <= 0 or step > 90:
        raise ValueError("Azimuth step must be in (0, 90] degrees")
    azimuths = np.arange(0.0, 180.0, step)
    mat = np.full((len(azimuths), len(freq_out)), np.nan)
    pf, pa = [], []
    for i, az in enumerate(azimuths):
        if cancel is not None and cancel.is_set():
            raise CancelledError()
        rad = np.deg2rad(az)
        if isinstance(matrix, (list, tuple)):
            hs = np.vstack([smooth(np.abs(n_k * np.cos(rad) + e_k * np.sin(rad)), m_k)
                            for n_k, e_k, m_k in zip(n_spec, e_spec, matrix)])
        else:
            h = np.abs(np.asarray(n_spec) * np.cos(rad) + np.asarray(e_spec) * np.sin(rad))
            hs = smooth(h, matrix)
        with np.errstate(all="ignore"):
            hv = hs / z_smooth
        agg = aggregate(hv, mean_method, min_valid)
        mat[i] = agg["values"]
        f, a = highest_peak(freq_out, agg["values"], *search_range)
        pf.append(f)
        pa.append(a)
        if progress:
            progress((i + 1) / len(azimuths))
    return {
        "azimuths": azimuths.tolist(), "frequency": np.asarray(freq_out).tolist(),
        "matrix": mat, "peak_frequency": pf, "peak_amplitude": pa,
        "definition": "H_θ(f) = N(f)cosθ + E(f)sinθ (θ clockwise from north), smoothed identically to the "
                      "components, divided by the smoothed vertical spectrum, aggregated over accepted windows "
                      f"with the {mean_method} mean.",
    }
