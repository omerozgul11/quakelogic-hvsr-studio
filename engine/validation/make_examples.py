"""Generate the SYNTHETIC example datasets shipped in examples/ (deterministic seeds).

Run:  engine/.venv/bin/python engine/validation/make_examples.py [output_dir]
Every file produced here is synthetic (see hvsr_engine.synthetic). None is a field measurement.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hvsr_engine.synthetic import synthetic_recording  # noqa: E402

FS = 100.0
DURATION = 1200.0  # 20 minutes


def write_txt_tab(rec, path: Path, label: str):
    t = rec.times()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# SYNTHETIC ambient-noise recording ({label}) — QuakeLogic HVSR Studio example, NOT field data\n")
        fh.write(f"# model: 1-DOF resonant amplification, f0 = {rec.meta['synthetic_model']['f0']} Hz, "
                 f"A0 = {rec.meta['synthetic_model']['amplification']:.2f}, damping = {rec.meta['synthetic_model']['damping']:.4f}\n")
        fh.write(f"# sample_rate = {rec.fs:g} Hz, start = {rec.start_time}, units = counts\n")
        fh.write("time_s\tnorth\teast\tvertical\n")
        for i in range(rec.n_samples):
            fh.write(f"{t[i]:.2f}\t{rec.n[i]:.4f}\t{rec.e[i]:.4f}\t{rec.z[i]:.4f}\n")


def write_csv_datetime(rec, path: Path, label: str, inject_problems: bool = False):
    start = datetime(2025, 3, 14, 9, 30, 0, tzinfo=timezone.utc)
    n, e, z = rec.n.copy(), rec.e.copy(), rec.z.copy()
    if inject_problems:
        n[30000:30025] = np.nan                       # 0.25 s of NaN in N
        lim = 0.55 * np.max(np.abs(e))
        e = np.clip(e, -lim, lim)                     # E clipped at ±55 % of its true range (digitiser saturation)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("timestamp_utc,N_counts,E_counts,Z_counts\n")
        for i in range(rec.n_samples):
            ts = (start + timedelta(seconds=i / rec.fs)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            def f(v):
                return "" if np.isnan(v) else f"{v:.4f}"
            fh.write(f"{ts},{f(n[i])},{f(e[i])},{f(z[i])}\n")


def write_split(rec, base: Path):
    for comp, arr in (("N", rec.n), ("E", rec.e), ("Z", rec.z)):
        with open(base.parent / f"{base.name}_{comp}.txt", "w", encoding="utf-8") as fh:
            fh.write(f"# SYNTHETIC single-component file ({comp}); no time column — the sample rate must be entered on import (100 Hz)\n")
            for v in arr:
                fh.write(f"{v:.4f}\n")


def write_mseed(rec, path: Path):
    import obspy
    from obspy import UTCDateTime
    st = obspy.Stream()
    for comp, arr in (("HHN", rec.n), ("HHE", rec.e), ("HHZ", rec.z)):
        tr = obspy.Trace(np.asarray(arr, dtype=np.float32), header={
            "network": "XX", "station": "SYNC", "location": "", "channel": comp,
            "sampling_rate": rec.fs, "starttime": UTCDateTime(rec.start_time)})
        st.append(tr)
    st.write(str(path), format="MSEED", encoding="FLOAT32", reclen=4096)


def main(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    a = synthetic_recording(FS, DURATION, f0=2.5, amplification=5.0, seed=101, station="SYNA")
    write_txt_tab(a, out_dir / "synthetic_site_A_2p5Hz.txt", "site A, f0 = 2.5 Hz")
    b = synthetic_recording(FS, DURATION, f0=0.8, amplification=4.0, seed=202, station="SYNB",
                            transients=[{"time_s": 300, "amplitude": 12, "duration_s": 3}, {"time_s": 815, "amplitude": 20, "duration_s": 2}])
    write_csv_datetime(b, out_dir / "synthetic_site_B_0p8Hz.csv", "site B, f0 = 0.8 Hz, two transients")
    c = synthetic_recording(FS, DURATION, f0=5.0, amplification=3.0, seed=303, station="SYNC")
    write_mseed(c, out_dir / "synthetic_site_C_5Hz.mseed")
    d = synthetic_recording(FS, DURATION, f0=1.5, amplification=6.0, seed=404, station="SYND", horizontal_ratio_ne=1.6)
    write_split(d, out_dir / "synthetic_site_D_split")
    e = synthetic_recording(FS, DURATION, f0=3.0, amplification=4.0, seed=505, station="SYNE")
    write_csv_datetime(e, out_dir / "synthetic_site_E_problems.csv", "site E with NaN + clipping", inject_problems=True)
    print("wrote examples to", out_dir)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "examples")
