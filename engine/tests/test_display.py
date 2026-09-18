import numpy as np

from hvsr_engine.display import downsample_minmax, recording_display
from hvsr_engine.synthetic import synthetic_recording


def test_minmax_preserves_extremes_and_order():
    t = np.arange(100000) / 100.0
    v = np.random.default_rng(0).normal(size=100000)
    v[54321] = 50.0
    v[12345] = -40.0
    td, vd = downsample_minmax(t, v, 2000)
    assert len(vd) <= 2000 and vd.max() == 50.0 and vd.min() == -40.0
    assert np.all(np.diff(td) >= 0)
    t2, v2 = downsample_minmax(t[:100], v[:100], 2000)
    assert len(v2) == 100


def test_recording_display_reports_downsampling():
    rec = synthetic_recording(duration_s=300, seed=1)
    d = recording_display(rec, max_points=1000)
    assert d["downsampled"] and d["n_display"] <= 1000 and d["n_source"] == 30000
    d2 = recording_display(rec, t_start=10, t_end=12, max_points=4000, components=("z",))
    assert not d2["downsampled"] and len(d2["components"]["z"]["t"]) == 201 and "n" not in d2["components"]
