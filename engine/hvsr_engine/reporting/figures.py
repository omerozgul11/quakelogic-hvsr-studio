"""Static figures of an HVSR result rendered with matplotlib (Agg backend).

Every figure is built from the ``result.json`` dictionary described in
``docs/architecture.md`` so that export works without the live engine state.
"""

from __future__ import annotations

import os
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

NAVY = "#3a3c41"  # QuakeLogic charcoal
ORANGE = "#F26522"
GREY = "#9AA0A6"
LIGHT_GREY = "#D5D8DC"

FIGURE_KINDS = ("hvsr", "spectra", "windows", "azimuthal", "peak_distribution")
FORMATS = ("png", "svg", "pdf")

_THEMES = {
    "light": {"bg": "#FFFFFF", "fg": "#1F2933", "grid": "#E4E7EB", "axes": "#FFFFFF"},
    "dark": {"bg": "#0F172A", "fg": "#E2E8F0", "grid": "#334155", "axes": "#1E293B"},
}

_BRAND_CMAP = LinearSegmentedColormap.from_list("quakelogic", ["#FFFFFF", "#C5C8CD", NAVY, ORANGE])


def _theme(theme: str) -> dict[str, str]:
    return _THEMES.get(theme, _THEMES["light"])


def _style(ax, th: dict[str, str]) -> None:
    ax.set_facecolor(th["axes"])
    ax.tick_params(colors=th["fg"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(th["grid"])
    ax.xaxis.label.set_color(th["fg"])
    ax.yaxis.label.set_color(th["fg"])
    ax.title.set_color(th["fg"])
    ax.grid(True, which="both", color=th["grid"], linewidth=0.5, alpha=0.8)


def _arr(values: Any) -> np.ndarray:
    if values is None:
        return np.array([], dtype=float)
    return np.asarray([np.nan if v is None else v for v in values], dtype=float)


def _selected_curve(result: dict) -> tuple[str, dict]:
    curves = result.get("curves") or {}
    key = curves.get("selected") or "geometric"
    curve = curves.get(key) or {}
    return key, curve


def _save(fig, fmt: str, output_path: str, th: dict[str, str]) -> str:
    fmt = fmt.lower()
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported figure format '{fmt}'. Use one of {FORMATS}.")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    kwargs: dict[str, Any] = {"format": fmt, "facecolor": th["bg"], "bbox_inches": "tight"}
    if fmt == "png":
        kwargs["dpi"] = 200
    fig.savefig(output_path, **kwargs)
    plt.close(fig)
    return output_path


def _peak_label(sel: dict | None) -> str | None:
    if not sel or sel.get("frequency") is None:
        return None
    f0 = float(sel["frequency"])
    a0 = sel.get("amplitude")
    src = sel.get("source", "automatic")
    a_txt = f", A0 = {float(a0):.2f}" if a0 is not None else ""
    return f"Selected peak ({src}): f0 = {f0:.3f} Hz{a_txt}"


def _hvsr_figure(result: dict, th: dict[str, str], window_curves: dict | None = None):
    f = _arr(result.get("frequency"))
    key, curve = _selected_curve(result)
    mean = _arr(curve.get("values"))
    lower = _arr(curve.get("lower"))
    upper = _arr(curve.get("upper"))
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=th["bg"])
    _style(ax, th)

    if window_curves and window_curves.get("curves"):
        wf = _arr(window_curves.get("frequency")) if window_curves.get("frequency") is not None else f
        accepted = window_curves.get("accepted") or [True] * len(window_curves["curves"])
        first = True
        for c, acc in zip(window_curves["curves"], accepted):
            if not acc:
                continue
            ax.plot(wf, _arr(c), color=GREY, linewidth=0.5, alpha=0.35,
                    label="Individual accepted windows" if first else None)
            first = False

    if lower.size and upper.size:
        ax.fill_between(f, lower, upper, color=NAVY, alpha=0.15,
                        label=f"Dispersion band: {curve.get('band', 'n/a')}")
    ax.plot(f, mean, color=NAVY, linewidth=2.0, label=f"{key.capitalize()} mean H/V")

    peaks = result.get("peaks") or {}
    sel = peaks.get("selected")
    lbl = _peak_label(sel)
    if lbl:
        f0 = float(sel["frequency"])
        ax.axvline(f0, color=ORANGE, linewidth=1.2, linestyle="--")
        if sel.get("amplitude") is not None:
            ax.plot([f0], [float(sel["amplitude"])], "o", color=ORANGE, markersize=7, label=lbl)
        else:
            ax.plot([], [], color=ORANGE, label=lbl)
    sr = peaks.get("search_range")
    if sr and len(sr) == 2:
        ax.axvspan(sr[0], sr[1], color=ORANGE, alpha=0.04, label=f"Peak search range {sr[0]}–{sr[1]} Hz")

    invalid = (result.get("masking") or {}).get("invalid_bins") or []
    if invalid and f.size:
        idx = [i for i in invalid if 0 <= i < f.size]
        if idx:
            ax.plot(f[idx], np.full(len(idx), ax.get_ylim()[0] if False else 1.0), "|", color="#B00020",
                    markersize=6, label="Invalid bins (vertical masked)")

    ax.set_xscale("log")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("H/V spectral ratio (–)")
    ax.set_title(f"HVSR — {key} mean of {result.get('windows', {}).get('count_accepted', '?')} accepted windows; "
                 f"band = {curve.get('band', 'n/a')}", fontsize=9)
    ax.legend(fontsize=7, loc="upper right", facecolor=th["axes"], labelcolor=th["fg"], edgecolor=th["grid"])
    ax.set_ylim(bottom=0)
    return fig


def _spectra_figure(result: dict, th: dict[str, str], unit_label: str = "counts", unit_factor: float = 1.0):
    f = _arr(result.get("frequency"))
    comps = result.get("components") or {}
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=th["bg"])
    _style(ax, th)
    colors = {"n": NAVY, "e": "#3F7CAC", "z": ORANGE, "h": GREY}
    labels = {"n": "N (horizontal 1)", "e": "E (horizontal 2)", "z": "Z (vertical)", "h": "H (combined horizontal)"}
    for key in ("n", "e", "z", "h"):
        vals = _arr(comps.get(key))
        if vals.size:
            ax.plot(f, vals * unit_factor, color=colors[key], linewidth=1.4, label=labels[key],
                    linestyle="--" if key == "h" else "-")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Frequency (Hz)")
    unit_txt = f"({unit_label})·s" if any(ch in unit_label for ch in "/ ·") else f"{unit_label}·s"
    ax.set_ylabel(f"Fourier amplitude spectrum ({unit_txt})")
    smoothing = (result.get("params") or {}).get("smoothing") or {}
    ax.set_title(f"Mean smoothed component amplitude spectra over accepted windows "
                 f"({smoothing.get('type', 'n/a')}, b = {smoothing.get('bandwidth', 'n/a')})", fontsize=9)
    ax.legend(fontsize=7, facecolor=th["axes"], labelcolor=th["fg"], edgecolor=th["grid"])
    return fig


