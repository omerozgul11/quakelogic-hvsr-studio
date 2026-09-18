import numpy as np

from hvsr_engine.io.canonical import Recording
from hvsr_engine.validation import check_regular_sampling, validate_recording


def _rec(n=30000, fs=100.0):
    rng = np.random.default_rng(0)
    return Recording(rng.normal(size=n), rng.normal(size=n), rng.normal(size=n), fs, meta={"units": "counts", "unit_kind": "raw"})


def codes(issues):
    return {i["code"]: i["severity"] for i in issues}


def test_clean_recording_has_no_errors():
    assert not any(i["severity"] == "error" for i in validate_recording(_rec()))


def test_nan_and_constant_are_errors():
    rec = _rec()
    rec.n[100] = np.nan
    rec.e[:] = 3.0
    c = codes(validate_recording(rec))
    assert c["nan_values"] == "error" and c["constant_channel"] == "error"
    detail = next(i for i in validate_recording(rec) if i["code"] == "nan_values")["details"]
    assert detail == {"component": "n", "count": 1, "first_index": 100}


def test_clipping_is_a_warning():
    rec = _rec()
    rec.z = np.clip(rec.z, -1.5, 1.5)
    c = codes(validate_recording(rec))
    assert c.get("clipping_suspected") == "warning"


def test_short_record_and_unknown_units():
    rec = _rec(n=5000)
    rec.meta = {}
    c = codes(validate_recording(rec))
    assert c["short_record"] == "warning" and c["unit_unknown"] == "info"


def test_regular_sampling_checks():
    t = np.arange(1000) / 50.0
    fs, issues = check_regular_sampling(t)
    assert abs(fs - 50) < 1e-9 and not issues
    t2 = np.concatenate([t[:500], t[500:] + 2.0])  # 2 s gap
    fs, issues = check_regular_sampling(t2)
    assert issues[0]["code"] == "gaps" and issues[0]["details"]["first_index"] == 499
    t3 = t.copy()
    t3[10] = t3[9]
    fs, issues = check_regular_sampling(t3)
    assert {i["code"] for i in issues} >= {"duplicate_timestamps"}
