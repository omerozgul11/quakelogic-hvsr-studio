# QuakeLogic HVSR Studio — User Guide

QuakeLogic HVSR Studio is a standalone, offline application for horizontal-to-vertical spectral
ratio (HVSR) analysis of three-component ambient-vibration recordings. It runs entirely on your
computer: no account, no license key, no internet connection. Everything you import, process and
export stays in a project folder on your disk.

Contents

1. Installation
2. Starting and stopping
3. The workspace
4. Projects
5. Import and validation
6. Waveforms and preprocessing
7. Window selection
8. HVSR analysis
9. Batch processing and comparison
10. Reports and exports
11. Settings
12. Where your data lives, backups and reproducibility
13. Troubleshooting
14. Scientific limitations you should keep in mind

---

## 1. Installation

### Windows (recommended)

1. Run `QuakeLogic-HVSR-Studio-<version>-setup-win-x64.exe`. The installer is per-user (no
   administrator rights needed) and installs into
   `%LocalAppData%\Programs\QuakeLogic HVSR Studio`. If the Microsoft Visual C++ runtime is missing
   it is installed silently.
2. Alternatively unzip `QuakeLogic-HVSR-Studio-<version>-win-x64.zip` anywhere (USB stick,
   network share, `C:\Tools\...`) — the application is fully portable.

The distribution bundles its own PHP and Python runtimes; nothing else needs to be installed.

### macOS and Linux (from source)

Requirements: `bash`, `curl`, `tar`. Run

```
scripts/setup-dev.sh
```

once. It downloads a private toolchain into `.tools/` and `runtime/` (static PHP, Composer, Node,
`uv` + Python 3.12), installs all pinned dependencies, builds the interface and prepares the
database. Internet access is needed only for this step.

### Windows from source (developers)

Install PHP 8.4 CLI, Composer, Node.js 22+ and Python 3.12, then run `scripts\setup-dev.ps1`.

## 2. Starting and stopping

* **Windows:** Start menu → *QuakeLogic HVSR Studio*, or double-click `HVSR Studio.vbs`
  (`HVSR Studio.bat` does the same but keeps a console window open, useful for troubleshooting).
* **Linux:** `launcher/hvsr-studio.sh` — **macOS:** double-click `launcher/hvsr-studio.command`.

The application opens in its **own window** (no browser tabs or address bar) with the QuakeLogic
icon; it uses the Chromium engine of Microsoft Edge, which is part of Windows 10/11 (Chrome or
Chromium on macOS/Linux). **Closing that window stops the application.** If no such browser is
installed, the interface opens in your default web browser instead and the launcher window must
be closed to stop the application. Start with `--browser` to force the browser mode. If the
application is already running, starting it again simply opens another window.

Both services listen on `127.0.0.1` only — other computers on your network cannot reach them.
If port 8090 or 8765 is busy, the launcher picks the next free port and prints the address.

Launcher options: `--no-browser`, `--port N`, `--engine-port N`, `--debug` (echo service logs to
the console), `--workers N` (parallel analysis threads; default half the CPU cores).

## 3. The workspace

```
┌───────────────────────────────────────────────────────────────────────┐
│ QuakeLogic HVSR Studio  /  <project>          [Engine ready] [☾] [⚙]  │
├───────────────┬──────────────────────────────────┬────────────────────┤
│ Sections      │                                  │ Processing panel   │
│  Projects     │      Plotting workspace          │ (context-dependent:│
│  Import       │      (Plotly, zoom/pan/export)   │  toolbox, window   │
│  Waveforms    │                                  │  or HVSR settings) │
│  Windows      │                                  │                    │
│  HVSR         │                                  │                    │
│  Batch        │                                  │                    │
│  Reports      │                                  │                    │
│  Settings     │                                  │                    │
│ ───────────── │                                  │                    │
│ Project tree  │                                  │                    │
│  stations →   │                                  │                    │
│  recordings → │                                  │                    │
│  runs, analyses                                  │                    │
└───────────────┴──────────────────────────────────┴────────────────────┘
```

* The **navigator** (left) lists the sections and the tree of the open project. Drag its right
  edge to resize it; the ▤ button collapses it.
* The **workspace** (centre) holds the plots and tables of the current page.
* The **processing panel** (right) holds the settings for the current page; it can be collapsed
  or resized. All numeric fields show units and a short explanation.