def _envelope(t: np.ndarray, v: np.ndarray, max_points: int = 3000):
    n = v.size
    if n <= max_points:
        return t, v
    buckets = max_points // 2
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    tt, vv = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        seg = v[a:b]
        lo, hi = np.nanmin(seg), np.nanmax(seg)
        tt.extend([t[a], t[b - 1]])
        vv.extend([lo, hi])
    return np.asarray(tt), np.asarray(vv)


def _windows_figure(result: dict, th: dict[str, str], recording):
    if recording is None:
        raise ValueError("The 'windows' figure requires the recording (waveforms) to be supplied.")
    fs = float(recording.fs)
    comps = [("n", "N"), ("e", "E"), ("z", "Z")]
    fig, axes = plt.subplots(3, 1, figsize=(9, 6.5), sharex=True, facecolor=th["bg"])
    items = (result.get("windows") or {}).get("items") or []
    for ax, (key, label) in zip(axes, comps):
        _style(ax, th)
        data = np.asarray(getattr(recording, key), dtype=float)
        t = np.arange(data.size) / fs
        te, ve = _envelope(t, data)
        ax.plot(te, ve, color=NAVY, linewidth=0.6)
        ymax = float(np.nanmax(np.abs(data))) if data.size else 1.0
        for w in items:
            color = "#2E7D32" if w.get("accepted") else "#C62828"
            ax.axvspan(w["start_s"], w["end_s"], color=color, alpha=0.12, linewidth=0)
        ax.set_ylabel(f"{label} ({(recording.meta or {}).get('units', 'counts')})", fontsize=8)
        ax.set_ylim(-1.05 * ymax, 1.05 * ymax)
    axes[-1].set_xlabel("Time since record start (s)")
    win = result.get("windows") or {}
    axes[0].set_title(f"Windows: {win.get('count_accepted', '?')} accepted (green), "
                      f"{win.get('count_rejected', '?')} rejected (red); length {win.get('length_s', '?')} s, "
                      f"overlap {win.get('overlap', '?')}", fontsize=9)
    fig.tight_layout()
    return fig


