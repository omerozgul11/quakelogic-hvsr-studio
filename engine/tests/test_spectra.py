import numpy as np

from hvsr_engine.spectra import compute_spectra, fourier_amplitude, tukey_taper
from hvsr_engine.synthetic import synthetic_recording


def test_fourier_amplitude_scaling_for_sinusoid():
    fs, n = 100.0, 10000
    t = np.arange(n) / fs
    x = 2.0 * np.sin(2 * np.pi * 5.0 * t)
    f, amp = fourier_amplitude(x, fs)
    # |X(f)|·dt for a sinusoid of amplitude A over duration T has a peak A·T/2
    assert abs(f[np.argmax(amp)] - 5.0) < 1e-6
    assert abs(amp.max() - 2.0 * (n / fs) / 2) / (2.0 * (n / fs) / 2) < 1e-3


def test_tukey_taper_per_side_percent():
    w = tukey_taper(1000, 5.0)
    assert w[0] == 0 and w[-1] == 0
    assert np.all(w[50:950] == 1.0)


def test_fas_psd_spectrogram_shapes(short_rec):
    fas = compute_spectra(short_rec, {"kind": "fas", "window_length_s": 30, "freq_min": 0.5, "freq_max": 30, "n_freq": 80})
    assert len(fas["frequency"]) == 80 and set(fas["components"]) == {"n", "e", "z"}
    assert fas["units"] == "counts*s"
    psd = compute_spectra(short_rec, {"kind": "psd", "window_length_s": 30, "freq_min": 0.5, "freq_max": 30})
    assert psd["units"] == "counts^2/Hz" and len(psd["frequency"]) == len(psd["components"]["z"])
    sg = compute_spectra(short_rec, {"kind": "spectrogram", "segment_length_s": 10, "components": ["z"]})
    z = sg["components"]["z"]
    assert len(z["db"]) == len(z["f"]) and len(z["db"][0]) == len(z["t"])


def test_fas_horizontal_exceeds_vertical_near_resonance():
    rec = synthetic_recording(fs=100, duration_s=600, f0=2.5, amplification=5, seed=5)
    fas = compute_spectra(rec, {"kind": "fas", "window_length_s": 60, "freq_min": 0.5, "freq_max": 20, "n_freq": 100})
    f = np.array(fas["frequency"])
    ratio = np.array(fas["components"]["n"]) / np.array(fas["components"]["z"])
    assert ratio[np.argmin(np.abs(f - 2.5))] > 3.0
    assert ratio[np.argmin(np.abs(f - 15.0))] < 0.5