* The **top bar** shows the QuakeLogic logo, the engine status (green = ready), the **?** button
  that opens the *Guided workflow*, the theme switch (light / dark / system) and a link to Settings.
* **User manual** (left navigator) opens this guide inside the application, together with the
  algorithm description, the validation report and the third-party notices — all offline, with a
  searchable table of contents.
* The **Guided workflow** is a step-by-step wizard (8 steps: project → import → waveforms →
  windows → HVSR → review → report → batch). It shows which steps are already done in the open
  project, explains each one, and its *Open* button takes you to the right page. It opens
  automatically the first time the application is used; tick *Don't open automatically* to stop
  that, and reopen it any time with the **?** button or from the *User manual* page.
* Long computations run in the processing engine; a progress strip appears at the bottom with a
  **Cancel** button. The interface stays responsive while jobs run.
* Every plot has a toolbar (zoom, pan, reset, hover values) and an **Export** menu (PNG, SVG;
  PDF for analysis plots).

## 4. Projects

A project is a folder that holds stations, recordings, processing runs, analyses, exports and
reports. Create one from the *Projects* page (name + optional description). Opening a project
loads its tree into the navigator. Rename or delete projects from the card menu; deleting a project
removes its folder and all its files after a confirmation.

Stations (site code, name, coordinates, elevation, sensor N-axis azimuth, notes) are managed on
the project overview page. Recordings can be assigned to a station during import or later.

## 5. Import and validation

Open *Import & validation* (or **Import recordings** on the project page). The wizard has four
steps.

**1 · Files.** Drop files on the drop zone or click *browse*; several files at once are fine. Each
file is staged, hashed (SHA-256) and inspected: the format (delimited ASCII or MiniSEED), the
delimiter, decimal mark, header rows, comment prefix, the columns and a possible time column are
detected. MiniSEED files list their traces (network, station, channel, start, rate, samples,
gaps).

**2 · Preview** (ASCII only). The raw first lines and the parsed table are shown side by side.
Correct the delimiter (comma, tab, semicolon, whitespace, …), decimal mark (`.` or `,`), number
of header rows and comment prefix until the parsed table looks right.

**3 · Mapping.** Choose the layout:

* *One file with all components* — pick the file, then the **N**, **E** and **Z** columns (or the
  three MiniSEED traces).
* *Three separate files* — pick one file per component and the column inside each.

Then set the timing:

* *Constant sampling rate* — you must type the sampling rate (Hz); the record has no time column.
* *Time column in seconds* — the sampling rate is derived from the column and checked for
  regularity and duplicates.
* *Time column with date/time* — ISO-8601 or common formats; the start time comes from the data.

For MiniSEED the timing comes from the headers and is cross-checked between traces.
Give the recording a name, choose or create a station, set units (raw counts, velocity,
acceleration, displacement + a unit label), an optional scale factor, the sensor orientation
(N-axis azimuth clockwise from true north; 0 = aligned) and tick *synthetic* for test data.

**The wizard refuses to continue when timing is missing** — HVSR Studio never guesses a sampling
rate.

**4 · Validate & create.** The engine parses the files and checks: component overlap and time
alignment (sub-sample misalignment is an error; a whole-sample offset or different lengths lead
to trimming to the common overlap, which is reported), sampling-rate mismatch, gaps and overlaps
(MiniSEED segments), duplicate or irregular time stamps, NaN/Inf samples, constant-value
channels, suspected clipping, unknown units and short records. Errors block the import and are
listed with an explanation; warnings and infos are stored with the recording and shown on the
project page. **Nothing is interpolated, resampled, rotated or substituted.** The staged files
stay available after a blocked import so you can fix the mapping and try again.

On success the source files are copied into the project folder, a canonical copy of the traces is
written, and the waveform page opens.

## 6. Waveforms and preprocessing

The page shows the three components on a shared time axis. Zoom or pan and the plot re-fetches
the visible range at display resolution; a note tells you when a min/max envelope is shown
("displayed at reduced resolution, n of N samples"). Analyses always use the full-resolution
data.

The **processing toolbox** (right panel) builds an ordered list of steps. Add steps from the
menu, enable/disable, move up/down, edit parameters and **Reset**. Available steps:

| Step | Parameters | Notes |
|---|---|---|
| Mean removal | – | subtracts the mean of each component |
| Linear detrend | – | least-squares line removed |
| Polynomial baseline | order 1–10 | least-squares polynomial removed; high orders warn |
| Butterworth filter | high-/low-/band-pass, band-stop; cutoffs; order; causal or zero-phase | SOS implementation; zero-phase = forward–backward (doubled order, no phase distortion); cutoffs are checked against the Nyquist frequency |
| Notch | frequency, Q, number of harmonics, causal/zero-phase | power-line interference (50/60 Hz and harmonics below Nyquist) |
| Taper | percent per side | cosine (Tukey) taper |
| Crop | start, end (s) | keeps the selected range |
| Resample | target rate, method | *decimate* = anti-aliased integer-factor FIR; *polyphase* = rational resampling with FIR anti-alias; up-sampling warns |
| Rotate horizontals | sensor N azimuth | rotates N/E to true north/east; stored in the metadata |
| Remove instrument response | StationXML file or manual poles/zeros; output VEL/ACC/DISP; water level; optional pre-filter | needs metadata matching the recording's network/station/channel codes; refuses otherwise |

With *Preview automatically* on, every change is applied in memory and the processed traces are
overlaid on the raw ones (toggle *Raw* / *Processed*). When a filter or notch step is selected,
its frequency response is drawn (dotted line: −3 dB). Warnings appear for cutoffs at or above
Nyquist, inverted bands, very high orders, edge effects on short records, up-sampling and
excessive processing (many steps or several filters). Nothing is applied automatically — the raw
recording is analysed as-is unless you add steps.

**Run & save** stores the processed traces as a named *processing run* together with the exact
steps and effective parameters. Runs appear under the recording in the tree and can be chosen as
the source for windows and analyses. The **save** icon next to *Load preset* stores the current
steps (and HVSR parameters) as a preset for reuse and batch processing.

Below the waveforms, three spectral views are available for the raw recording or a run:
**Amplitude spectra (FAS)** — mean Fourier amplitude spectrum per component over windows, with
optional Konno–Ohmachi smoothing; **Power spectral density** — Welch PSD in counts²/Hz (labelled
separately, never mixed with amplitude spectra); **Spectrograms** — time–frequency maps (dB) per
component.

## 7. Window selection

Choose the source (raw recording or a run), the **window length** (s) and **overlap** (fraction).
The frequency resolution 1/T is shown. Transient screening can be switched on:

* **STA/LTA anti-trigger** — the ratio of a short-term to a long-term average of the absolute
  signal is computed on every component; a window is rejected when the ratio leaves the
  `[min, max]` band anywhere inside it (Geopsy-style anti-trigger). Defaults: STA 2 s, LTA 30 s,
  min 0.2, max 2.5.
* **Amplitude criterion** — rejects windows whose peak absolute amplitude exceeds *k* × the RMS of
  the whole component.

**Compute windows** draws every window on the waveforms (green = accepted, red = rejected) and
lists them with reasons and STA/LTA statistics. Click a window in the plot or use *Reject* /
*Accept* in the table to override the automatic decision; overrides are kept when parameters
change and are stored with the analysis (reason *manual*). Windows containing NaN are always
rejected. **Continue to HVSR analysis** carries the window settings and overrides forward.

## 8. HVSR analysis

The right panel holds every parameter with a short explanation; sensible defaults are preloaded
and presets can be applied.

| Group | Parameters | Meaning |
|---|---|---|
| Windows | length, overlap, screening | as in Window selection |
| Spectra & smoothing | per-window detrend, taper per side, smoothing type, Konno–Ohmachi bandwidth *b* (default 40), frequency range, number of frequencies | each window is detrended, tapered and transformed; every component is smoothed identically onto a log-spaced axis |
| Horizontal combination | geometric mean √(|N|·|E|), RMS √((|N|²+|E|²)/2), or directional (|N|/|Z| and |E|/|Z| in addition to the geometric-mean curve); combination stage (advanced, default *after smoothing*) | documented in `docs/hvsr-algorithms.md` |
| Statistic | geometric (log) mean, arithmetic mean or median | all three are computed; the choice sets the displayed curve and the peak search |
| Peak search | range, minimum prominence | only local maxima inside the range are candidates |
| Vertical floor (advanced) | relative and absolute floor | bins with a near-zero smoothed vertical spectrum are masked (set to invalid), never clipped |
| Minimum valid windows | n | frequency bins with fewer valid windows are flagged invalid |
| Bootstrap | on/off, resamples | resamples accepted windows to estimate a percentile interval of the peak; the random seed is stored |
| Azimuthal | on/off, step (°) | H/V for a single rotated horizontal component from 0° to 180° |
| SESAME criteria | on/off | evaluates the SESAME (2004) reliability and clear-peak criteria |
| Random seed | blank = generated | recorded in the result for reproducibility |

