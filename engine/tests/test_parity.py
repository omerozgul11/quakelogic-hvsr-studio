"""Parity additions: window modes, variable-length analysis, forward modelling, curve files,
SAF / generic seismic import, survey section in the report, new service endpoints."""
from __future__ import annotations

import json
import time

import numpy as np
import pytest

from hvsr_engine.hvsr import analyze, load_result, select_peak, write_result
from hvsr_engine.io.canonical import save_recording
from hvsr_engine.io.curves import read_curve_file, write_hv
from hvsr_engine.io.importer import import_recording
from hvsr_engine.io.inspect import inspect_file
from hvsr_engine.modelling import model_hvsr, poisson_from_vp_vs, vp_from_poisson
from hvsr_engine.synthetic import synthetic_recording
from hvsr_engine.windows import pack_windows, resolve_window_params, screen_windows


# ---------------------------------------------------------------- windows ------------------------------------------

def test_legacy_aliases_still_define_fixed_windows(syn_rec):
    out = screen_windows(syn_rec, {"window_length_s": 30.0, "overlap": 0.0})
    assert out["mode"] == "fixed" and out["counts"]["total"] == 40
    assert all(abs(w["length_s"] - 30.0) < 1e-9 for w in out["windows"])
    assert [w["color_index"] for w in out["windows"]] == list(range(40))
    assert abs(out["t10_hz"] - 10.0 / 30.0) < 1e-12


def test_custom_windows_are_used_and_appended(syn_rec):
    out = screen_windows(syn_rec, {"windows": {"mode": "custom", "custom": [[10, 40], [100, 145.5]]}, "screening": {"enabled": False}})
    assert out["mode"] == "custom" and out["counts"]["total"] == 2
    assert [w["length_s"] for w in out["windows"]] == [30.0, 45.5]
    out2 = screen_windows(syn_rec, {"windows": {"mode": "fixed", "length_s": 60, "overlap": 0, "custom": [[5, 20]]},
                                    "screening": {"enabled": False}})
    assert out2["counts"]["total"] == 21 and out2["windows"][0]["start_s"] == 0.0 and out2["windows"][1]["start_s"] == 5.0


def test_pack_windows_greedy():
    quiet = np.ones(1000, dtype=bool)
    quiet[400:420] = False  # a 20-sample transient
    wins = pack_windows(quiet, fs=1.0, min_length_s=100, max_length_s=250)
    assert wins == [(0, 250), (250, 400), (420, 670), (670, 920)]


def test_auto_variable_avoids_transients(syn_rec):
    rec = syn_rec.copy()
    rec.n[30000:30200] += 50 * np.nanstd(rec.n)  # 2-s burst at t = 300 s
    out = screen_windows(rec, {"windows": {"mode": "auto_variable", "min_length_s": 20, "max_length_s": 60,
                                           "levels": {"enabled": True, "mode": "ratio_rms", "ratio": 6.0}},
                               "screening": {"enabled": False}})
    assert out["mode"] == "auto_variable"
    assert out["counts"]["total"] > 10
    lengths = {round(w["length_s"]) for w in out["windows"]}
    assert lengths <= set(range(20, 61))
    assert not any(w["start_s"] <= 300.0 < w["end_s"] for w in out["windows"])


def test_bad_mode_and_bad_lengths_raise():
    with pytest.raises(ValueError):
        resolve_window_params({"windows": {"mode": "nope"}})
    with pytest.raises(ValueError):
        resolve_window_params({"windows": {"mode": "auto_variable", "min_length_s": 60, "max_length_s": 30}})


