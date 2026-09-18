import numpy as np

from hvsr_engine.synthetic import synthetic_recording
from hvsr_engine.windows import make_windows, screen_windows, sta_lta_ratio


def test_window_counts_with_overlap():
    assert len(make_windows(6000, 100, 60, 0.0)) == 1
    assert len(make_windows(12000, 100, 60, 0.0)) == 2
    assert len(make_windows(12000, 100, 60, 0.5)) == 3
    w = make_windows(12000, 100, 60, 0.5)
    assert w[1][0] == 3000 and all(e - s == 6000 for s, e in w)
    assert make_windows(100, 100, 60, 0.5) == []


def test_sta_lta_of_stationary_noise_is_near_one():
    x = np.random.default_rng(1).normal(size=60000)
    r, nlta = sta_lta_ratio(x, 100, 2, 30)
    assert nlta == 3000 and np.isnan(r[:nlta - 1]).all()
    assert 0.7 < np.nanmin(r) and np.nanmax(r) < 1.5


def test_transient_window_is_rejected_and_override_wins():
    rec = synthetic_recording(fs=100, duration_s=600, f0=2.5, amplification=5, seed=7,
                              transients=[{"time_s": 300, "amplitude": 30, "duration_s": 2}])
    res = screen_windows(rec, {"window_length_s": 60, "overlap": 0.5})
    items = res["windows"]
    hit = [it for it in items if it["start_s"] <= 300 < it["end_s"]]
    assert hit and all(not it["accepted"] and it["reason"] == "sta_lta" for it in hit)
    assert res["counts"]["rejected"] >= len(hit)
    forced = screen_windows(rec, {"window_length_s": 60, "overlap": 0.5}, {str(hit[0]["index"]): {"accepted": True}})
    assert forced["windows"][hit[0]["index"]]["accepted"] and forced["windows"][hit[0]["index"]]["reason"] == "manual"


def test_amplitude_criterion_and_nan_windows():
    rec = synthetic_recording(fs=100, duration_s=300, seed=8)
    rec.z[20000] = np.nan
    res = screen_windows(rec, {"window_length_s": 60, "overlap": 0.0,
                               "screening": {"amplitude": {"enabled": True, "max_ratio_to_rms": 3.0}}})
    nan_items = [it for it in res["windows"] if it["has_nan"]]
    assert nan_items and all(it["reason"] == "nan" and not it["accepted"] for it in nan_items)
    # forcing a NaN window to accepted is refused
    forced = screen_windows(rec, {"window_length_s": 60, "overlap": 0.0}, {nan_items[0]["index"]: {"accepted": True}})
    assert not forced["windows"][nan_items[0]["index"]]["accepted"]
    assert all(it["amp_ratio"] is not None for it in res["windows"])
