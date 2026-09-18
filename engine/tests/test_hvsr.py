import json
import threading
from pathlib import Path

import numpy as np
import pytest

from hvsr_engine.errors import CancelledError
from hvsr_engine.hvsr import analyze, load_result, select_peak, window_curves, write_result
from hvsr_engine.io.canonical import Recording
from hvsr_engine.synthetic import expected_hvsr, synthetic_recording

FAST = {"bootstrap": {"enabled": False}, "n_freq": 120}


def _white_rec(n=60000, fs=100.0, seed=0, scale_n=2.0, scale_e=2.0):
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    return Recording(scale_n * z, scale_e * z, z, fs, meta={"station": "W"})


def _band(d, lo=0.5, hi=20):
    f = np.array(d["frequency"])
    return f, (f >= lo) & (f <= hi)


def test_constant_ratio_geometric_rms_and_directional():
    rec = _white_rec(scale_n=2.0, scale_e=2.0)
    d = analyze(rec, {**FAST, "screening": {"enabled": False}}).to_dict()
    f, sel = _band(d)
    for m in ("geometric", "arithmetic", "median"):
        np.testing.assert_allclose(np.array(d["curves"][m]["values"], dtype=float)[sel], 2.0, rtol=1e-9)
    rec2 = _white_rec(scale_n=3.0, scale_e=1.0)
    d_gm = analyze(rec2, {**FAST, "screening": {"enabled": False}, "horizontal_method": "geometric_mean"}).to_dict()
    np.testing.assert_allclose(np.array(d_gm["curves"]["geometric"]["values"], dtype=float)[sel], np.sqrt(3.0), rtol=1e-9)
    d_rms = analyze(rec2, {**FAST, "screening": {"enabled": False}, "horizontal_method": "rms"}).to_dict()
    np.testing.assert_allclose(np.array(d_rms["curves"]["geometric"]["values"], dtype=float)[sel], np.sqrt(5.0), rtol=1e-9)
    d_dir = analyze(rec2, {**FAST, "screening": {"enabled": False}, "horizontal_method": "directional"}).to_dict()
    np.testing.assert_allclose(np.array(d_dir["directional"]["n_over_z"]["values"], dtype=float)[sel], 3.0, rtol=1e-9)
    np.testing.assert_allclose(np.array(d_dir["directional"]["e_over_z"]["values"], dtype=float)[sel], 1.0, rtol=1e-9)
    assert d_gm["peaks"]["status"] == "none"  # a flat curve has no peak


def test_synthetic_frequency_dependent_ratio_matches_analytic(syn_rec):
    d = analyze(syn_rec, {"n_freq": 200, "random_seed": 1}, random_seed=1).to_dict()
    f = np.array(d["frequency"])
    v = np.array(d["curves"]["geometric"]["values"], dtype=float)
    damping = syn_rec.meta["synthetic_model"]["damping"]
    exp = expected_hvsr(f, 2.5, damping)
    sel = (f >= 0.5) & (f <= 20)
    rel = np.abs(v[sel] / exp[sel] - 1)
    assert np.nanmedian(rel) < 0.05
    assert np.nanmax(rel) < 0.2  # the smoothed peak is slightly lower than the analytic resonance
    assert d["peaks"]["status"] == "clear"
    assert abs(d["peaks"]["selected"]["frequency"] - 2.5) < 0.15
    assert 4.0 < d["peaks"]["selected"]["amplitude"] < 5.5
    assert d["sesame"]["reliability_passed"] and d["sesame"]["clarity_passed"]
    assert d["input"]["is_synthetic"] is True
    assert d["random_seed"] == 1 and d["peak_variability"]["bootstrap"]["seed"] == 1
    assert any("NOT a direct measurement of site amplification" in n for n in d["interpretation_notes"])


def test_combination_before_smoothing_is_close_but_distinct(syn_rec):
    a = analyze(syn_rec, {**FAST, "combination_stage": "after_smoothing"}).to_dict()
    b = analyze(syn_rec, {**FAST, "combination_stage": "before_smoothing"}).to_dict()
    va = np.array(a["curves"]["geometric"]["values"], dtype=float)
    vb = np.array(b["curves"]["geometric"]["values"], dtype=float)
    assert np.nanmax(np.abs(va / vb - 1)) < 0.1
    assert not np.allclose(va, vb)
    assert b["method"]["combination_stage"] == "before_smoothing"


def test_near_zero_vertical_is_masked_not_clipped():
    rec = _white_rec(n=60000)
    # kill the vertical energy in a band by notch-like frequency-domain zeroing
    spec = np.fft.rfft(rec.z)
    f = np.fft.rfftfreq(len(rec.z), 0.01)
    spec[(f > 3.0) & (f < 8.0)] = 0
    rec.z = np.fft.irfft(spec, n=len(rec.z))
    d = analyze(rec, {**FAST, "screening": {"enabled": False}, "vertical_floor": {"relative": 1e-2, "absolute": 1e-12}}).to_dict()
    fr = np.array(d["frequency"])
    vals = d["curves"]["geometric"]["values"]
    inband = [v for fq, v in zip(fr, vals) if 4.5 < fq < 5.5]
    assert all(v is None for v in inband)                # masked → null, not a huge number
    assert d["masking"]["bins_masked_any_window"] > 0
    assert len(d["masking"]["invalid_bins"]) > 0
    assert {fl["code"] for fl in d["quality_flags"]} >= {"vertical_masked_bins", "invalid_bins"}
    finite = [v for v in vals if v is not None]
    assert max(finite) < 100


