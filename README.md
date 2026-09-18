# QuakeLogic HVSR Studio

Standalone, offline desktop application for horizontal-to-vertical spectral ratio (HVSR)
analysis of three-component ambient-vibration recordings.

* **Import** TXT / CSV / MiniSEED (single multicolumn files, three separate component files,
  multi-trace MiniSEED) through a wizard with delimiter detection, column mapping, explicit
  N / E / Z assignment and strict validation (gaps, NaNs, clipping, sample-rate and alignment
  checks). Nothing is interpolated, resampled, rotated or substituted silently.
* **Preprocess** with a recorded, reorderable toolbox: mean removal, detrending, polynomial
  baseline, Butterworth filters (causal / zero-phase), notch, taper, crop, anti-aliased
  resampling, horizontal rotation, instrument-response removal — with filter-response plots
  and warnings.
* **Analyse** with a transparent HVSR engine: configurable windows and overlap, STA/LTA and
  amplitude screening, manual window acceptance, Konno–Ohmachi smoothing, geometric-mean /
  RMS / directional horizontal combination, arithmetic / median / geometric aggregation with
  explicitly defined dispersion bands, candidate peaks, manual peak selection, window-level
  peak variability with a seeded bootstrap interval, the SESAME (2004) reliability and
  clarity criteria reported one by one, and optional azimuthal HVSR.
* **Compare** stations or runs, process batches with saved presets, and **export** CSV / JSON
  / PNG / SVG / PDF plus a professional PDF report — all offline.

No account, login, license key, activation or cloud connection. Binds to 127.0.0.1 only.

## Download (Windows)

Ready-made builds are published on the GitHub **Releases** page of this repository: the
`…-setup-win-x64.exe` installer (recommended) or the portable `…-win-x64.zip`. Both are produced
automatically by the `Windows release` workflow from a version tag.

## Quick start (Windows)

1. Run the installer `QuakeLogic-HVSR-Studio-<version>-setup-win-x64.exe` (or unzip the
   portable zip anywhere).
2. Start **QuakeLogic HVSR Studio** from the Start menu (or double-click `HVSR Studio.vbs`).
   The application opens in its own window; close that window to stop it. (`HVSR Studio.bat`
   starts it with a visible console for troubleshooting.)
3. Create a project, import the synthetic examples from `examples/` and follow
   `docs/user-guide.md`.

## Quick start (from source: Linux / macOS / Windows)

```
scripts/setup-dev.sh          # Linux / macOS — downloads a private toolchain, builds everything
launcher/hvsr-studio.sh       # start (macOS: launcher/hvsr-studio.command)

scripts\setup-dev.ps1         # Windows developers (needs php, composer, node, python 3.12)
"HVSR Studio.bat"
```

## Documentation

| Document | Content |
|---|---|
| `docs/user-guide.md` | installation, workflow, every screen and parameter |
| `docs/hvsr-algorithms.md` | the processing and HVSR algorithms with equations and citations |
| `docs/validation.md` | numerical validation results and comparison with hvsrpy |
| `docs/architecture.md` | tiers, repository layout, interface contract |
| `docs/engine-api.md`, `docs/laravel-api.md`, `docs/frontend.md` | per-tier references |
| `docs/sample-report.pdf` | example PDF report generated from a synthetic dataset |
| `packaging/README.md` | building the Windows distribution and installer |

## Technology

Laravel 13 (PHP 8.4, SQLite) · Vue 3 + TypeScript + Tailwind CSS 4 · Plotly.js · Python 3.12 with
NumPy, SciPy, ObsPy, pandas, Matplotlib, ReportLab · FastAPI processing service on localhost.
All dependencies are open source (see `THIRD_PARTY_NOTICES.md`) and pinned
(`composer.lock`, `package-lock.json`, `engine/uv.lock`, `engine/requirements.lock.txt`).

## Tests

```
engine/.venv/bin/python -m pytest engine/tests -q        # scientific engine + service
php artisan test                                          # Laravel API
npx vue-tsc --noEmit && npm run build                     # frontend type-check + build
engine/.venv/bin/python engine/validation/run_validation.py
```

## License

MIT — see `LICENSE`. Third-party components keep their own licenses (`THIRD_PARTY_NOTICES.md`).