def test_analyze_with_variable_window_lengths(syn_rec):
    params = {"windows": {"mode": "custom", "custom": [[0, 60], [60, 100], [100, 160], [160, 190], [190, 250], [250, 310]]},
              "freq_min": 0.5, "freq_max": 20, "n_freq": 120, "bootstrap": {"enabled": True, "n_resamples": 20},
              "azimuthal": {"enabled": True, "step_deg": 45}}
    res = analyze(syn_rec, params, random_seed=1)
    d = res.to_dict()
    assert d["windows"]["mode"] == "custom" and d["windows"]["count_total"] == 6
    assert sorted({round(w["length_s"]) for w in d["windows"]["items"]}) == [30, 40, 60]
    assert abs(d["t10_hz"] - 10.0 / 60.0) < 1e-9
    tf = d["time_frequency"]
    assert len(tf["times_s"]) == 6 and len(tf["matrix"]) == 6 and len(tf["matrix"][0]) == 120
    assert d["peaks"]["selected"] and abs(d["peaks"]["selected"]["frequency"] - 2.5) / 2.5 < 0.15
    assert d["azimuthal"] and len(d["azimuthal"]["azimuths"]) == 4
    # SESAME n_c uses the mean accepted length × n windows
    r2 = next(c for c in d["sesame"]["reliability"] if c["id"] == "R2")
    assert abs(r2["value"] - d["windows"]["mean_accepted_length_s"] * d["windows"]["count_accepted"] * d["sesame"]["f0"]) < 1e-6


def test_write_result_includes_hv_and_time_frequency(syn_rec, tmp_path):
    res = analyze(syn_rec, {"window_length_s": 60, "freq_min": 0.5, "freq_max": 20, "n_freq": 80,
                            "bootstrap": {"enabled": False}}, random_seed=2)
    write_result(res, tmp_path)
    assert (tmp_path / "exports" / "hvsr_mean.hv").exists()
    curve = read_curve_file(tmp_path / "exports" / "hvsr_mean.hv")
    assert curve["format"] == "geopsy_hv" and curve["n_points"] > 50 and curve["lower"] is not None
    d = load_result(tmp_path)
    assert "time_frequency" in d and "t10_hz" in d
    d2 = select_peak(tmp_path, 2.6)
    assert d2["peaks"]["selected"]["source"] == "manual" and "time_frequency" in d2


# ---------------------------------------------------------------- modelling ----------------------------------------

def test_single_layer_peak_at_vs_over_4h():
    r = model_hvsr([{"thickness_m": 50, "vs": 200, "vp": 400, "density": 1800}, {"vs": 800, "vp": 1600, "density": 2200}],
                   0.2, 20, 600)
    assert abs(r["f0_model"] - 1.0) / 1.0 < 0.05
    assert r["a0_model"] > 1.5
    assert r["layers"][0]["depth_bottom_m"] == 50 and r["layers"][1]["half_space"]


def test_half_space_is_flat_and_vs30_uniform():
    r = model_hvsr([{"vs": 300, "vp": 600, "density": 2000}], 0.2, 20, 50)
    assert max(r["hvsr"]) == pytest.approx(1.0) and min(r["hvsr"]) == pytest.approx(1.0)
    assert r["vs30"] == pytest.approx(300.0)
    u = model_hvsr([{"thickness_m": 10, "vs": 250, "poisson": 0.3}, {"thickness_m": 20, "vs": 250, "poisson": 0.3}, {"vs": 250, "poisson": 0.3}])
    assert u["vs30"] == pytest.approx(250.0)


def test_vs30_vseq_and_poisson():
    r = model_hvsr([{"thickness_m": 8, "vs": 120, "poisson": 0.35, "density": 2000},
                    {"thickness_m": 12, "vs": 250, "poisson": 0.33, "density": 2000},
                    {"vs": 800, "vp": 1600, "density": 2200}], vs30_offset_m=0)
    # Vs30: 8 m @120, 12 m @250, 10 m @800
    expected_vs30 = 30.0 / (8 / 120 + 12 / 250 + 10 / 800)
    assert r["vs30"] == pytest.approx(expected_vs30, rel=1e-6)
    assert r["vseq"]["depth_m"] == pytest.approx(20.0)
    assert r["vseq"]["value"] == pytest.approx(20.0 / (8 / 120 + 12 / 250), rel=1e-6)
    assert r["layers"][0]["vp"] == pytest.approx(vp_from_poisson(120, 0.35))
    assert poisson_from_vp_vs(vp_from_poisson(200, 0.3), 200) == pytest.approx(0.3)
    assert r["layers"][2]["poisson"] == pytest.approx(poisson_from_vp_vs(1600, 800))
    with pytest.raises(ValueError):
        model_hvsr([{"thickness_m": 5, "vs": -1}, {"vs": 300}])
    with pytest.raises(ValueError):
        model_hvsr([{"thickness_m": 5, "vs": 100, "poisson": 0.6}, {"vs": 300}])