def test_insufficient_data_short_record():
    rec = synthetic_recording(duration_s=100, seed=9)
    d = analyze(rec, {**FAST, "window_length_s": 60, "overlap": 0.0}).to_dict()
    assert d["windows"]["count_total"] == 1
    assert d["peaks"]["status"] == "insufficient_data" and d["peaks"]["selected"] is None
    assert {fl["code"] for fl in d["quality_flags"]} >= {"insufficient_windows", "short_record"}
    with pytest.raises(ValueError):
        analyze(rec, {**FAST, "window_length_s": 200})


def test_window_overrides_and_manual_peak(syn_rec):
    d = analyze(syn_rec, {**FAST}, window_overrides={"0": {"accepted": False}, 1: {"accepted": False}},
                manual_peak={"frequency": 4.0}).to_dict()
    items = d["windows"]["items"]
    assert not items[0]["accepted"] and items[0]["reason"] == "manual" and not items[1]["accepted"]
    assert d["windows"]["count_accepted"] == d["windows"]["count_total"] - 2
    assert d["peaks"]["selected"]["source"] == "manual"
    assert abs(d["peaks"]["selected"]["frequency"] - 4.0) < 0.1
    assert d["sesame"]["f0"] == d["peaks"]["selected"]["frequency"]


def test_multiple_peaks_status():
    # two resonances of similar amplitude
    rec = synthetic_recording(fs=100, duration_s=600, f0=1.5, amplification=4, seed=11)
    rec2 = synthetic_recording(fs=100, duration_s=600, f0=6.0, amplification=4, seed=12)
    rec.n = rec.n + rec2.n
    rec.e = rec.e + rec2.e
    d = analyze(rec, {**FAST, "screening": {"enabled": False}}).to_dict()
    assert d["peaks"]["status"] == "multiple"
    assert len([c for c in d["peaks"]["candidates"] if c["amplitude"] >= 2]) >= 2


def test_write_load_roundtrip_and_reproducibility(tmp_path, short_rec):
    params = {"n_freq": 100, "bootstrap": {"n_resamples": 50}, "azimuthal": {"enabled": True, "step_deg": 30}}
    r1 = analyze(short_rec, params, random_seed=123)
    r2 = analyze(short_rec, params, random_seed=123)
    d1, d2 = r1.to_dict(), r2.to_dict()
    for d in (d1, d2):
        d.pop("computed_at")
        d.pop("elapsed_s")
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
    out = tmp_path / "an"
    write_result(r1, out)
    loaded = load_result(out)
    assert loaded["peaks"]["selected"]["frequency"] == d1["peaks"]["selected"]["frequency"]
    assert loaded["azimuthal"]["matrix"] and len(loaded["azimuthal"]["azimuths"]) == 6
    wc = window_curves(out)
    assert len(wc["curves"]) == d1["windows"]["count_total"] and len(wc["frequency"]) == 100
    for name in ("hvsr_mean.csv", "hvsr_windows.csv", "component_spectra.csv", "summary.csv", "summary.json", "config.json", "azimuthal.csv"):
        assert (out / "exports" / name).exists(), name
    cfg = json.loads((out / "exports" / "config.json").read_text())
    assert cfg["random_seed"] == 123 and cfg["params"]["n_freq"] == 100
    # re-running from the stored config reproduces the result exactly
    r3 = analyze(short_rec, cfg["params"], random_seed=cfg["random_seed"]).to_dict()
    r3.pop("computed_at"); r3.pop("elapsed_s")
    assert json.dumps(r3, sort_keys=True) == json.dumps(d1, sort_keys=True)
    # strict JSON (no NaN tokens)
    text = (out / "result.json").read_text()
    assert "NaN" not in text and "Infinity" not in text


def test_select_peak_manual_then_automatic(tmp_path, short_rec):
    out = tmp_path / "an"
    write_result(analyze(short_rec, FAST, random_seed=5), out)
    auto_f0 = load_result(out)["peaks"]["selected"]["frequency"]
    d = select_peak(out, 6.0)
    assert d["peaks"]["selected"]["source"] == "manual" and abs(d["peaks"]["selected"]["frequency"] - 6.0) < 0.2
    assert d["sesame"]["f0"] == d["peaks"]["selected"]["frequency"]
    assert json.loads((out / "exports" / "summary.json").read_text())["peak_source"] == "manual"
    d2 = select_peak(out, None)
    assert d2["peaks"]["selected"]["source"] == "automatic" and d2["peaks"]["selected"]["frequency"] == auto_f0


def test_cancellation(syn_rec):
    ev = threading.Event()
    ev.set()
    with pytest.raises(CancelledError):
        analyze(syn_rec, FAST, cancel=ev)


def test_progress_callback_and_random_seed_recorded(short_rec):
    calls = []
    d = analyze(short_rec, FAST, progress=lambda fr, msg=None: calls.append((fr, msg))).to_dict()
    assert calls and calls[-1][0] == 1.0 and calls[0][0] <= calls[-1][0]
    assert isinstance(d["random_seed"], int)


def test_azimuthal_peak_follows_stronger_component():
    rec = synthetic_recording(fs=100, duration_s=600, f0=2.0, amplification=5, seed=21, horizontal_ratio_ne=2.0)
    d = analyze(rec, {**FAST, "azimuthal": {"enabled": True, "step_deg": 15}, "screening": {"enabled": False}}).to_dict()
    az = d["azimuthal"]
    amps = np.array(az["peak_amplitude"], dtype=float)
    assert len(az["azimuths"]) == 12 and az["azimuths"][0] == 0.0
    assert amps[0] > amps[6]  # 0° (north) stronger than 90° (east)
    assert len(az["matrix"]) == 12 and len(az["matrix"][0]) == len(az["frequency"])
