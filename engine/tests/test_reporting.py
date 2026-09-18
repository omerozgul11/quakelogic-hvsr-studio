"""Tests for hvsr_engine.reporting (figures + PDF report) using a contract-shaped fake result."""

from __future__ import annotations

import json
import os
import re
import types

import numpy as np
import pytest

from hvsr_engine.reporting import FIGURE_KINDS, build_report, figure


def make_fake_result(n_freq: int = 300, n_windows: int = 30, azimuthal: bool = True, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    f = np.logspace(np.log10(0.2), np.log10(30.0), n_freq)
    f0, a0 = 2.5, 4.0
    base = 1.0 + (a0 - 1.0) / (1.0 + ((np.log(f / f0)) / 0.25) ** 2)
    curves = []
    for _ in range(n_windows):
        curves.append(base * np.exp(rng.normal(0, 0.12, n_freq)))
    curves = np.asarray(curves)
    accepted = [i % 7 != 3 for i in range(n_windows)]
    acc = curves[np.asarray(accepted)]
    ln = np.log(acc)
    mu, sd = ln.mean(0), ln.std(0, ddof=1)
    geo = {"values": np.exp(mu).tolist(), "lower": np.exp(mu - sd).tolist(), "upper": np.exp(mu + sd).tolist(),
           "band": "exp(mean(ln HV) ± std(ln HV, ddof=1))", "sigma_ln": sd.tolist()}
    arith = {"values": acc.mean(0).tolist(), "lower": (acc.mean(0) - acc.std(0, ddof=1)).tolist(),
             "upper": (acc.mean(0) + acc.std(0, ddof=1)).tolist(), "band": "mean(HV) ± std(HV, ddof=1)"}
    med = {"values": np.median(acc, 0).tolist(), "lower": np.percentile(acc, 16, 0).tolist(),
           "upper": np.percentile(acc, 84, 0).tolist(), "band": "16th–84th percentile of window curves"}
    win_f0 = [float(f[int(np.argmax(c))]) for c in acc]
    items = []
    for i in range(n_windows):
        items.append({"index": i, "start_s": 30.0 * i, "end_s": 30.0 * i + 60.0, "accepted": accepted[i],
                      "reason": None if accepted[i] else "sta_lta", "sta_lta_max": float(rng.uniform(1, 3)),
                      "sta_lta_min": float(rng.uniform(0.1, 0.9)), "amp_ratio": float(rng.uniform(1, 4)),
                      "f0": float(f[int(np.argmax(curves[i]))]), "a0": float(curves[i].max())})
    az = None
    if azimuthal:
        azs = list(range(0, 180, 10))
        matrix = [(base * (1 + 0.3 * np.cos(np.radians(2 * a))) ).tolist() for a in azs]
        az = {"azimuths": azs, "frequency": f.tolist(), "matrix": matrix,
              "peak_frequency": [f0] * len(azs), "peak_amplitude": [a0] * len(azs)}
    return {
        "engine_version": "1.0.0",
        "versions": {"numpy": np.__version__, "python": "3.12"},
        "computed_at": "2026-01-01T00:00:00Z", "elapsed_s": 1.23, "random_seed": 12345,
        "params": {"window_length_s": 60, "overlap": 0.5, "detrend": "linear", "taper_percent": 5,
                   "smoothing": {"type": "konno_ohmachi", "bandwidth": 40}, "freq_min": 0.2, "freq_max": 30,
                   "n_freq": n_freq, "horizontal_method": "geometric_mean", "combination_stage": "after_smoothing",
                   "mean_method": "geometric", "peak": {"search_min": 0.5, "search_max": 20, "min_prominence": 0.0},
                   "vertical_floor": {"relative": 1e-6, "absolute": 1e-12}, "min_valid_windows": 3,
                   "screening": {"enabled": True, "sta_lta": {"enabled": True, "sta_s": 1, "lta_s": 30,
                                                              "min_ratio": 0.2, "max_ratio": 2.5},
                                 "amplitude": {"enabled": False}},
                   "bootstrap": {"enabled": True, "n_resamples": 200}, "azimuthal": {"enabled": azimuthal, "step_deg": 10},
                   "sesame": True},
        "input": {"path": "/tmp/x.npz", "sha256": "ab" * 32, "fs": 100.0, "n_samples": 120000, "duration_s": 1200.0,
                  "start_time": "2026-01-01T00:00:00.000000Z", "station": "SYN1", "is_synthetic": True},
        "frequency": f.tolist(),
        "windows": {"length_s": 60, "overlap": 0.5, "count_total": n_windows, "count_accepted": int(sum(accepted)),
                    "count_rejected": int(n_windows - sum(accepted)), "items": items},
        "curves": {"selected": "geometric", "geometric": geo, "arithmetic": arith, "median": med},
        "components": {"n": (base * 1e-3).tolist(), "e": (base * 1.1e-3).tolist(), "z": [1e-3] * n_freq,
                       "h": (base * 1.05e-3).tolist()},
        "directional": None,
        "masking": {"policy": "bins with smoothed |Z| below max(1e-12, 1e-6·max|Z|) are NaN", "bins_masked_any_window": 0,
                    "invalid_bins": [], "min_valid_windows": 3},
        "peaks": {"search_range": [0.5, 20], "candidates": [{"frequency": f0, "amplitude": a0, "prominence": 2.9, "rank": 1}],
                  "selected": {"frequency": f0, "amplitude": a0, "source": "automatic"}, "status": "clear",
                  "message": "One clear peak."},
        "peak_variability": {"window_f0": win_f0, "window_a0": [float(c.max()) for c in acc], "n": len(win_f0),
                             "median": float(np.median(win_f0)), "p16": float(np.percentile(win_f0, 16)),
                             "p84": float(np.percentile(win_f0, 84)), "std": float(np.std(win_f0, ddof=1)),
                             "std_ln": float(np.std(np.log(win_f0), ddof=1)),
                             "definition": "Highest local maximum of each accepted window curve in the search range",
                             "bootstrap": {"n_resamples": 200, "seed": 12345, "f0_p2_5": 2.3, "f0_p50": 2.5,
                                           "f0_p97_5": 2.7, "a0_p2_5": 3.6, "a0_p97_5": 4.4,
                                           "definition": "bootstrap percentile interval"}},
        "sesame": {"reference": "SESAME (2004) D23.12", "f0": f0, "a0": a0,
                   "reliability": [{"id": "R1", "label": "f0 > 10/lw", "passed": True, "value": f0, "threshold": 0.167, "detail": ""},
                                   {"id": "R2", "label": "nc > 200", "passed": True, "value": 3900, "threshold": 200, "detail": ""},
                                   {"id": "R3", "label": "sigma_A < 2", "passed": True, "value": 1.2, "threshold": 2, "detail": ""}],
                   "clarity": [{"id": f"C{i}", "label": f"criterion {i}", "passed": i != 5, "value": 1.0, "threshold": 2.0,
                                "detail": "x"} for i in range(1, 7)],
                   "reliability_passed": True, "clarity_passed_count": 5, "clarity_passed": True},
        "quality_flags": [{"code": "short_record", "severity": "warning", "message": "Record shorter than 30 min."}],
        "interpretation_notes": ["HVSR amplitude is not site amplification.", "No velocity profile is inferred."],
        "azimuthal": az,
    }


def _fake_recording(fs: float = 100.0, duration: float = 1200.0):
    rng = np.random.default_rng(1)
    n = int(fs * duration)
    return types.SimpleNamespace(n=rng.normal(size=n), e=rng.normal(size=n), z=rng.normal(size=n), fs=fs,
                                 start_time="2026-01-01T00:00:00.000000Z", meta={"units": "counts"})


@pytest.fixture(scope="module")
def result():
    return make_fake_result()


@pytest.mark.parametrize("kind", FIGURE_KINDS)
@pytest.mark.parametrize("fmt", ["png", "svg", "pdf"])
def test_figures_render(tmp_path, result, kind, fmt):
    out = tmp_path / f"{kind}.{fmt}"
    rec = _fake_recording() if kind == "windows" else None
    path = figure(result, kind, fmt, str(out), recording=rec)
    assert os.path.exists(path) and os.path.getsize(path) > 1000
    head = open(path, "rb").read(8)
    if fmt == "png":
        assert head.startswith(b"\x89PNG")
    elif fmt == "pdf":
        assert head.startswith(b"%PDF")
    else:
        assert b"<" in open(path, "rb").read(200)


def test_windows_figure_requires_recording(tmp_path, result):
    with pytest.raises(ValueError):
        figure(result, "windows", "png", str(tmp_path / "w.png"))


def test_unknown_figure_and_format(tmp_path, result):
    with pytest.raises(ValueError):
        figure(result, "nope", "png", str(tmp_path / "x.png"))
    with pytest.raises(ValueError):
        figure(result, "hvsr", "gif", str(tmp_path / "x.gif"))


def test_figure_dark_theme_and_window_curves(tmp_path, result):
    wc = {"frequency": result["frequency"], "curves": [result["curves"]["geometric"]["values"]] * 3,
          "accepted": [True, False, True]}
    path = figure(result, "hvsr", "png", str(tmp_path / "dark.png"), theme="dark", window_curves=wc)
    assert os.path.getsize(path) > 1000


def test_pdf_report(tmp_path, result):
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    (analysis_dir / "result.json").write_text(json.dumps(result))
    context = {
        "project": {"name": "Demo project", "description": "Synthetic validation"},
        "station": {"code": "SYN1", "name": "Synthetic site", "latitude": 37.0, "longitude": -122.0,
                    "elevation": 12.0, "sensor_orientation_deg": 0.0},
        "recording": {"name": "synthetic_site_A", "sample_rate": 100.0, "start_time": "2026-01-01T00:00:00Z",
                      "duration_s": 1200.0, "n_samples": 120000, "units": "counts", "channels": "HHN/HHE/HHZ",
                      "is_synthetic": True},
        "source_files": [{"name": "synthetic_site_A.txt", "role": "all", "size_bytes": 12345, "sha256": "cd" * 32}],
        "processing_steps": [{"op": "demean", "params": {}}, {"op": "filter", "params": {"kind": "highpass", "freq_low": 0.1, "order": 4}}],
        "app_version": "1.0.0",
    }
    progress = []
    out = build_report(result, context, str(tmp_path / "report.pdf"), str(analysis_dir),
                       recording=_fake_recording(), progress=lambda f, m: progress.append((f, m)))
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF")
    assert len(data) > 20_000
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    assert pages >= 4
    assert progress and progress[-1][0] == 1.0


def test_pdf_report_minimal_context(tmp_path):
    res = make_fake_result(azimuthal=False)
    res["sesame"] = None
    res["peaks"]["selected"] = None
    res["peak_variability"]["bootstrap"] = None
    out = build_report(res, {}, str(tmp_path / "min.pdf"), str(tmp_path))
    assert open(out, "rb").read().startswith(b"%PDF")


def test_pdf_report_us_units_and_disclaimer(tmp_path):
    from hvsr_engine.reporting.pdf import copyright_line, display_amplitude_unit, format_elevation
    res = make_fake_result(azimuthal=False)
    context = {
        "unit_system": "us",
        "station": {"code": "SYN1", "elevation": 12.0},
        "recording": {"name": "synthetic_site_A", "units": "m/s", "unit_kind": "velocity", "is_synthetic": True},
        "app_version": "1.0.0",
    }
    out = build_report(res, context, str(tmp_path / "us.pdf"), str(tmp_path))
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF")
    # helpers used by the report
    assert format_elevation(12.0, "us") == "39.4 ft (12.00 m)"
    assert format_elevation(12.0, "metric") == "12.00 m (39.4 ft)"
    assert display_amplitude_unit("m/s", "velocity", "us") == ("in/s", 39.37007874015748)
    assert display_amplitude_unit("counts", "raw", "us") == ("counts", 1.0)
    assert display_amplitude_unit("cm/s^2", "acceleration", "us")[0] == "in/s²"
    assert copyright_line("2026-09-15 19:00 UTC") == "© 2026 QuakeLogic Inc. All rights reserved."
    # the disclaimer heading, copyright and company block are in the story: check via an uncompressed build
    from reportlab import rl_config
    rl_config.pageCompression = 0
    out2 = build_report(res, context, str(tmp_path / "us-plain.pdf"), str(tmp_path))
    rl_config.pageCompression = 1
    plain = open(out2, "rb").read()
    assert b"Disclaimer" in plain
    assert b"QuakeLogic Inc. All rights reserved." in plain
    assert b"Roseville, CA 95678" in plain
