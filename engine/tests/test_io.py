import numpy as np
import pytest

from hvsr_engine.io.canonical import Recording, load_recording, save_recording
from hvsr_engine.io.importer import import_recording
from hvsr_engine.io.inspect import inspect_file


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def _req(paths_roles, fmt="ascii", ascii_cfg=None, mseed=None, out=None, metadata=None):
    return {"recording_id": "t", "output_path": out, "format": fmt,
            "sources": [{"path": p, "role": r} for p, r in paths_roles],
            "ascii": ascii_cfg or {}, "mseed": mseed or {}, "metadata": metadata or {}}


def test_canonical_roundtrip(tmp_path):
    rec = Recording(np.arange(5.0), np.arange(5.0) * 2, np.arange(5.0) * 3, 50.0, "2024-05-01T10:00:00.000000Z",
                    {"station": "ABC", "units": "counts"})
    meta = save_recording(rec, tmp_path / "r.npz")
    back = load_recording(tmp_path / "r.npz")
    assert back.fs == 50.0 and back.start_time == rec.start_time and back.meta["station"] == "ABC"
    np.testing.assert_array_equal(back.e, rec.e)
    assert meta["n_samples"] == 5 and back.end_time().startswith("2024-05-01T10:00:00.08")


def test_inspect_and_import_tab_txt_with_comments_and_seconds_column(tmp_path):
    lines = ["# synthetic test file", "# sample rate: 50 Hz", "t\tN\tE\tZ"]
    for i in range(2000):
        lines.append(f"{i / 50:.3f}\t{np.sin(i / 7):.4f}\t{np.cos(i / 5):.4f}\t{np.sin(i / 3):.4f}")
    p = _write(tmp_path / "a.txt", "\n".join(lines) + "\n")
    info = inspect_file(p)
    a = info["ascii"]
    assert info["format"] == "ascii" and a["delimiter"] == "\t" and a["header_rows"] == 1 and a["comment_prefix"] == "#"
    assert a["sample_rate_hint"] == 50.0 and a["time_column_guess"] == {"index": 0, "kind": "seconds", "sample_rate_estimate": 50.0}
    assert [c["name"] for c in a["columns"]] == ["t", "N", "E", "Z"]
    assert len(info["sha256"]) == 64
    res = import_recording(_req([(p, "all")], ascii_cfg={"delimiter": "\t", "header_rows": 1, "comment_prefix": "#",
                                                          "columns": {"n": 1, "e": 2, "z": 3},
                                                          "time": {"mode": "seconds_column", "column": 0},
                                                          "start_time": "2024-01-01T00:00:00Z"}, out=str(tmp_path / "o.npz")))
    assert res["ok"], res["validation"]
    assert res["meta"]["fs"] == 50.0 and res["meta"]["n_samples"] == 2000
    rec = load_recording(tmp_path / "o.npz")
    assert abs(rec.e[0] - 1.0) < 1e-6


def test_decimal_comma_semicolon_csv(tmp_path):
    lines = ["N;E;Z"] + [f"{np.sin(i / 7):.3f};{np.cos(i / 5):.3f};{np.sin(i / 3):.3f}".replace(".", ",") for i in range(1000)]
    p = _write(tmp_path / "dc.csv", "\n".join(lines) + "\n")
    info = inspect_file(p)["ascii"]
    assert info["delimiter"] == ";" and info["decimal"] == "," and info["header_rows"] == 1
    res = import_recording(_req([(p, "all")], ascii_cfg={"delimiter": ";", "decimal": ",", "header_rows": 1,
                                                          "columns": {"n": 0, "e": 1, "z": 2},
                                                          "time": {"mode": "sample_rate", "sample_rate": 20}}, out=str(tmp_path / "o.npz")))
    assert res["ok"]
    rec = load_recording(tmp_path / "o.npz")
    assert abs(rec.e[0] - 1.0) < 1e-6 and rec.fs == 20.0
    assert any(i["code"] == "start_time_assumed" for i in res["validation"]["issues"])


def test_missing_sample_rate_is_blocking(tmp_path):
    p = _write(tmp_path / "x.txt", "\n".join(f"{i} {i * 2} {i * 3}" for i in range(500)) + "\n")
    res = import_recording(_req([(p, "all")], ascii_cfg={"delimiter": "whitespace", "columns": {"n": 0, "e": 1, "z": 2},
                                                          "time": {"mode": "sample_rate"}}, out=str(tmp_path / "o.npz")))
    assert not res["ok"] and res["validation"]["blocking"]
    assert res["validation"]["issues"][0]["code"] == "no_timing_information"
    assert not (tmp_path / "o.npz").exists()


