"""Compact summary of a result.json for storage in the application database."""

from __future__ import annotations


def summarize(result: dict) -> dict:
    pv = dict(result.get("peak_variability") or {})
    pv.pop("window_f0", None)
    pv.pop("window_a0", None)
    windows = result.get("windows") or {}
    masking = result.get("masking") or {}
    sesame = result.get("sesame")
    sesame_small = None
    if sesame:
        sesame_small = {
            "f0": sesame.get("f0"), "a0": sesame.get("a0"),
            "reliability_passed": sesame.get("reliability_passed"),
            "clarity_passed_count": sesame.get("clarity_passed_count"),
            "clarity_passed": sesame.get("clarity_passed"),
            "reliability": [{k: c.get(k) for k in ("id", "passed", "value", "threshold")} for c in sesame.get("reliability") or []],
            "clarity": [{k: c.get(k) for k in ("id", "passed", "value", "threshold")} for c in sesame.get("clarity") or []],
            "reference": sesame.get("reference"),
        }
    return {
        "engine_version": result.get("engine_version"),
        "computed_at": result.get("computed_at"),
        "elapsed_s": result.get("elapsed_s"),
        "random_seed": result.get("random_seed"),
        "input": result.get("input"),
        "windows": {k: windows.get(k) for k in ("length_s", "overlap", "count_total", "count_accepted", "count_rejected")},
        "curves_selected": (result.get("curves") or {}).get("selected"),
        "peaks": result.get("peaks"),
        "peak_variability": pv,
        "sesame": sesame_small,
        "masking": {"policy": masking.get("policy"), "bins_masked_any_window": masking.get("bins_masked_any_window"),
                    "invalid_bin_count": len(masking.get("invalid_bins") or [])},
        "quality_flags": result.get("quality_flags") or [],
        "azimuthal_enabled": bool(result.get("azimuthal")),
        "interpretation_notes": result.get("interpretation_notes") or [],
    }