**Run analysis** submits a job; progress is shown in the job strip. When it finishes, the result
page shows:

* Summary cards — selected f0, amplitude A0 (explicitly "H/V ratio, not site amplification"),
  peak status (*clear*, *multiple*, *none* = no clear peak, *insufficient data*), window counts,
  window-level f0 spread (16–84 %) and the SESAME verdict.
* **H/V curve** — the chosen mean curve with its dispersion band (the band definition is printed
  in the legend and under the plot; it is the log-normal ±1σ, arithmetic ±1σ or 16–84 % band and
  is *not* a confidence interval), faint individual window curves (toggle), candidate peaks,
  the selected peak with an annotation and the shaded search range. Click the curve to propose a
  manual peak.
* **Component spectra**, **Peak distribution** (histogram of window peak frequencies with median,
  16/84 % and the bootstrap interval), **Azimuthal** heat map (azimuth × frequency, when enabled),
  **Windows** (accepted / rejected list) and **SESAME** (every criterion with value, threshold and
  pass/fail, plus the citation).
* Candidate-peak table with **Select** buttons and a manual frequency field; *Back to automatic*
  restores the automatic selection. The selection source (automatic / manual) is stored.
* Quality flags (e.g. many rejected windows, masked bins, peak at the search-range edge, high
  dispersion), masking details and the interpretation notes.
* Reproducibility card: engine version, seed, computation time, and **Re-run** which repeats the
  analysis with the stored parameters and seed.

**Re-run with new parameters** (right panel) creates a new analysis from the same source with the
edited settings, keeping the previous one.

## 9. Batch processing and comparison