def test_three_separate_files_with_different_lengths_are_trimmed(tmp_path):
    rng = np.random.default_rng(1)
    paths = []
    for role, n in (("n", 1000), ("e", 990), ("z", 1000)):
        paths.append((_write(tmp_path / f"{role}.txt", "\n".join(f"{v:.5f}" for v in rng.normal(size=n)) + "\n"), role))
    res = import_recording(_req(paths, ascii_cfg={"delimiter": "whitespace", "columns": {"n": 0, "e": 0, "z": 0},
                                                  "time": {"mode": "sample_rate", "sample_rate": 100}}, out=str(tmp_path / "o.npz")))
    assert res["ok"] and res["meta"]["n_samples"] == 990
    codes = {i["code"]: i for i in res["validation"]["issues"]}
    assert "trimmed_to_overlap" in codes and codes["trimmed_to_overlap"]["severity"] == "warning"
    assert codes["trimmed_to_overlap"]["details"]["trimmed"]["n"]["removed_samples"] == 10


def test_missing_component_is_blocking(tmp_path):
    p = _write(tmp_path / "two.csv", "\n".join(f"{i},{i}" for i in range(300)) + "\n")
    res = import_recording(_req([(p, "all")], ascii_cfg={"delimiter": ",", "columns": {"n": 0, "e": 1},
                                                          "time": {"mode": "sample_rate", "sample_rate": 10}}))
    assert not res["ok"] and any(i["code"] == "missing_component" and i["details"].get("component") == "z"
                                 for i in res["validation"]["issues"])


def test_datetime_column_rate_detection_and_gap_rejection(tmp_path):
    import pandas as pd
    t = pd.date_range("2025-02-01T00:00:00Z", periods=3000, freq="20ms")
    rows = [f"{ts.isoformat()},{np.sin(i / 3):.4f},{np.cos(i / 3):.4f},{np.sin(i / 9):.4f}" for i, ts in enumerate(t)]
    p = _write(tmp_path / "dt.csv", "time,n,e,z\n" + "\n".join(rows) + "\n")
    guess = inspect_file(p)["ascii"]["time_column_guess"]
    assert guess["kind"] == "datetime" and guess["sample_rate_estimate"] == 50.0
    cfg = {"delimiter": ",", "header_rows": 1, "columns": {"n": 1, "e": 2, "z": 3}, "time": {"mode": "datetime_column", "column": 0}}
    res = import_recording(_req([(p, "all")], ascii_cfg=cfg, out=str(tmp_path / "o.npz")))
    assert res["ok"] and res["meta"]["fs"] == 50.0 and res["meta"]["start_time"] == "2025-02-01T00:00:00.000000Z"
    # a gap in the middle is rejected, never interpolated
    rows_gap = rows[:1500] + rows[1600:]
    p2 = _write(tmp_path / "gap.csv", "time,n,e,z\n" + "\n".join(rows_gap) + "\n")
    res2 = import_recording(_req([(p2, "all")], ascii_cfg=cfg, out=str(tmp_path / "o2.npz")))
    assert not res2["ok"] and res2["validation"]["issues"][0]["code"] == "gaps"
    # duplicate timestamp
    p3 = _write(tmp_path / "dup.csv", "time,n,e,z\n" + "\n".join(rows[:100] + [rows[99]] + rows[100:]) + "\n")
    res3 = import_recording(_req([(p3, "all")], ascii_cfg=cfg))
    assert not res3["ok"] and any(i["code"] == "duplicate_timestamps" for i in res3["validation"]["issues"])


def _mseed(tmp_path, name="s.mseed", gap=False, shift_samples=0, fs=100.0):
    import obspy
    from obspy import UTCDateTime
    st = obspy.Stream()
    rng = np.random.default_rng(0)
    t0 = UTCDateTime("2025-01-01T00:00:00")
    for ch in ("HHN", "HHE", "HHZ"):
        data = rng.normal(size=6000).astype(np.float32)
        start = t0 + (shift_samples / fs if ch == "HHE" else 0)
        if gap and ch == "HHZ":
            st.append(obspy.Trace(data[:3000], header={"network": "XX", "station": "T", "channel": ch, "sampling_rate": fs, "starttime": start}))
            st.append(obspy.Trace(data[3100:], header={"network": "XX", "station": "T", "channel": ch, "sampling_rate": fs, "starttime": start + 31.0}))
        else:
            st.append(obspy.Trace(data, header={"network": "XX", "station": "T", "channel": ch, "sampling_rate": fs, "starttime": start}))
    p = tmp_path / name
    st.write(str(p), format="MSEED", encoding="FLOAT32")
    return str(p)


