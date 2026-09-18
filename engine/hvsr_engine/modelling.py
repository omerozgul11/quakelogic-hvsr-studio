"""Forward modelling of the HVSR curve from a 1-D layered ground model.

Method (Herak, 2008, *ModelHVSR*): the H/V curve of a horizontally layered half-space excited by
vertically incident body waves is approximated by the ratio of the SH-wave and P-wave
transfer functions of the layer stack,

    HVSR_model(f) = |T_SH(f)| / |T_P(f)|,

where each transfer function is the surface-to-outcrop amplification computed with the
Thomson–Haskell propagator for vertical incidence and complex (anelastic) velocities
v* = v (1 + i / (2Q)).  For a single layer of thickness H and shear velocity Vs over a
half-space the SH transfer function peaks at f ≈ Vs / (4H).

The model is a forward model only: a layered profile whose synthetic curve resembles a
measured H/V curve is **not unique** — many profiles produce the same curve, and the
absolute H/V level is not site amplification. The module also reports Vs30 and VsEq
(Italian NTC-style "equivalent" shear-wave velocity down to the bedrock when it is
shallower than 30 m) and completes Poisson's ratio ν from Vp/Vs or Vp from ν.

Reference: Herak, M. (2008). ModelHVSR — a Matlab tool to model horizontal-to-vertical spectral
ratio of ambient noise. Computers & Geosciences, 34(11), 1514–1526.
"""
from __future__ import annotations

import numpy as np

from .smoothing import log_frequency_axis

METHOD = ("Herak (2008) body-wave transfer-function ratio |T_SH|/|T_P| (Thomson–Haskell, vertical "
          "incidence, complex velocities v(1 + i/(2Q)))")
NOTES = [
    "A forward model that fits the measured curve is not unique: many layered profiles produce the same "
    "H/V curve. The model supports interpretation; it does not determine the velocity profile.",
    "The synthetic curve is the ratio of body-wave transfer functions (SH over P) for vertical incidence; "
    "the measured H/V of ambient vibrations also contains surface-wave contributions, so amplitudes and "
    "secondary peaks may differ.",
    "Vs30 and VsEq are computed from the entered profile only.",
]

DEFAULT_QS = 30.0
DEFAULT_QP = 60.0
DEFAULT_DENSITY = 1900.0


def poisson_from_vp_vs(vp: float, vs: float) -> float:
    r2 = (vp / vs) ** 2
    return (r2 - 2.0) / (2.0 * (r2 - 1.0))


def vp_from_poisson(vs: float, nu: float) -> float:
    return vs * np.sqrt((2.0 - 2.0 * nu) / (1.0 - 2.0 * nu))


def normalise_layers(layers: list[dict]) -> list[dict]:
    if not layers or len(layers) < 1:
        raise ValueError("At least one layer (the half-space) is required.")
    out = []
    depth = 0.0
    for i, raw in enumerate(layers):
        last = i == len(layers) - 1
        thickness = raw.get("thickness_m")
        thickness = None if thickness in (None, "", 0, 0.0) and last else thickness
        if last and thickness is not None:
            # a finite last layer would be a stack without half-space; treat it as the half-space
            thickness = None
        if not last and (thickness is None or float(thickness) <= 0):
            raise ValueError(f"Layer {i + 1}: thickness must be positive (only the last layer, the half-space, has none).")
        vs = raw.get("vs")
        if vs is None or float(vs) <= 0:
            raise ValueError(f"Layer {i + 1}: Vs must be positive.")
        vs = float(vs)
        vp = raw.get("vp")
        nu = raw.get("poisson")
        if vp not in (None, "") and float(vp) > 0:
            vp = float(vp)
            if vp <= vs * np.sqrt(4.0 / 3.0) * 1.0000001 and vp <= vs:
                raise ValueError(f"Layer {i + 1}: Vp must exceed Vs.")
            nu = poisson_from_vp_vs(vp, vs)
            if not (0.0 <= nu < 0.5):
                raise ValueError(f"Layer {i + 1}: Vp/Vs = {vp / vs:.3f} gives Poisson's ratio {nu:.3f} outside [0, 0.5).")
        elif nu not in (None, ""):
            nu = float(nu)
            if not (0.0 <= nu < 0.5):
                raise ValueError(f"Layer {i + 1}: Poisson's ratio must be in [0, 0.5).")
            vp = float(vp_from_poisson(vs, nu))
        else:
            nu = 0.33
            vp = float(vp_from_poisson(vs, nu))
        density = float(raw.get("density") or DEFAULT_DENSITY)
        if density <= 0:
            raise ValueError(f"Layer {i + 1}: density must be positive.")
        qs = float(raw.get("qs") or DEFAULT_QS)
        qp = float(raw.get("qp") or DEFAULT_QP)
        if qs <= 0 or qp <= 0:
            raise ValueError(f"Layer {i + 1}: Q values must be positive.")
        top = depth
        bottom = None if thickness is None else depth + float(thickness)
        out.append({"thickness_m": None if thickness is None else float(thickness), "vs": vs, "vp": vp,
                    "poisson": float(nu), "density": density, "qs": qs, "qp": qp,
                    "depth_top_m": top, "depth_bottom_m": bottom, "half_space": thickness is None})
        if bottom is not None:
            depth = bottom
    return out


