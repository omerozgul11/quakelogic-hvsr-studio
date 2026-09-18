# HVSR algorithms in QuakeLogic HVSR Studio

This document describes exactly what the engine (`engine/hvsr_engine`) computes. Every
result file (`result.json`) echoes the parameters and the versions used, so any figure or
number can be traced back to the equations below.

## 1. Data model and what is never done automatically

A recording is three equal-length, equally sampled arrays N, E, Z with a sample rate
f_s and a UTC start time. The importer validates and reports problems; it **never**
interpolates gaps, resamples, rotates, filters or substitutes a missing component. The
only automatic modification is trimming the three components to their common time
overlap when they start at different whole-sample times or have different lengths, and
that is reported as the warning `trimmed_to_overlap`.

The processing toolbox (section 2) is applied only when the user adds steps. Each step
and its effective parameters are stored with the processed data and copied into every
analysis result (`input.processing_steps`).

## 2. Signal-processing toolbox

| Operation | Implementation |
|---|---|
| Mean removal | x − mean(x) |
| Linear detrend | least-squares line removed (`scipy.signal.detrend`) |
| Polynomial baseline | least-squares polynomial of order 1–10 on t ∈ [−1, 1] removed (`numpy.polynomial.Polynomial.fit`) |
| Butterworth filters | high/low/band-pass, band-stop; design in second-order sections (`scipy.signal.butter(..., output="sos")`); zero-phase = forward–backward (`sosfiltfilt`, magnitude squared, no phase shift) or causal (`sosfilt`). Cutoffs must satisfy 0 < f < f_Nyquist; band filters need f_low < f_high. Impossible designs are refused, not silently changed. |
| Notch | `scipy.signal.iirnotch(f₀, Q)` for the line frequency and the requested harmonics below Nyquist, converted to SOS; zero-phase or causal |
| Taper | cosine (Tukey) taper; the percentage is per end (ObsPy convention), α = 2·percent/100 |
| Crop | sample-exact slice; the start time is advanced accordingly |
| Resample | *decimate*: integer factor q, polyphase FIR (Kaiser window) anti-alias low-pass at the new Nyquist frequency, zero-phase (`scipy.signal.resample_poly(x, 1, q)`); *polyphase*: rational factor up/down from `Fraction(target/f_s)` with the same FIR. Up-sampling is allowed but flagged. |
| Rotation | sensor N-axis azimuth α clockwise from true north: N = N′cos α − E′sin α, E = N′sin α + E′cos α (energy preserving; verified by tests) |
| Instrument response | ObsPy `remove_response` with a StationXML inventory matched on network/station/location/channel, or `simulate(paz_remove=…)` with user poles/zeros/gain/sensitivity; output DISP/VEL/ACC, water level and optional pre-filter recorded. No taper is applied automatically; a warning recommends adding a taper step first. |

Warnings (`cutoff_above_nyquist`, `band_inverted`, `edge_effects`, `record_short_for_filter`,
`high_order`, `excessive_processing`, `resample_upsampling`, `resample_not_integer`,
`response_missing`, `polynomial_high_order`) are returned with every preview/run.

## 3. Windows and screening

Windows of length l_w (default 60 s) with overlap o (default 50 %) are cut from the start
of the record; only complete windows are used. Window k covers samples
[k·s, k·s + n_w) with n_w = round(l_w f_s) and s = round(n_w(1 − o)).

**Automatic screening (optional, on by default)**

* STA/LTA anti-trigger: the ratio of the trailing mean of |x| over `sta_s` (2 s) to the
  trailing mean over `lta_s` (30 s), computed for each component. The absolute amplitude
  (not x²) is used as characteristic function because it is far less spiky for
  narrow-band ambient noise. A window is rejected when, on any component, the ratio
  exceeds `max_ratio` (2.5) or falls below `min_ratio` (0.2) anywhere in the window
  (samples where the LTA is not yet defined are ignored).
* Amplitude criterion (off by default): reject when max|x| in the window exceeds
  `max_ratio_to_rms` × RMS of the whole component.
* A window that contains NaN is always rejected (`nan`).

Manual decisions (`window_overrides`) always win over automatic ones and are recorded with
reason `manual`; a NaN window can never be accepted.

### 3a. Window modes (fixed, automatic variable-length, custom)

`params.windows.mode` selects how windows are placed; screening (STA/LTA, amplitude, NaN) and manual
overrides are then applied to every window regardless of the mode.

* **fixed** — equal windows of `length_s` with fractional `overlap`, from the record start (the
  legacy `window_length_s` / `overlap` parameters are aliases and keep working).