def test_mseed_inspect_and_import(tmp_path):
    p = _mseed(tmp_path)
    info = inspect_file(p)
    assert info["format"] == "mseed" and {t["id"] for t in info["mseed"]["traces"]} == {"XX.T..HHN", "XX.T..HHE", "XX.T..HHZ"}
    res = import_recording(_req([(p, "all")], fmt="mseed", mseed={"n": "XX.T..HHN", "e": "XX.T..HHE", "z": "XX.T..HHZ"},
                                out=str(tmp_path / "o.npz"), metadata={"station": "T"}))
    assert res["ok"] and res["meta"]["fs"] == 100.0 and res["meta"]["n_samples"] == 6000
    assert res["meta"]["channels"] == {"n": "HHN", "e": "HHE", "z": "HHZ"} and res["meta"]["network"] == "XX"


def test_mseed_gaps_are_rejected(tmp_path):
    p = _mseed(tmp_path, gap=True)
    info = inspect_file(p)
    z = next(t for t in info["mseed"]["traces"] if t["channel"] == "HHZ")
    assert z["has_gaps"] and z["segments"] == 2
    res = import_recording(_req([(p, "all")], fmt="mseed", mseed={"n": "XX.T..HHN", "e": "XX.T..HHE", "z": "XX.T..HHZ"}))
    assert not res["ok"] and any(i["code"] == "gaps" and i["details"]["component"] == "z" for i in res["validation"]["issues"])


def test_mseed_whole_sample_offset_trimmed_and_subsample_rejected(tmp_path):
    p = _mseed(tmp_path, "a.mseed", shift_samples=5)
    res = import_recording(_req([(p, "all")], fmt="mseed", mseed={"n": "XX.T..HHN", "e": "XX.T..HHE", "z": "XX.T..HHZ"},
                                out=str(tmp_path / "o.npz")))
    assert res["ok"] and res["meta"]["n_samples"] == 5995
    assert any(i["code"] == "trimmed_to_overlap" for i in res["validation"]["issues"])
    assert res["meta"]["start_time"] == "2025-01-01T00:00:00.050000Z"
    p2 = _mseed(tmp_path, "b.mseed", shift_samples=0.4)
    res2 = import_recording(_req([(p2, "all")], fmt="mseed", mseed={"n": "XX.T..HHN", "e": "XX.T..HHE", "z": "XX.T..HHZ"}))
    assert not res2["ok"] and any(i["code"] == "time_misaligned" for i in res2["validation"]["issues"])


def test_mseed_missing_trace(tmp_path):
    p = _mseed(tmp_path)
    res = import_recording(_req([(p, "all")], fmt="mseed", mseed={"n": "XX.T..HHN", "e": "XX.T..HHE", "z": "XX.T..BHZ"}))
    assert not res["ok"] and any(i["code"] == "missing_component" for i in res["validation"]["issues"])


def test_example_files_import(examples_dir, tmp_path):
    res = import_recording(_req([(str(examples_dir / "synthetic_site_A_2p5Hz.txt"), "all")],
                                ascii_cfg={"delimiter": "\t", "header_rows": 1, "comment_prefix": "#",
                                           "columns": {"n": 1, "e": 2, "z": 3}, "time": {"mode": "seconds_column", "column": 0}},
                                out=str(tmp_path / "a.npz"), metadata={"is_synthetic": True}))
    assert res["ok"] and res["meta"]["fs"] == 100.0 and res["meta"]["is_synthetic"]
    res = import_recording(_req([(str(examples_dir / "synthetic_site_E_problems.csv"), "all")],
                                ascii_cfg={"delimiter": ",", "header_rows": 1, "columns": {"n": 1, "e": 2, "z": 3},
                                           "time": {"mode": "datetime_column", "column": 0}}))
    codes = {i["code"] for i in res["validation"]["issues"]}
    assert not res["ok"] and {"nan_values", "clipping_suspected"} <= codes