def transfer_function(freq: np.ndarray, thickness: np.ndarray, velocity: np.ndarray, density: np.ndarray,
                      q: np.ndarray) -> np.ndarray:
    """Complex surface/outcrop transfer function of a layer stack for vertically incident waves.

    ``thickness`` has one entry per layer above the half-space; ``velocity``/``density``/``q`` have
    one more entry (the half-space). Returns |T| is 1 for a bare half-space."""
    freq = np.asarray(freq, dtype=np.float64)
    omega = 2.0 * np.pi * freq
    vc = velocity * (1.0 + 1j / (2.0 * q))
    n_layers = len(thickness)
    a = np.ones_like(omega, dtype=np.complex128)
    b = np.ones_like(omega, dtype=np.complex128)
    for j in range(n_layers):
        alpha = (density[j] * vc[j]) / (density[j + 1] * vc[j + 1])
        k = omega / vc[j]
        e_plus = np.exp(1j * k * thickness[j])
        e_minus = np.exp(-1j * k * thickness[j])
        a_next = 0.5 * a * (1.0 + alpha) * e_plus + 0.5 * b * (1.0 - alpha) * e_minus
        b_next = 0.5 * a * (1.0 - alpha) * e_plus + 0.5 * b * (1.0 + alpha) * e_minus
        a, b = a_next, b_next
    with np.errstate(divide="ignore", invalid="ignore"):
        t = 1.0 / a  # (A_1 + B_1) / (2 A_N) with A_1 = B_1 = 1
    return t


def vs30(layers: list[dict], offset_m: float = 0.0) -> float:
    return equivalent_velocity(layers, offset_m, 30.0)


def equivalent_velocity(layers: list[dict], offset_m: float, depth_m: float) -> float:
    """Time-averaged Vs over ``depth_m`` metres below ``offset_m``: H / Σ(h_i / Vs_i)."""
    remaining = float(depth_m)
    tt = 0.0
    z = 0.0
    for lay in layers:
        h = lay["thickness_m"]
        seg_top = z
        seg_bottom = np.inf if h is None else z + h
        lo = max(seg_top, offset_m)
        hi = min(seg_bottom, offset_m + depth_m)
        if hi > lo:
            tt += (hi - lo) / lay["vs"]
            remaining -= (hi - lo)
        if h is None:
            break
        z = seg_bottom
    used = depth_m - max(0.0, remaining)
    return float(used / tt) if tt > 0 else float("nan")


def model_hvsr(layers: list[dict], freq_min: float = 0.2, freq_max: float = 100.0, n_freq: int = 200,
               vs30_offset_m: float = 0.0) -> dict:
    lays = normalise_layers(layers)
    if freq_min <= 0 or freq_max <= freq_min:
        raise ValueError("Frequency range must satisfy 0 < freq_min < freq_max.")
    freq = log_frequency_axis(float(freq_min), float(freq_max), int(n_freq))
    thick = np.array([l["thickness_m"] for l in lays[:-1]], dtype=np.float64)
    rho = np.array([l["density"] for l in lays])
    t_sh = transfer_function(freq, thick, np.array([l["vs"] for l in lays]), rho, np.array([l["qs"] for l in lays]))
    t_p = transfer_function(freq, thick, np.array([l["vp"] for l in lays]), rho, np.array([l["qp"] for l in lays]))
    with np.errstate(divide="ignore", invalid="ignore"):
        hv = np.abs(t_sh) / np.abs(t_p)
    offset = float(vs30_offset_m or 0.0)
    v30 = vs30(lays, offset)
    bedrock_depth = (lays[-1]["depth_top_m"] - offset) if len(lays) > 1 else 0.0
    if 0.0 < bedrock_depth < 30.0:
        vseq = {"value": equivalent_velocity(lays, offset, bedrock_depth), "depth_m": bedrock_depth,
                "definition": f"VsEq = H / Σ(h_i/Vs_i) down to the bedrock (top of the half-space) at {bedrock_depth:g} m "
                              f"below the offset, because it is shallower than 30 m."}
    else:
        vseq = {"value": v30, "depth_m": 30.0,
                "definition": "Bedrock is at or below 30 m (or there is no layer above it): VsEq = Vs30."}
    finite = np.isfinite(hv)
    f0_model = float(freq[np.nanargmax(np.where(finite, hv, -np.inf))]) if finite.any() else None
    a0_model = float(np.nanmax(hv[finite])) if finite.any() else None
    return {
        "frequency": freq.tolist(), "hvsr": _clean(hv), "t_sh": _clean(np.abs(t_sh)), "t_p": _clean(np.abs(t_p)),
        "layers": lays, "vs30": v30, "vs30_offset_m": offset, "vseq": vseq,
        "f0_model": f0_model, "a0_model": a0_model,
        "method": METHOD, "notes": NOTES,
        "reference": "Herak, M. (2008). ModelHVSR — a Matlab tool to model horizontal-to-vertical spectral ratio of "
                     "ambient noise. Computers & Geosciences 34(11), 1514–1526.",
    }


def _clean(arr: np.ndarray) -> list:
    return [float(v) if np.isfinite(v) else None for v in np.asarray(arr, dtype=np.float64)]