* **auto_variable** — a sample is *quiet* when every component is finite, below its level threshold
  (absolute value per component, or `ratio × RMS`) and, when the STA/LTA anti-trigger is enabled, the
  ratio lies inside `[min_ratio, max_ratio]`. Each run of quiet samples is filled greedily with the
  longest possible windows, `min_length_s ≤ L ≤ max_length_s`, without overlap; leftovers shorter than
  `min_length_s` are dropped. This reproduces the "minimum/maximum window length + amplitude levels"
  selection of field software such as GeoExplorer-HVSR.
* **custom** — the user-supplied list `custom = [[start_s, end_s], …]` (windows drawn or repositioned
  by hand, any lengths). Custom windows may also be appended in the other two modes.

Every window carries `length_s` and `color_index` (its position in time order) so the interface
colours windows and their curves consistently.

**Variable window lengths in the analysis.** Each distinct window length gets its own rfft grid and
its own Konno–Ohmachi matrix (§5) onto the common log-spaced output axis, so window curves of
different lengths are directly comparable. Where SESAME uses `l_w · n_w` (criterion R2, §11) the
engine uses `Σ l_i = mean accepted length × n_w`, i.e. the actual number of cycles recorded.

**T10 limit.** SESAME's first reliability criterion, `f0 > 10 / l_w`, is reported as `t10_hz = 10 /
l_w` (with `l_w` the longest window) and drawn on the H/V plot as the frequency below which fewer
than ten cycles fit into a window; curves left of that line are not reliable.

**H/V versus time.** `time_frequency` lists every window's start time and its H/V curve (rejected
windows as null) in time order; drawn as a time × frequency map it shows whether the peak is
stationary during the recording and which windows carry anomalous ratios.

## 4. Spectra

For each accepted window and each component:

1. linear detrend;
2. Tukey taper with `taper_percent` per end (default 5 %);
3. real FFT; Fourier amplitude spectrum |X(f)| · Δt (units: signal units × s). The
   frequency resolution is Δf = 1/l_w. The absolute scaling cancels in the ratio but is
   the same for all three components.

Separately labelled PSD views use Welch's method (`scipy.signal.welch`, density scaling,
units²/Hz) and spectrograms 10·log10 of the short-time PSD.

## 5. Konno–Ohmachi smoothing

Each component amplitude spectrum is smoothed onto a log-spaced output axis of `n_freq`
points between `freq_min` and `freq_max` with the Konno & Ohmachi (1998) window

  W(f, f_c) = [ sin(b·log10(f/f_c)) / (b·log10(f/f_c)) ]⁴ ,  W(f_c, f_c) = 1, W(0, f_c) = 0,

with bandwidth coefficient b (default 40; larger b = narrower window). Weights are
normalised to sum to 1 for every centre frequency, so a flat spectrum is unchanged
(verified to 1e-15). The full window is used (weights below 1e-8 are truncated). The
same smoothing matrix is applied to N, E and Z.

Reference: Konno, K. & Ohmachi, T. (1998). Ground-motion characteristics estimated from
spectral ratio between horizontal and vertical components of microtremor. *Bull. Seismol.
Soc. Am.* 88(1), 228–241.

## 6. Horizontal combination and the per-window ratio

**Combination stage.** By default the horizontals are combined **after** smoothing
(`combination_stage = "after_smoothing"`): with S(·) the smoothed amplitude spectrum,

* geometric mean: H = √( S(|N|) · S(|E|) )
* root-mean-square: H = √( (S(|N|)² + S(|E|)²) / 2 )
* directional: |N|/|Z| = S(|N|)/S(|Z|) and |E|/|Z| = S(|E|)/S(|Z|) are reported
  separately; the main curve of a directional analysis is the geometric mean so every
  result has one main curve.

The per-window HVSR is HV_k(f) = H_k(f) / S(|Z_k|)(f).

The option `combination_stage = "before_smoothing"` combines the raw amplitude spectra
first and smooths the combined horizontal (the hvsrpy / Geopsy-"squared average of raw
spectra" convention). The two differ systematically for noise-like spectra: by Jensen's
inequality E[√(N·E)] < √(E[N]·E[E]) (≈ 0.93 for independent Rayleigh-distributed
amplitudes), so combining before smoothing gives curves that are a few percent lower.
The stage is stored in `method.combination_stage` and never changes silently. See
`docs/validation.md`, cases B1–B3.

## 7. Near-zero vertical masking

For every window, output bins where the smoothed vertical amplitude is below
max(`absolute_floor`, `relative_floor` × max S(|Z_k|) over the analysis band) are
excluded (NaN) for that window. Bins with fewer than `min_valid_windows` valid windows
are invalid in every aggregate curve, reported as `null`, listed in
`masking.invalid_bins` and flagged (`vertical_masked_bins`, `invalid_bins`). Ratios are
never clipped to a ceiling. Defaults: relative 1e-6, absolute 1e-12, min 3 windows.

## 8. Aggregate curves (dispersion bands, not confidence intervals)

Over the accepted windows, per frequency bin (nan-aware):

| `mean_method` | central curve | band |
|---|---|---|
| geometric (default) | exp( mean ln HV ) | exp( mean ln HV ± std(ln HV, ddof = 1) ); σ_ln is also reported |
| arithmetic | mean HV | mean ± std(HV, ddof = 1) |
| median | median HV | 16th–84th percentile of the window curves |

All three are stored; `curves.selected` names the one chosen for display and peak
picking. These bands describe the spread of the window curves. They are **not**
confidence intervals of the mean and are never labelled as such.

## 9. Peaks

Candidates are the local maxima (`scipy.signal.find_peaks`) of the selected mean curve
inside the search range [`search_min`, `search_max`] with prominence ≥ `min_prominence`,
ranked by amplitude. Status:

* `insufficient_data` — fewer accepted windows than `min_valid_windows`; no peak reported;
* `none` — no candidate with amplitude ≥ 2 (the SESAME A₀ > 2 level); candidates are
  still listed;
* `clear` — the top candidate has amplitude ≥ 2 and is alone or ≥ 1.5 × the runner-up;
* `multiple` — two or more candidates of comparable amplitude; the highest is the
  automatic selection and the message asks the user to verify or pick manually.

A manual selection snaps to the nearest curve frequency and is stored with
`source = "manual"`. If the maximum of the curve sits at the search-range edge the flag
`peak_at_search_edge` is raised.

## 10. Peak-frequency variability

* **Window-level distribution.** For each accepted window the highest local maximum of
  its own curve inside the search range gives f₀,k and A₀,k. Reported: n, median, 16th
  and 84th percentiles, sample standard deviation σ_f (ddof = 1; this is SESAME's σ_f)
  and the standard deviation of ln f₀.
* **Bootstrap percentile interval.** The accepted windows are resampled with replacement
  `n_resamples` times (default 200) with `numpy.random.default_rng(seed)`; each resample's
  mean curve is recomputed with the selected method and its peak located. The 2.5th, 50th
  and 97.5th percentiles of the resampled f₀ and A₀ are reported as a *bootstrap
  percentile interval*. The seed is always recorded (a random one is drawn and stored if
  none is given), so the interval is reproducible.

## 11. SESAME (2004) criteria

Implemented from Appendix A of: SESAME (2004). *Guidelines for the implementation of the
H/V spectral ratio technique on ambient vibrations — measurements, processing and
interpretation.* SESAME European research project, WP12 – Deliverable D23.12, European
Commission – Research General Directorate, Project No. EVG1-CT-2000-00026, December 2004.

Notation: f₀ selected peak frequency, A₀ amplitude of the geometric-mean curve at f₀,
l_w window length, n_w number of accepted windows, n_c = l_w·n_w·f₀, σ_A(f) = exp(σ_ln(f))
the multiplicative standard deviation (the factor by which the mean curve is multiplied or
divided), σ_f the standard deviation of the window peak frequencies. All criteria are
evaluated on the geometric (log) mean curve whatever the display mean.

Reliability (all three required):

| | Criterion |
|---|---|
| R1 | f₀ > 10 / l_w |
| R2 | n_c(f₀) = l_w · n_w · f₀ > 200 |
| R3 | σ_A(f) < 2 for 0.5 f₀ < f < 2 f₀ if f₀ > 0.5 Hz; σ_A(f) < 3 in that band if f₀ < 0.5 Hz |

Clear peak (at least 5 of 6 required):

| | Criterion |
|---|---|
| C1 | ∃ f⁻ ∈ [f₀/4, f₀] : A_H/V(f⁻) < A₀/2 |
| C2 | ∃ f⁺ ∈ [f₀, 4f₀] : A_H/V(f⁺) < A₀/2 |
| C3 | A₀ > 2 |
| C4 | f_peak[A_H/V(f) ± σ_A(f)] = f₀ ± 5 % — the peak of the curves mean×σ_A and mean/σ_A (nearest local maximum to f₀ within [f₀/2, 2f₀]) lies within 5 % of f₀ |
| C5 | σ_f < ε(f₀) |
| C6 | σ_A(f₀) < θ(f₀) |

Threshold table (SESAME Table 1):

| f₀ range (Hz) | < 0.2 | 0.2–0.5 | 0.5–1.0 | 1.0–2.0 | > 2.0 |
|---|---|---|---|---|---|
| ε(f₀) | 0.25 f₀ | 0.20 f₀ | 0.15 f₀ | 0.10 f₀ | 0.05 f₀ |
| θ(f₀) for σ_A(f₀) | 3.0 | 2.5 | 2.0 | 1.78 | 1.58 |
| log θ(f₀) for σ_logH/V(f₀) | 0.48 | 0.40 | 0.30 | 0.25 | 0.20 |

Every criterion is reported separately with its value, threshold, pass/fail and a
one-line explanation. The engine does not claim "SESAME compliance"; it reports which
criteria are met.

## 12. Azimuthal analysis (optional)

Using the complex per-window spectra, the horizontal component at azimuth θ (clockwise
from north, 0 ≤ θ < 180°, step `step_deg`) is H_θ(f) = N(f)·cos θ + E(f)·sin θ (rotation
is linear, so this equals the FFT of the rotated time series). |H_θ| is smoothed with the
same matrix, divided by the smoothed vertical (with the same masking) and aggregated with
the selected mean method, giving a matrix azimuth × frequency and the peak per azimuth.

## 13. Quality flags and interpretation notes

`quality_flags` include: `insufficient_windows`, `many_windows_rejected` (> 50 %),
`short_record`, `vertical_masked_bins`, `invalid_bins`, `high_dispersion` (median σ_A in
the search range > 2), `peak_at_search_edge`, `low_frequency_resolution`,
`freq_max_clamped`. Every result also carries `interpretation_notes` stating that the
HVSR amplitude is not a measurement of site amplification and that no unique velocity
profile follows from an HVSR curve alone.

## 14. Reproducibility

`result.json` stores the engine and dependency versions, the complete parameter set
(after defaults), the random seed, the SHA-256 of the input file, the processing steps
that produced it, every window decision and the numerical curves. `exports/config.json`
is sufficient to re-run the analysis; `analyze(rec, config["params"],
random_seed=config["random_seed"])` reproduces the stored result bit-for-bit (tested).

## 15. Synthetic reference model

`hvsr_engine.synthetic.synthetic_recording` shapes independent white noise for N and E
with the absolute transmissibility of a damped 1-DOF oscillator,

  H(f) = (1 + 2iξr) / (1 − r² + 2iξr), r = f/f₀, |H(f₀)| = √(1 + 4ξ²) / (2ξ),

and uses independent white noise of the same variance for Z, so the expected HVSR is
|H(f)|. For a requested A₀ the damping is ξ = 1 / (2√(A₀² − 1)). The example files in
`examples/` are produced this way and are labelled synthetic in their headers, in
`meta.is_synthetic` and in every report.

## 16. Display down-sampling

Waveforms sent to the browser are reduced with a min/max envelope per pixel bucket and
the response states `downsampled`, the number of source samples and the number shown.
All analyses use the full-resolution data.

## 17. Forward modelling of the H/V curve (1-D ground model)

`hvsr_engine.modelling.model_hvsr` computes a synthetic H/V curve for a stack of horizontal layers
over a half-space following Herak (2008): the curve is approximated by the ratio of the SH- and
P-wave transfer functions for vertically incident body waves,

    HVSR_model(f) = |T_SH(f)| / |T_P(f)|,

where each transfer function is the surface-to-outcrop amplification of the Thomson–Haskell
propagator with complex, anelastic velocities `v* = v (1 + i / (2Q))` (recursion over the layers with
impedance ratios `ρ_j v*_j / ρ_{j+1} v*_{j+1}`; for the free surface `A₁ = B₁ = 1` and `T = 1 / A_N`).
For one layer over a half-space `|T_SH|` peaks at `f ≈ Vs / (4H)`. Poisson's ratio is completed from
`Vp/Vs` (`ν = (r² − 2) / (2(r² − 1))`) or `Vp` from `ν` (`Vp = Vs √((2 − 2ν)/(1 − 2ν))`).

`Vs30 = 30 / Σ(h_i / Vs_i)` over the 30 m below an optional offset; `VsEq = H / Σ(h_i / Vs_i)` down to
the top of the half-space when that depth `H < 30 m`, otherwise `VsEq = Vs30`.

This is a **forward** model only. A profile whose synthetic curve resembles the measured one is not
unique (many profiles give the same curve), the measured ambient-vibration H/V also contains
surface-wave energy, and the H/V level is not site amplification. The engine reports these notes
with every model result.

Reference: Herak, M. (2008). ModelHVSR — a Matlab tool to model horizontal-to-vertical spectral
ratio of ambient noise. *Computers & Geosciences* 34(11), 1514–1526.

## 18. Curve files and additional input formats

* `exports/hvsr_mean.hv` is a Geopsy-compatible `.hv` file (`#` header, then
  `frequency average min max`; min/max are the dispersion band, not a confidence interval).
  `read_curve_file` reads `.hv` files and 2–4 column tables for comparison with external curves.
* Input formats: delimited ASCII, SESAME ASCII format (`.saf`: `KEY = value` header with
  `SAMP_FREQ`, `NDAT`, `START_TIME`, `CH0_ID..CH2_ID`, then three columns V N E), and every
  ObsPy-readable seismic format (MiniSEED, GSE2, SEG-2, SAC, …) reported as `seismic`.