# ---------------------------------------------------------------- curves -------------------------------------------

def test_curve_file_round_trip_and_csv(tmp_path):
    f = np.logspace(-1, 1, 30)
    v = 1 + 3 * np.exp(-((np.log(f) - np.log(2)) ** 2) / 0.05)
    p = write_hv(tmp_path / "c.hv", f, v, v * 0.8, v * 1.2, name="Test curve")
    c = read_curve_file(p)
    assert c["name"] == "Test curve" and c["n_points"] == 30
    assert np.allclose(c["values"], v, rtol=1e-5) and np.allclose(c["upper"], v * 1.2, rtol=1e-5)
    csv_path = tmp_path / "c.csv"
    csv_path.write_text("frequency,hv\n" + "\n".join(f"{a},{b}" for a, b in zip(f, v)))
    c2 = read_curve_file(csv_path)
    assert c2["format"] == "csv" and c2["lower"] is None and np.allclose(c2["values"], v, rtol=1e-5)


# ---------------------------------------------------------------- formats ------------------------------------------

def _write_saf(path, rec, channels=("V", "N", "E")):
    lines = ["SESAME ASCII data format (saf) v. 1", "# generated for tests", "STA_CODE = TST",
             "START_TIME = 2024 01 05 21 15 04.000", f"SAMP_FREQ = {rec.fs:g}", f"NDAT = {rec.n_samples}",
             f"CH0_ID = {channels[0]}", f"CH1_ID = {channels[1]}", f"CH2_ID = {channels[2]}", "UNITS = counts",
             "####" + "-" * 60]
    body = "\n".join(f"{z:.4f} {n:.4f} {e:.4f}" for z, n, e in zip(rec.z, rec.n, rec.e))
    path.write_text("\n".join(lines) + "\n" + body + "\n")


def test_saf_inspect_and_import(short_rec, tmp_path):
    path = tmp_path / "rec.saf"
    _write_saf(path, short_rec)
    info = inspect_file(path)
    assert info["format"] == "saf" and info["saf"]["sample_rate"] == 100.0 and info["saf"]["channels"] == ["V", "N", "E"]
    assert info["saf"]["columns"] == {"z": 0, "n": 1, "e": 2}
    out = tmp_path / "rec.npz"
    res = import_recording({"recording_id": "x", "output_path": str(out), "sources": [{"path": str(path), "role": "all"}],
                            "format": "saf", "metadata": {"is_synthetic": True}})
    assert res["ok"], res["validation"]
    assert res["meta"]["fs"] == 100.0 and res["meta"]["n_samples"] == short_rec.n_samples
    assert res["meta"]["start_time"].startswith("2024-01-05T21:15:04")
    assert res["meta"]["channels"] == {"z": "V", "n": "N", "e": "E"} and res["meta"]["station"] == "TST"


def test_gse2_inspect_and_import(short_rec, tmp_path):
    import obspy
    st = obspy.Stream()
    for name, data in (("N", short_rec.n), ("E", short_rec.e), ("Z", short_rec.z)):
        tr = obspy.Trace(np.asarray(data, dtype=np.int32))
        tr.stats.update({"network": "XX", "station": "GSE", "channel": f"HH{name}", "sampling_rate": short_rec.fs,
                         "starttime": obspy.UTCDateTime("2024-01-01T00:00:00")})
        st += tr
    path = tmp_path / "rec.gse"
    st.write(str(path), format="GSE2")
    info = inspect_file(path)
    assert info["format"] == "seismic" and info["mseed"]["n_traces"] == 3
    ids = {t["channel"][-1].lower(): t["id"] for t in info["mseed"]["traces"]}
    res = import_recording({"recording_id": "g", "output_path": str(tmp_path / "g.npz"),
                            "sources": [{"path": str(path), "role": "all"}], "format": "seismic",
                            "mseed": {"n": ids["n"], "e": ids["e"], "z": ids["z"]}, "metadata": {"is_synthetic": True}})
    assert res["ok"], res["validation"]
    assert res["meta"]["n_samples"] == short_rec.n_samples and res["meta"]["channels"]["n"] == "HHN"


# ---------------------------------------------------------------- report -------------------------------------------

