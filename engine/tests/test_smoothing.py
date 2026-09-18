import numpy as np

from hvsr_engine.smoothing import konno_ohmachi_matrix, konno_ohmachi_weights, log_frequency_axis, smooth


def test_rows_normalised_and_flat_spectrum_unchanged():
    f_in = np.fft.rfftfreq(6000, d=0.01)
    f_out = log_frequency_axis(0.2, 30, 100)
    m = konno_ohmachi_matrix(f_in, f_out, 40)
    assert m.shape == (100, len(f_in))
    np.testing.assert_allclose(m.sum(axis=1), 1.0, atol=1e-12)
    flat = np.full(len(f_in), 3.7)
    np.testing.assert_allclose(smooth(flat, m), 3.7, rtol=1e-12)
    assert np.all(m[:, 0] == 0)  # DC bin excluded


def test_weight_is_one_at_centre_and_symmetric_in_log_frequency():
    f_in = np.array([0.5, 1.0, 2.0])
    w = konno_ohmachi_weights(f_in, 1.0, 40)
    assert np.argmax(w) == 1
    assert np.isclose(w[0], w[2])


def test_bandwidth_controls_width():
    f_in = np.linspace(0.01, 50, 5000)
    f_out = np.array([5.0])
    wide = konno_ohmachi_matrix(f_in, f_out, 10)[0]
    narrow = konno_ohmachi_matrix(f_in, f_out, 80)[0]
    # effective support (bins with >1% of max weight) is wider for smaller b
    assert (wide > 0.01 * wide.max()).sum() > (narrow > 0.01 * narrow.max()).sum()


def test_matrix_smoothing_of_many_windows_matches_loop():
    f_in = np.fft.rfftfreq(2000, d=0.01)
    f_out = log_frequency_axis(0.5, 40, 50)
    m = konno_ohmachi_matrix(f_in, f_out, 40)
    spectra = np.random.default_rng(0).random((5, len(f_in)))
    batch = smooth(spectra, m)
    for i in range(5):
        np.testing.assert_allclose(batch[i], smooth(spectra[i], m))


def test_peak_is_preserved_in_position():
    f_in = np.fft.rfftfreq(6000, d=0.01)
    f_out = log_frequency_axis(0.5, 20, 400)
    spec = 1 + 5 * np.exp(-0.5 * ((f_in - 3.0) / 0.2) ** 2)
    sm = smooth(spec, konno_ohmachi_matrix(f_in, f_out, 40))
    assert abs(f_out[np.argmax(sm)] - 3.0) < 0.1
