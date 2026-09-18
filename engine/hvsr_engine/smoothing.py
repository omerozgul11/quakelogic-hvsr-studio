"""Konno–Ohmachi spectral smoothing.

Konno, K. & Ohmachi, T. (1998). Ground-motion characteristics estimated from spectral
ratio between horizontal and vertical components of microtremor. Bull. Seismol. Soc. Am.
88(1), 228–241.

    W(f, fc) = [ sin(b·log10(f/fc)) / (b·log10(f/fc)) ]^4

with W = 1 at f = fc and W = 0 at f = 0. The bandwidth coefficient ``b`` (default 40)
controls the width: larger ``b`` = narrower window. Weights are row-normalised so a
flat spectrum is unchanged by smoothing. The same matrix is applied to all components.
"""
from __future__ import annotations

import numpy as np


def konno_ohmachi_weights(f_in: np.ndarray, fc: float, bandwidth: float) -> np.ndarray:
    """Normalised K–O weights of the input frequencies ``f_in`` for one centre frequency."""
    f_in = np.asarray(f_in, dtype=np.float64)
    w = np.zeros_like(f_in)
    positive = f_in > 0
    x = bandwidth * np.log10(f_in[positive] / fc)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.sin(x) / x
    s[x == 0] = 1.0
    w[positive] = s ** 4
    total = w.sum()
    return w / total if total > 0 else w


def konno_ohmachi_matrix(f_in: np.ndarray, f_out: np.ndarray, bandwidth: float = 40.0,
                         min_weight: float = 1e-8) -> np.ndarray:
    """Return an (n_out, n_in) matrix ``M`` such that ``smoothed = M @ spectrum``.

    Rows are normalised to sum to 1 (over the available input bins). Weights below
    ``min_weight`` (relative) are truncated to zero to keep the matrix well-conditioned.
    ``f_in`` may contain 0 (DC), which receives zero weight.
    """
    f_in = np.asarray(f_in, dtype=np.float64)
    f_out = np.asarray(f_out, dtype=np.float64)
    if bandwidth <= 0:
        raise ValueError("Konno–Ohmachi bandwidth must be positive")
    if np.any(f_out <= 0):
        raise ValueError("Output frequencies must be positive")
    positive = f_in > 0
    log_in = np.full_like(f_in, np.nan)
    log_in[positive] = np.log10(f_in[positive])
    log_out = np.log10(f_out)
    x = bandwidth * (log_in[None, :] - log_out[:, None])  # (n_out, n_in)
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.sin(x) / x
    s = np.where(x == 0, 1.0, s)
    w = np.nan_to_num(s, nan=0.0) ** 4
    w[:, ~positive] = 0.0
    w[w < min_weight] = 0.0
    sums = w.sum(axis=1, keepdims=True)
    sums[sums == 0] = 1.0
    return w / sums


def smooth(spectra: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Apply the smoothing matrix to one spectrum (n_in,) or many (n_windows, n_in)."""
    spectra = np.asarray(spectra, dtype=np.float64)
    if spectra.ndim == 1:
        return matrix @ spectra
    return spectra @ matrix.T


def log_frequency_axis(freq_min: float, freq_max: float, n_freq: int) -> np.ndarray:
    if freq_min <= 0 or freq_max <= freq_min:
        raise ValueError("Require 0 < freq_min < freq_max")
    if n_freq < 2:
        raise ValueError("n_freq must be >= 2")
    return np.logspace(np.log10(freq_min), np.log10(freq_max), int(n_freq))