def test_report_survey_section_with_photos(syn_rec, tmp_path):
    from hvsr_engine.reporting.pdf import build_report
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    res = analyze(syn_rec, {"window_length_s": 60, "freq_min": 0.5, "freq_max": 20, "n_freq": 60,
                            "bootstrap": {"enabled": False}, "sesame": True}, random_seed=5)
    d = write_result(res, tmp_path)
    (tmp_path / "survey").mkdir()
    for i in (1, 2):
        fig, ax = plt.subplots(figsize=(3, 2))
        ax.plot([0, 1], [i, 0])
        fig.savefig(tmp_path / "survey" / f"photo{i}.png")
        plt.close(fig)
    context = {"project": {"name": "P"}, "station": {"code": "SYN"}, "recording": {"name": "R"}, "app_version": "t",
               "survey": {"date": "2024-01-05", "client": "ACME", "place_id": "Perugia", "address": "Via X 1",
                          "latitude": 43.1, "longitude": 12.4, "datum": "WGS84", "elevation_m": 300, "weather": "sunny",
                          "notes": "quiet site", "photos": [{"file": "survey/photo1.png", "caption": "north view"},
                                                             {"file": "survey/photo2.png", "caption": "sensor"}]}}
    out = build_report(d, context, str(tmp_path / "r.pdf"), str(tmp_path))
    pdf = (tmp_path / "r.pdf").read_bytes()
    assert len(pdf) > 30000 and pdf.count(b"/Type /Page") >= 5
    # photos are embedded as image XObjects
    assert pdf.count(b"/Subtype /Image") >= 2


# ---------------------------------------------------------------- service -------------------------------------------

def test_service_model_and_curve_endpoints(tmp_path):
    from fastapi.testclient import TestClient
    from hvsr_service.app import create_app

    with TestClient(create_app(workers=1)) as client:
        r = client.post("/model/hvsr", json={"layers": [{"thickness_m": 25, "vs": 200, "poisson": 0.33}, {"vs": 900, "vp": 1800}],
                                              "freq_min": 0.5, "freq_max": 20, "n_freq": 100})
        assert r.status_code == 200, r.text
        body = r.json()
        assert abs(body["f0_model"] - 2.0) / 2.0 < 0.1 and body["vs30"] > 0
        bad = client.post("/model/hvsr", json={"layers": [{"thickness_m": 25, "vs": 200, "poisson": 0.7}, {"vs": 900}]})
        assert bad.status_code == 422
        f = np.logspace(-0.5, 1, 20)
        p = write_hv(tmp_path / "x.hv", f, np.ones(20) * 2, name="External")
        r2 = client.post("/curves/import", json={"path": str(p)})
        assert r2.status_code == 200 and r2.json()["name"] == "External" and r2.json()["n_points"] == 20
        assert client.post("/curves/import", json={"path": str(tmp_path / "missing.hv")}).status_code == 404


def test_service_windows_endpoint_with_modes(tmp_path):
    from fastapi.testclient import TestClient
    from hvsr_service.app import create_app

    rec = synthetic_recording(fs=100.0, duration_s=300.0, f0=3.0, amplification=4.0, seed=9)
    path = tmp_path / "r.npz"
    save_recording(rec, path)
    with TestClient(create_app(workers=1)) as client:
        r = client.post("/hvsr/windows", json={"input_path": str(path), "params": {"windows": {"mode": "auto_variable", "min_length_s": 20,
                                                                                               "max_length_s": 40}}})
        assert r.status_code == 200 and r.json()["mode"] == "auto_variable" and r.json()["counts"]["total"] >= 5
        r = client.post("/hvsr/analyze", json={"input_path": str(path), "output_dir": str(tmp_path / "a"),
                                               "params": {"windows": {"mode": "custom", "custom": [[0, 50], [50, 90], [90, 150], [150, 200]]},
                                                          "freq_min": 0.5, "freq_max": 20, "n_freq": 50, "bootstrap": {"enabled": False}}})
        job = r.json()
        t0 = time.time()
        while job["status"] in ("queued", "running") and time.time() - t0 < 60:
            time.sleep(0.2)
            job = client.get(f"/jobs/{job['id']}").json()
        assert job["status"] == "done", job
        d = json.loads((tmp_path / "a" / "result.json").read_text())
        assert d["windows"]["count_total"] == 4 and (tmp_path / "a" / "exports" / "hvsr_mean.hv").exists()