*Batch comparison* → **Batch runner**: choose a preset (its processing steps are optional — tick
*Apply the preset's processing steps first* to create a run before each analysis), select
recordings and press **Run batch**. The queue shows every item with status, progress and error;
a failed file is recorded and skipped, the rest continues. **Cancel** stops the remaining items.

**Select analyses to compare** lists the finished analyses by station; tick two or more and press
**Compare** to overlay their mean curves (optionally with bands). The table below lists f0, A0 and
peak status for each.

## 10. Reports and exports

From an analysis (Export menu) or the *Reports & exports* page:

| Export | Content |
|---|---|
| HVSR curves CSV | frequency, mean curve, lower/upper band, all three statistics, per-window columns |
| Windows CSV | window table (times, accepted, reason, STA/LTA, f0/A0 per window) |
| Component spectra CSV | mean smoothed N, E, Z and H amplitude spectra |
| Summary CSV / JSON | peak, statistics, SESAME results, flags, versions, seed |
| Configuration JSON | every parameter needed to reproduce the analysis |
| Azimuthal CSV | azimuth × frequency matrix (when enabled) |
| Figures | PNG / SVG from the plot toolbar; PNG / SVG / PDF rendered by the engine |
| **PDF report** | station and recording metadata, source files with checksums, processing steps, HVSR parameters, window statistics, figures, peak table and variability definitions, SESAME table, quality flags, interpretation limitations and reproducibility data |

All exports are produced locally in the analysis folder (`exports/`) and downloaded through the
browser.

## 11. Settings

Theme, default preset, and read-only information: data directory, engine address, engine and
library versions, application version, third-party notices.

## 12. Where your data lives, backups and reproducibility

```
<data dir>/hvsr-studio.sqlite            the project database
<data dir>/projects/<project>/
    sources/<recording>/...              your original files (unchanged, SHA-256 recorded)
    traces/<recording>.npz               canonical parsed copy
    runs/<run>/processed.npz, steps.json processed traces + the exact steps applied
    analyses/<analysis>/result.json      full result (parameters, curves, peaks, SESAME, seed, versions)
    analyses/<analysis>/curves.npz       per-window curves
    analyses/<analysis>/exports/         CSV / JSON / figures
    analyses/<analysis>/report.pdf
<data dir>/logs/                          launcher, engine and web-server logs
```

The data directory is `data/` next to the application (portable install) or
`%LocalAppData%\QuakeLogic\HVSR Studio\data` when the application folder is read-only. Back up
the whole data directory. Every analysis stores its parameters, accepted windows, random seed and
software versions; *Re-run* reproduces it, and `config.json` can be applied to other recordings.

## 13. Troubleshooting

| Symptom | What to do |
|---|---|
| "Processing engine is not running" banner | the Python service stopped; close and restart the launcher; read `data/logs/engine.log` |
| Browser shows nothing at 127.0.0.1:8090 | the launcher window prints the actual port; check `data/logs/web.log` |
| Upload fails or hangs on a large file | files up to 4 GB are accepted; disk space is required for the copy + canonical traces |
| Import blocked | the listed errors must be fixed in the source data or the mapping; HVSR Studio never repairs data silently |
| Analysis says *insufficient data* | fewer accepted windows than *minimum valid windows*; relax screening, accept windows manually, use shorter windows or a longer record |
| Many masked frequency bins | the vertical spectrum is near zero there (synthetic data, dead channel, over-filtering); check the component spectra |
| Ports 8090/8765 in use | the launcher moves to the next free port; or pass `--port` / `--engine-port` |
| Read-only installation folder | the launcher stores settings, database and projects under the per-user data folder automatically |

Console diagnostics: `php artisan hvsr:doctor` (from the application folder using the bundled PHP:
`runtime\win-x64\php\php.exe artisan hvsr:doctor`).

## 14. Scientific limitations you should keep in mind

* The H/V amplitude is a spectral ratio; it is **not** a direct measurement of site amplification.
* An H/V peak frequency does **not** determine a unique shear-wave velocity profile; inversion
  requires additional constraints and is outside the scope of this software.
* Dispersion bands describe the scatter of the window curves; only the bootstrap interval is an
  interval estimate, and it depends on the resampling assumptions stated in the result.
* The SESAME (2004) criteria are evaluated exactly as published and reported one by one; passing
  them supports, but does not prove, the presence of a resonance.
* Results depend on the processing chain (filters, windows, smoothing). Everything is recorded so
  that a reader can judge and repeat the analysis. See `docs/hvsr-algorithms.md` for the exact
  definitions.

All example files shipped in `examples/` are **synthetic** (generated by
`engine/validation/make_examples.py` with the parameters in `examples/README.md`); they are not
field measurements.

## 15. QLExplorer-style tools (added)

* **Window modes** (Window selection → panel): *Fixed* (length + overlap), *Automatic* (variable
  length between a minimum and a maximum, packed into the quiet parts of the record using amplitude
  levels and/or the STA/LTA anti-trigger) and *Custom* (draw windows on the plot with a box selection,
  edit start/end in the table, load a saved window set). Windows are colour-coded by time (rainbow);
  the same colours are used for the single-window H/V curves and the H/V-vs-time colour strip. T10
  = 10 / longest window is the SESAME reliability limit shown on the plots.
* **Seismogram player** (Waveforms and Window selection): listen to a channel at a chosen playback
  frequency, add *bookmarks* at suspicious sounds (key **B**), then *Reject bookmarked windows*.
* **H/V results view**: window table (colour, length, use), Select all / Invert / Clear, box-select
  curves on the plot to toggle windows and re-run, options for the mean, standard-deviation band or
  curves, T10, single ratios, a loaded external curve (Geopsy `.hv` or CSV), absolute H and V
  spectra in dB on the right axis, manual scales and log/linear frequency; SESAME boxes
  (Curve I–III, Peak I–VI, Overall) beside the plot.
* **H/V vs time**: H/V level of every accepted window against clock time (stationarity check).
  **H/V rotate**: azimuthal H/V heat map with colour-scale controls.
* **Modelling**: a layered ground model (thickness, Vp, Vs, Poisson, density, Q) produces a
  synthetic H/V curve (Herak 2008 body-wave transfer-function ratio) to compare with the measured
  curve, with Vs30, VsEq, model f0 and a misfit; the Vp/Vs depth profile can be shown. A model that
  fits is never unique — this is a comparison tool, not an inversion.
* **Report details**: survey date, client, place, address, coordinates/datum, elevation, weather,
  notes and two photos are stored with the analysis and printed in the PDF report.
* **Files**: import SESAME ASCII (`.saf`), GSE2 (`.gse`), SEG-2 (`.seg`, `.sg2`) and SAC in
  addition to TXT/CSV/MiniSEED; export the mean curve as Geopsy `.hv`; save/load window sets;
  **Backup** a project to a zip and **Restore** it on the Projects page.