def _azimuthal_figure(result: dict, th: dict[str, str]):
    az = result.get("azimuthal")
    if not az:
        raise ValueError("This result has no azimuthal analysis.")
    f = _arr(az.get("frequency"))
    azimuths = _arr(az.get("azimuths"))
    matrix = np.asarray([[np.nan if v is None else v for v in row] for row in az.get("matrix") or []], dtype=float)
    if matrix.size == 0:
        raise ValueError("Azimuthal matrix is empty.")
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=th["bg"])
    _style(ax, th)
    ax.grid(False)
    mesh = ax.pcolormesh(f, azimuths, matrix, cmap=_BRAND_CMAP, shading="nearest")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("H(θ)/V (–)", color=th["fg"])
    cbar.ax.yaxis.set_tick_params(color=th["fg"], labelcolor=th["fg"])
    pf = _arr(az.get("peak_frequency"))
    if pf.size == azimuths.size:
        ax.plot(pf, azimuths, "o-", color=ORANGE, markersize=3, linewidth=0.8, label="Peak frequency per azimuth")
        ax.legend(fontsize=7, facecolor=th["axes"], labelcolor=th["fg"], edgecolor=th["grid"], loc="upper right")
    ax.set_xscale("log")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Azimuth of horizontal component θ (° clockwise from N)")
    ax.set_title("Azimuthal H/V: H(θ) = N cos θ + E sin θ, divided by V", fontsize=9)
    return fig


def _peak_distribution_figure(result: dict, th: dict[str, str]):
    pv = result.get("peak_variability") or {}
    f0s = _arr(pv.get("window_f0"))
    f0s = f0s[np.isfinite(f0s)]
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=th["bg"])
    _style(ax, th)
    if f0s.size:
        lo, hi = float(f0s.min()), float(f0s.max())
        if lo <= 0:
            lo = min(x for x in f0s if x > 0) if np.any(f0s > 0) else 0.1
        if hi <= lo:
            hi = lo * 1.5
        bins = np.logspace(np.log10(lo / 1.1), np.log10(hi * 1.1), max(8, min(40, int(np.sqrt(f0s.size) * 3))))
        ax.hist(f0s, bins=bins, color=NAVY, alpha=0.75, label=f"Window peak frequencies (n = {f0s.size})")
        ax.set_xscale("log")
    else:
        ax.text(0.5, 0.5, "No window-level peaks in the search range", ha="center", va="center",
                transform=ax.transAxes, color=th["fg"])
    for key, style, label in (("median", "-", "Median"), ("p16", ":", "16th percentile"), ("p84", ":", "84th percentile")):
        v = pv.get(key)
        if v is not None and np.isfinite(v):
            ax.axvline(float(v), color=ORANGE, linestyle=style, linewidth=1.3, label=f"{label} = {float(v):.3f} Hz")
    boot = pv.get("bootstrap")
    if boot and boot.get("f0_p2_5") is not None and boot.get("f0_p97_5") is not None:
        ax.axvspan(float(boot["f0_p2_5"]), float(boot["f0_p97_5"]), color="#3F7CAC", alpha=0.15,
                   label=f"Bootstrap 2.5–97.5 % percentile interval (n = {boot.get('n_resamples')}, seed {boot.get('seed')})")
    sel = (result.get("peaks") or {}).get("selected")
    if sel and sel.get("frequency") is not None:
        ax.axvline(float(sel["frequency"]), color=NAVY, linestyle="--", linewidth=1.0,
                   label=f"Selected peak f0 = {float(sel['frequency']):.3f} Hz")
    ax.set_xlabel("Peak frequency (Hz)")
    ax.set_ylabel("Number of windows")
    ax.set_title(pv.get("definition") or "Distribution of window-level peak frequencies", fontsize=8)
    ax.legend(fontsize=7, facecolor=th["axes"], labelcolor=th["fg"], edgecolor=th["grid"])
    return fig


def figure(result: dict, figure: str, fmt: str, output_path: str, recording=None,
           theme: str = "light", window_curves: dict | None = None,
           unit_system: str | None = None, units: str | None = None, unit_kind: str | None = None) -> str:
    """Render one figure of ``result`` to ``output_path`` and return the path.

    figure: hvsr | spectra | windows | azimuthal | peak_distribution
    fmt:    png | svg | pdf
    """
    th = _theme(theme)
    if figure == "hvsr":
        fig = _hvsr_figure(result, th, window_curves)
    elif figure == "spectra":
        from .pdf import display_amplitude_unit
        src_units = units or (result.get("input") or {}).get("units") or (recording.meta.get("units") if recording is not None and getattr(recording, "meta", None) else None)
        src_kind = unit_kind or (result.get("input") or {}).get("unit_kind") or (recording.meta.get("unit_kind") if recording is not None and getattr(recording, "meta", None) else None)
        label, factor = display_amplitude_unit(src_units, src_kind, unit_system)
        fig = _spectra_figure(result, th, label, factor)
    elif figure == "windows":
        fig = _windows_figure(result, th, recording)
    elif figure == "azimuthal":
        fig = _azimuthal_figure(result, th)
    elif figure == "peak_distribution":
        fig = _peak_distribution_figure(result, th)
    else:
        raise ValueError(f"Unknown figure '{figure}'. Use one of {FIGURE_KINDS}.")
    return _save(fig, fmt, output_path, th)
