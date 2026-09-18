import numpy as np
import pytest

from hvsr_engine.errors import ProcessingError
from hvsr_engine.io.canonical import Recording
from hvsr_engine.preprocessing import apply_steps, filter_response, rotate_horizontals
from hvsr_engine.synthetic import synthetic_recording


def _sine_rec(fs=100.0, n=20000, freqs=(1.0, 10.0)):
    t = np.arange(n) / fs
    x = sum(np.sin(2 * np.pi * f * t) for f in freqs)
    return Recording(x.copy(), x.copy(), x.copy(), fs, meta={"station": "T"})


def test_butterworth_minus_3db_at_cutoff_and_zero_phase_doubles():
    r = filter_response(100, {"op": "filter", "params": {"kind": "lowpass", "freq_high": 10, "order": 4, "zero_phase": False}})
    f, m = np.array(r["frequency"]), np.array(r["magnitude_db"])
    assert abs(np.interp(10, f, m) + 3.01) < 0.05
    r2 = filter_response(100, {"op": "filter", "params": {"kind": "lowpass", "freq_high": 10, "order": 4, "zero_phase": True}})
    assert abs(np.interp(10, f, np.array(r2["magnitude_db"])) + 6.02) < 0.1
    assert all(p == 0 for p in r2["phase_deg"])


def test_bandpass_attenuates_out_of_band_and_zero_phase_has_no_shift():
    rec = _sine_rec()
    out, warnings, applied = apply_steps(rec, [{"op": "filter", "params": {"kind": "lowpass", "freq_high": 4, "order": 4, "zero_phase": True}}])
    t = np.arange(rec.n_samples) / rec.fs
    ref = np.sin(2 * np.pi * 1.0 * t)
    mid = slice(2000, 18000)
    assert np.max(np.abs(out.n[mid] - ref[mid])) < 0.03  # 10 Hz removed, 1 Hz kept without phase shift
    assert applied[0]["effective"]["design"].startswith("Butterworth")
    causal, _, _ = apply_steps(rec, [{"op": "filter", "params": {"kind": "lowpass", "freq_high": 4, "order": 4, "zero_phase": False}}])
    assert np.max(np.abs(causal.n[mid] - ref[mid])) > 0.1  # causal filter shifts the phase


def test_invalid_filter_designs_raise():
    rec = _sine_rec()
    with pytest.raises(ProcessingError) as e:
        apply_steps(rec, [{"op": "filter", "params": {"kind": "lowpass", "freq_high": 60}}])
    assert e.value.code == "cutoff_above_nyquist"
    with pytest.raises(ProcessingError) as e:
        apply_steps(rec, [{"op": "filter", "params": {"kind": "bandpass", "freq_low": 10, "freq_high": 2}}])
    assert e.value.code == "band_inverted"
    with pytest.raises(ProcessingError):
        apply_steps(rec, [{"op": "filter", "params": {"kind": "highpass", "freq_low": 0}}])


def test_notch_removes_line_frequency():
    fs, n = 200.0, 40000
    t = np.arange(n) / fs
    x = np.sin(2 * np.pi * 3 * t) + 0.5 * np.sin(2 * np.pi * 50 * t)
    rec = Recording(x, x.copy(), x.copy(), fs)
    out, _, applied = apply_steps(rec, [{"op": "notch", "params": {"frequency": 50, "quality": 30, "harmonics": 3}}])
    spec = np.abs(np.fft.rfft(out.z))
    f = np.fft.rfftfreq(n, 1 / fs)
    assert spec[np.argmin(np.abs(f - 50))] < 0.01 * spec[np.argmin(np.abs(f - 3))]
    assert applied[0]["effective"]["sections"] == 1  # 100 Hz harmonic is at Nyquist → skipped


def test_rotation_pure_north_becomes_east_and_round_trip():
    n = np.sin(np.linspace(0, 10, 500))
    e = np.zeros_like(n)
    rn, re_ = rotate_horizontals(n, e, 90.0)
    np.testing.assert_allclose(rn, 0.0, atol=1e-12)
    np.testing.assert_allclose(re_, n, atol=1e-12)
    # 30° then −30° restores the input
    a, b = rotate_horizontals(n, e + 0.3, 30.0)
    c, d = rotate_horizontals(a, b, -30.0)
    np.testing.assert_allclose(c, n, atol=1e-12)
    np.testing.assert_allclose(d, e + 0.3, atol=1e-12)
    # energy is preserved
    assert np.isclose(np.sum(a ** 2 + b ** 2), np.sum(n ** 2 + (e + 0.3) ** 2))


def test_rotate_step_updates_orientation_meta():
    rec = synthetic_recording(duration_s=60, seed=2)
    rec.meta["orientation_deg"] = 15.0
    out, _, _ = apply_steps(rec, [{"op": "rotate", "params": {"azimuth_deg": 15.0}}])
    assert out.meta["orientation_deg"] == 0.0


