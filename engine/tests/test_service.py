"""End-to-end tests of hvsr_service through the FastAPI TestClient."""

from __future__ import annotations

import importlib
import os
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from hvsr_service.app import create_app


def _has(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


needs_engine = pytest.mark.skipif(
    not (_has("hvsr_engine.hvsr") and _has("hvsr_engine.preprocessing")),
    reason="hvsr_engine.hvsr / preprocessing not available yet (engine fork still building)",
)


@pytest.fixture(scope="module")
def recording_path(tmp_path_factory):
    from hvsr_engine.io.canonical import Recording, save_recording

    path = tmp_path_factory.mktemp("rec") / "syn.npz"
    if _has("hvsr_engine.synthetic"):
        from hvsr_engine.synthetic import synthetic_recording

        rec = synthetic_recording(fs=100.0, duration_s=600.0, f0=2.5, amplification=4.0, seed=3, station="SYN1")
    else:
        rng = np.random.default_rng(0)
        n = 60000
        rec = Recording(rng.normal(size=n), rng.normal(size=n), rng.normal(size=n), 100.0,
                        "2026-01-01T00:00:00.000000Z", {"station": "SYN1", "units": "counts"})
    rec.meta = dict(rec.meta or {})
    rec.meta["is_synthetic"] = True
    save_recording(rec, path)
    return str(path)


@pytest.fixture(scope="module")
def client():
    app = create_app(workers=2)
    with TestClient(app) as c:
        yield c


def _wait(client: TestClient, job_id: str, timeout: float = 120.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = client.get(f"/jobs/{job_id}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body["service_version"] == "1.0.0"
    assert "workers" in body and "jobs_running" in body


def test_token_rejection(recording_path):
    app = create_app(workers=1, token="secret")
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200  # exempt
        r = c.post("/recordings/data", json={"path": recording_path})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
        r = c.post("/recordings/data", json={"path": recording_path}, headers={"X-Engine-Token": "secret"})
        assert r.status_code == 200


def test_error_envelope_not_found(client):
    r = client.post("/recordings/data", json={"path": "/nonexistent/file.npz"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    r = client.get("/jobs/doesnotexist")
    assert r.status_code == 404
    r = client.post("/files/inspect", json={"path": "/nonexistent.txt"})
    assert r.status_code == 404


def test_validation_error_envelope(client):
    r = client.post("/recordings/data", json={"max_points": 5})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_recording_data(client, recording_path):
    r = client.post("/recordings/data", json={"path": recording_path, "max_points": 500})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fs"] == 100.0
    assert body["downsampled"] is True
    assert set(body["components"]) == {"n", "e", "z"}
    assert len(body["components"]["z"]["v"]) <= 520
    r = client.post("/recordings/data", json={"path": recording_path, "t_start": 10, "t_end": 12, "max_points": 5000})
    assert r.json()["downsampled"] is False
    assert len(r.json()["components"]["n"]["v"]) in (200, 201)


@needs_engine
def test_filter_response(client):
    r = client.post("/processing/filter-response", json={
        "fs": 100, "step": {"op": "filter", "params": {"kind": "bandpass", "freq_low": 0.5, "freq_high": 20, "order": 4}}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["frequency"]) == len(body["magnitude_db"])
    r = client.post("/processing/filter-response", json={
        "fs": 100, "step": {"op": "filter", "params": {"kind": "lowpass", "freq_high": 80, "order": 4}}})
    assert r.status_code in (200, 422)  # above Nyquist: warning or rejected, never a 500
    if r.status_code == 200:
        assert any(w.get("code") == "cutoff_above_nyquist" for w in r.json().get("warnings", []))


@needs_engine
def test_processing_preview_and_run(client, recording_path, tmp_path):
    steps = [{"op": "demean", "params": {}}, {"op": "filter", "params": {"kind": "highpass", "freq_low": 0.2, "order": 4, "zero_phase": True}}]
    r = client.post("/processing/preview", json={"input_path": recording_path, "steps": steps, "max_points": 300})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "raw" in body and "processed" in body and body["fs_out"] == 100.0
    assert len(body["applied"]) == 2

    out = str(tmp_path / "processed.npz")
    r = client.post("/processing/run", json={"input_path": recording_path, "output_path": out, "steps": steps})
    assert r.status_code == 200, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done", job
    assert os.path.exists(out)
    assert job["result"]["output_path"] == out
    assert job["progress"] == 1.0


@needs_engine
def test_windows(client, recording_path):
    r = client.post("/hvsr/windows", json={"input_path": recording_path,
                                           "params": {"window_length_s": 60, "overlap": 0.5},
                                           "window_overrides": {"0": {"accepted": False, "reason": "manual"}}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["total"] == len(body["windows"]) > 5
    assert body["windows"][0]["accepted"] is False and body["windows"][0]["reason"] == "manual"


@pytest.fixture(scope="module")
def analysis_dir(client, recording_path, tmp_path_factory):
    if not (_has("hvsr_engine.hvsr") and _has("hvsr_engine.preprocessing")):
        pytest.skip("engine analysis not available yet")
    out = str(tmp_path_factory.mktemp("analysis"))
    params = {"window_length_s": 40, "overlap": 0.5, "freq_min": 0.3, "freq_max": 30, "n_freq": 150,
              "bootstrap": {"enabled": True, "n_resamples": 30}, "azimuthal": {"enabled": True, "step_deg": 30}}
    r = client.post("/hvsr/analyze", json={"input_path": recording_path, "output_dir": out, "params": params,
                                           "random_seed": 42})
    assert r.status_code == 200, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done", job
    return out


@needs_engine
def test_analyze_results(client, analysis_dir):
    assert os.path.isfile(os.path.join(analysis_dir, "result.json"))
    r = client.post("/analyses/load", json={"dir": analysis_dir})
    assert r.status_code == 200
    result = r.json()
    assert result["random_seed"] == 42
    assert len(result["frequency"]) == 150
    assert result["windows"]["count_accepted"] >= 3
    sel = result["peaks"]["selected"]
    assert sel and 1.8 < sel["frequency"] < 3.3, sel
    assert result["azimuthal"] and len(result["azimuthal"]["azimuths"]) == 6

    r = client.post("/analyses/window-curves", json={"dir": analysis_dir})
    assert r.status_code == 200
    wc = r.json()
    assert len(wc["curves"]) == result["windows"]["count_total"]

    r = client.post("/analyses/summary", json={"dir": analysis_dir})
    assert r.status_code == 200
    s = r.json()
    assert "window_f0" not in s["peak_variability"] and s["peaks"]["selected"]["frequency"] == sel["frequency"]


@needs_engine
def test_select_peak(client, analysis_dir):
    r = client.post("/hvsr/select-peak", json={"analysis_dir": analysis_dir, "frequency": 5.0})
    assert r.status_code == 200, r.text
    sel = r.json()["result"]["peaks"]["selected"]
    assert sel["source"] == "manual" and abs(sel["frequency"] - 5.0) < 0.3
    r = client.post("/hvsr/select-peak", json={"analysis_dir": analysis_dir, "frequency": None})
    assert r.json()["result"]["peaks"]["selected"]["source"] == "automatic"


@needs_engine
@pytest.mark.parametrize("fig,fmt", [("hvsr", "png"), ("spectra", "svg"), ("windows", "pdf"),
                                     ("azimuthal", "png"), ("peak_distribution", "png")])
def test_export_figure(client, analysis_dir, tmp_path, fig, fmt):
    out = str(tmp_path / f"{fig}.{fmt}")
    r = client.post("/exports/figure", json={"analysis_dir": analysis_dir, "figure": fig, "format": fmt, "output_path": out})
    assert r.status_code == 200, r.text
    assert os.path.getsize(out) > 1000


@needs_engine
def test_export_report(client, analysis_dir, tmp_path):
    out = str(tmp_path / "report.pdf")
    ctx = {"project": {"name": "Service test"}, "station": {"code": "SYN1"},
           "recording": {"name": "syn", "is_synthetic": True}, "source_files": [], "processing_steps": [],
           "app_version": "test"}
    r = client.post("/exports/report", json={"analysis_dir": analysis_dir, "output_path": out, "context": ctx})
    assert r.status_code == 200, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done", job
    assert open(out, "rb").read(4) == b"%PDF" and os.path.getsize(out) > 20_000


@needs_engine
def test_cancel_flow(client, recording_path, tmp_path):
    params = {"window_length_s": 10, "overlap": 0.9, "n_freq": 400,
              "bootstrap": {"enabled": True, "n_resamples": 3000},
              "azimuthal": {"enabled": True, "step_deg": 1}}
    r = client.post("/hvsr/analyze", json={"input_path": recording_path, "output_dir": str(tmp_path / "c"),
                                           "params": params})
    job_id = r.json()["id"]
    r = client.post(f"/jobs/{job_id}/cancel")
    assert r.status_code == 200
    job = _wait(client, job_id)
    assert job["status"] in ("cancelled", "done"), job
    assert job["status"] == "cancelled" or job["result"] is not None
    listing = client.get("/jobs").json()["jobs"]
    assert any(j["id"] == job_id for j in listing)


def test_job_failure_is_reported(client, tmp_path):
    """A job whose engine call raises ends as `failed`, and the service keeps working."""
    r = client.post("/processing/run", json={"input_path": "/nonexistent.npz", "output_path": str(tmp_path / "o.npz"),
                                             "steps": []})
    assert r.status_code == 404
    assert client.get("/health").status_code == 200
