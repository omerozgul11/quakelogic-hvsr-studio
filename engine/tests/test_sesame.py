import numpy as np

from hvsr_engine.sesame import evaluate, thresholds


def test_threshold_table_matches_guidelines():
    assert thresholds(0.1) == {"epsilon_factor": 0.25, "theta": 3.0, "log10_theta": 0.48}
    assert thresholds(0.3) == {"epsilon_factor": 0.20, "theta": 2.5, "log10_theta": 0.40}
    assert thresholds(0.7) == {"epsilon_factor": 0.15, "theta": 2.0, "log10_theta": 0.30}
    assert thresholds(1.5) == {"epsilon_factor": 0.10, "theta": 1.78, "log10_theta": 0.25}
    assert thresholds(5.0) == {"epsilon_factor": 0.05, "theta": 1.58, "log10_theta": 0.20}
    for f0 in (0.1, 0.3, 0.7, 1.5, 5.0):
        assert abs(np.log10(thresholds(f0)["theta"]) - thresholds(f0)["log10_theta"]) < 0.01


def _peak_curve(f0=2.0, a0=5.0, width=0.15):
    f = np.logspace(np.log10(0.2), np.log10(30), 300)
    curve = 1 + (a0 - 1) * np.exp(-0.5 * (np.log(f / f0) / width) ** 2)
    return f, curve


def test_all_criteria_pass_for_ideal_peak():
    f, curve = _peak_curve()
    sigma = np.full_like(f, np.log(1.2))
    wf = 2.0 + np.random.default_rng(0).normal(0, 0.02, 30)
    res = evaluate(f, curve, sigma, 2.0, 5.0, 60.0, 30, wf, (0.5, 20))
    assert res["evaluated"] and res["reliability_passed"] and res["clarity_passed_count"] == 6
    assert [c["id"] for c in res["reliability"]] == ["R1", "R2", "R3"]
    assert [c["id"] for c in res["clarity"]] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert all({"label", "value", "threshold", "passed", "detail"} <= set(c) for c in res["reliability"] + res["clarity"])


def test_individual_failures():
    f, curve = _peak_curve(f0=0.3, a0=1.5)
    sigma = np.full_like(f, np.log(3.5))
    wf = 0.3 + np.random.default_rng(0).normal(0, 0.2, 5)
    res = evaluate(f, curve, sigma, 0.3, 1.5, 20.0, 5, wf, (0.2, 20))
    by = {c["id"]: c for c in res["reliability"] + res["clarity"]}
    assert not by["R1"]["passed"]   # 0.3 < 10/20
    assert not by["R2"]["passed"]   # 20*5*0.3 = 30
    assert not by["R3"]["passed"]   # σ_A = 3.5 > 3
    assert not by["C3"]["passed"]   # A0 = 1.5
    assert not by["C5"]["passed"]   # σ_f = 0.2 > 0.2*0.3
    assert not by["C6"]["passed"]   # 3.5 > 2.5
    assert not res["reliability_passed"] and not res["clarity_passed"]


def test_not_evaluated_without_peak():
    f, curve = _peak_curve()
    res = evaluate(f, curve, np.zeros_like(f), None, None, 60, 10, np.array([]), (0.5, 20))
    assert not res["evaluated"] and res["reliability"] == [] and "Not evaluated" in res["message"]