@pytest.mark.parametrize("method,target", [("decimate", 50.0), ("decimate", 20.0), ("polyphase", 40.0)])
def test_resampling_keeps_sinusoid_aligned(method, target):
    fs, n = 200.0, 40000
    t = np.arange(n) / fs
    x = np.sin(2 * np.pi * 1.0 * t)
    rec = Recording(x, x.copy(), x.copy(), fs)
    out, warnings, applied = apply_steps(rec, [{"op": "resample", "params": {"target_rate": target, "method": method}}])
    assert out.fs == target
    t2 = np.arange(out.n_samples) / out.fs
    mid = slice(int(0.1 * out.n_samples), int(0.9 * out.n_samples))
    np.testing.assert_allclose(out.z[mid], np.sin(2 * np.pi * 1.0 * t2[mid]), atol=2e-3)
    assert abs(out.n_samples - n * target / fs) <= 1
    assert not any(w["code"] == "resample_upsampling" for w in warnings)


def test_resampling_removes_aliasing_content_and_flags_non_integer():
    fs, n = 200.0, 40000
    t = np.arange(n) / fs
    x = np.sin(2 * np.pi * 1.0 * t) + np.sin(2 * np.pi * 45.0 * t)
    rec = Recording(x, x.copy(), x.copy(), fs)
    out, _, _ = apply_steps(rec, [{"op": "resample", "params": {"target_rate": 50.0}}])
    t2 = np.arange(out.n_samples) / out.fs
    mid = slice(1000, 9000)
    assert np.max(np.abs(out.z[mid] - np.sin(2 * np.pi * 1.0 * t2[mid]))) < 0.02  # 45 Hz removed, not aliased
    with pytest.raises(ProcessingError) as e:
        apply_steps(rec, [{"op": "resample", "params": {"target_rate": 60.0}}])
    assert e.value.code == "resample_not_integer"
    _, warnings, _ = apply_steps(rec, [{"op": "resample", "params": {"target_rate": 400.0, "method": "polyphase"}}])
    assert any(w["code"] == "resample_upsampling" for w in warnings)


def test_demean_detrend_polynomial_taper_crop():
    rec = synthetic_recording(duration_s=120, seed=4)
    t = rec.times()
    rec.z = rec.z + 50 + 0.1 * t + 0.001 * t ** 2
    out, warnings, applied = apply_steps(rec, [{"op": "demean"}, {"op": "polynomial", "params": {"order": 2}},
                                               {"op": "taper", "params": {"percent": 5}},
                                               {"op": "crop", "params": {"start_s": 10, "end_s": 50}}])
    assert abs(np.mean(out.z)) < 1.0
    assert out.n_samples == 4000 and out.start_time.startswith("2025-01-01T00:00:10")
    assert [a["op"] for a in applied] == ["demean", "polynomial", "taper", "crop"]
    assert out.meta["steps"][1]["effective"]["order"] == 2
    # original untouched
    assert rec.n_samples == 12000


def test_disabled_steps_are_skipped_and_nan_refused():
    rec = synthetic_recording(duration_s=60, seed=4)
    out, _, applied = apply_steps(rec, [{"op": "demean", "enabled": False}, {"op": "detrend"}])
    assert [a["op"] for a in applied] == ["detrend"]
    rec.n[5] = np.nan
    with pytest.raises(ProcessingError) as e:
        apply_steps(rec, [{"op": "demean"}])
    assert e.value.code == "nan_values"


def test_excessive_processing_warning():
    rec = synthetic_recording(duration_s=120, seed=4)
    steps = [{"op": "filter", "params": {"kind": "highpass", "freq_low": 0.5}}] * 3
    _, warnings, _ = apply_steps(rec, steps)
    assert any(w["code"] == "excessive_processing" for w in warnings)


def test_remove_response_with_paz_scales_amplitude():
    fs, n = 100.0, 20000
    t = np.arange(n) / fs
    x = np.sin(2 * np.pi * 1.0 * t)
    rec = Recording(x, x.copy(), x.copy(), fs, meta={"channels": {"n": "HHN", "e": "HHE", "z": "HHZ"}})
    # flat velocity response with sensitivity 1000 counts/(m/s)
    paz = {"poles": [], "zeros": [], "gain": 1.0, "sensitivity": 1000.0, "units": "VEL"}
    out, _, applied = apply_steps(rec, [{"op": "remove_response", "params": {"source": "paz", "paz": paz, "output": "VEL",
                                                                              "water_level": 60, "pre_filt": [0.05, 0.1, 40, 45]}}])
    mid = slice(2000, 18000)
    np.testing.assert_allclose(out.z[mid], x[mid] / 1000.0, atol=2e-5)
    assert out.meta["units"] == "m/s" and out.meta["unit_kind"] == "velocity"
    with pytest.raises(ProcessingError):
        apply_steps(rec, [{"op": "remove_response", "params": {"source": "stationxml", "path": None}}])
