# QuakeLogic HVSR Studio — Architecture & Interface Contract

This document is the single source of truth for how the three tiers of the
application fit together. Every tier is built against it.

```
┌──────────────────────────────┐   HTTP (JSON)   ┌────────────────────────────┐
│  Browser: Vue 3 + TS +       │ ─────────────▶  │  Laravel 13 (PHP 8.4)       │
│  Tailwind 4 + Plotly         │ ◀─────────────  │  SQLite app DB, project     │
│  (built assets, served by    │                 │  folders, exports, API      │
│  Laravel at 127.0.0.1:8090)  │                 └─────────────┬──────────────┘
└──────────────────────────────┘                               │ HTTP (JSON), localhost only
                                                               ▼
                                                 ┌────────────────────────────┐
                                                 │  Python 3.12 service        │
                                                 │  FastAPI + uvicorn          │
                                                 │  127.0.0.1:8765             │
                                                 │  hvsr_service → hvsr_engine │
                                                 │  (NumPy/SciPy/ObsPy/pandas) │
                                                 └────────────────────────────┘
```

* **hvsr_engine** (Python package) — pure scientific code. No HTTP, no DB.
  Fully testable with pytest.
* **hvsr_service** (Python package) — thin FastAPI layer over the engine:
  file inspection/import, processing, HVSR jobs (thread pool, progress,
  cancellation), figure/report/CSV export. Stateless except for an in-memory
  job table and an LRU cache of loaded traces.
* **Laravel** — owns the SQLite database (projects, stations, recordings,
  presets, runs, analyses, batches, history), the project folders on disk,
  file uploads, and the JSON API consumed by the browser. It never does
  numerical work; it calls the Python service (`App\Services\Engine\EngineClient`).
* **Vue SPA** — `resources/js`, served by a single Blade view. Talks only to
  the Laravel API (`/api/...`). Plotly for every scientific graphic.
* **Launcher** — `launcher/launch.py` starts the Python service and
  `php artisan serve`, waits for both health checks, opens the browser, and
  shuts both down on exit. Wrapped by `HVSR Studio.bat` / `.sh` / `.command`.

Everything binds to `127.0.0.1`. No accounts, no network access at runtime.

## Repository layout

```
hvsr-studio/
├── app/                     Laravel application code
│   ├── Http/Controllers/Api/  thin JSON controllers
│   ├── Models/
│   └── Services/
│       ├── Engine/EngineClient.php     HTTP client for the Python service
│       ├── Projects/ProjectStorage.php project folder layout + checksums
│       └── ...
├── database/migrations/     SQLite schema
├── resources/js/            Vue 3 SPA (TypeScript)
├── resources/css/app.css    Tailwind 4 + theme tokens
├── routes/api.php, web.php
├── engine/                  Python project (pyproject.toml, uv.lock, requirements.lock.txt)
│   ├── hvsr_engine/         scientific package
│   ├── hvsr_service/        FastAPI service
│   ├── tests/               pytest
│   └── validation/          cross-checks vs. hvsrpy / analytic references + results
├── launcher/                launch.py + OS wrappers
├── packaging/windows/       build-dist.ps1 (portable zip), installer.iss (Inno Setup)
├── scripts/                 setup-dev.sh / setup-dev.ps1 / build-frontend
├── examples/                synthetic TXT / CSV / MiniSEED datasets (+ README)
├── docs/                    user guide, algorithms, this file, validation report, sample PDF
├── data/                    runtime data (gitignored): hvsr-studio.sqlite, projects/
└── runtime/                 bundled runtimes (gitignored): <platform>/php, <platform>/python
```

## Runtime configuration (`.env`)

```
APP_URL=http://127.0.0.1:8090
HVSR_DATA_DIR=./data                  # absolute or relative to the app root
HVSR_ENGINE_URL=http://127.0.0.1:8765
HVSR_ENGINE_TOKEN=                    # optional shared secret (X-Engine-Token header)
DB_CONNECTION=sqlite
DB_DATABASE=./data/hvsr-studio.sqlite
```

## Project folder layout (on disk, managed by Laravel; paths handed to Python)

```
<HVSR_DATA_DIR>/projects/<project_slug>/
  project.json                       name, ulid, created, app version
  uploads/<upload_ulid>/<original>    staged uploads (before a recording exists)
  sources/<recording_ulid>/<original> managed copies of the source files (sha256 stored in DB)
  traces/<recording_ulid>.npz         canonical parsed recording (see "Canonical trace file")
  runs/<run_ulid>/processed.npz       output of a processing run
  runs/<run_ulid>/steps.json          ordered steps actually applied + warnings
  analyses/<analysis_ulid>/result.json
  analyses/<analysis_ulid>/curves.npz          per-window curves (float32)
  analyses/<analysis_ulid>/exports/*.csv|json|png|svg|pdf
  analyses/<analysis_ulid>/report.pdf
```

### Canonical trace file (`.npz`)
Written by `hvsr_engine.io.canonical.save_recording`. Keys:
`n`, `e`, `z` (float64 arrays, equal length), `meta` (JSON string):
```
{"fs": 100.0, "start_time": "2025-01-01T00:00:00.000000Z", "n_samples": 360000,
 "units": "counts", "unit_kind": "raw|velocity|acceleration|displacement|unknown",
 "channels": {"n": "HHN", "e": "HHE", "z": "HHZ"}, "station": "SYN1", "network": "XX",
 "location": "", "orientation_deg": 0.0, "source_files": [...], "import_settings": {...},
 "is_synthetic": false, "engine_version": "1.0.0"}
```
Processed outputs use the same format plus `"steps": [...]` and `"parent": "<path>"`.

## Python service API (127.0.0.1:8765)

All bodies/responses are JSON. Errors: `{"error": {"code": "...", "message": "...", "details": {...}}}`
with 400/404/422/500. If `HVSR_ENGINE_TOKEN` is set, every request must carry `X-Engine-Token`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{status:"ok", engine_version, python, versions{numpy,scipy,obspy,pandas,matplotlib}, workers, jobs_running}` |
| POST | `/files/inspect` | `{path}` → format detection + preview (see below) |
| POST | `/recordings/import` | parse + validate + write canonical npz (sync) |
| POST | `/recordings/data` | display-ready (downsampled) waveform data for a time range |
| POST | `/recordings/spectra` | FAS / PSD / spectrogram of a canonical or processed file (sync) |
| POST | `/processing/preview` | apply steps in memory, return display data + warnings (sync) |
| POST | `/processing/run` | apply steps, write `processed.npz` (**job**) |
| POST | `/processing/filter-response` | frequency response of a filter/notch design (sync) |
| POST | `/hvsr/windows` | window table with screening results (sync) |
| POST | `/hvsr/analyze` | full HVSR analysis, writes result files (**job**) |
| POST | `/analyses/load` | `{dir}` → `result.json` content |
| POST | `/analyses/window-curves` | `{dir}` → per-window curves `{frequency, curves:[[...]], accepted:[...]}` |
| POST | `/exports/figure` | matplotlib PNG/SVG/PDF of a result figure (sync) |
| POST | `/exports/report` | PDF report (**job**) |
| GET | `/jobs/{id}` | `{id, kind, status: queued|running|done|failed|cancelled, progress: 0..1, message, result, error, started_at, finished_at}` |
| POST | `/jobs/{id}/cancel` | request cancellation (cooperative) |
| GET | `/jobs` | list of recent jobs |

### `/files/inspect` response
```
{ "path", "size_bytes", "sha256", "format": "ascii"|"mseed"|"unknown",
  "ascii": { "encoding", "delimiter": ","|"\t"|";"|" "|"whitespace", "decimal": ".",
             "header_rows": 1, "comment_prefix": "#"|null, "columns": [{"index":0,"name":"time","numeric":true,"sample":[...]}],
             "n_rows_estimate", "preview_lines": ["raw line", ...] (first 40), "preview_rows": [[...],...] (parsed first 20),
             "time_column_guess": {"index":0,"kind":"seconds"|"datetime"|null,"sample_rate_estimate":100.0|null},
             "sample_rate_hint": 100.0|null (from "# sample_rate" style comments) },
  "mseed": { "traces": [{"id":"XX.SYN1..HHZ","network","station","location","channel","starttime","endtime","sampling_rate","npts","segments":2,"has_gaps":true}] }
}
```

### `/recordings/import` request
```
{ "recording_id": "<ulid>", "output_path": ".../traces/<ulid>.npz",
  "sources": [ {"path": "...", "role": "all"|"n"|"e"|"z"} ],
  "format": "ascii"|"mseed",
  "ascii": { "delimiter", "decimal", "header_rows", "comment_prefix",
             "columns": {"n": 1, "e": 2, "z": 3},            # column index per component (per-file when role != all)
             "time": {"mode": "sample_rate"|"seconds_column"|"datetime_column", "sample_rate": 100.0, "column": 0, "datetime_format": null},
             "start_time": "ISO8601"|null, "units": "counts", "unit_kind": "raw", "scale_factor": 1.0 },
  "mseed":  { "n": "XX.S..HHN", "e": "XX.S..HHE", "z": "XX.S..HHZ", "merge_policy": "reject_gaps" },
  "metadata": { "station": "SYN1", "network": "XX", "location": "", "orientation_deg": 0.0, "is_synthetic": true }
}
```
Response: `{"ok": true|false, "meta": {...canonical meta...}, "validation": {"blocking": bool, "issues": [{"code","severity":"error"|"warning"|"info","message","details"}]}}`.
The engine never interpolates gaps, never resamples, never rotates, never fabricates a missing
component during import. Blocking `error` issues mean no npz is written (`ok=false`).

Validation codes: `missing_component`, `sample_rate_mismatch`, `length_mismatch`, `time_misaligned`,
`gaps`, `overlaps`, `duplicate_timestamps`, `irregular_sampling`, `nan_values`, `constant_channel`,
`clipping_suspected`, `no_timing_information`, `short_record`, `unit_unknown`.

### `/recordings/data` request/response
```
req:  {"path": "...npz", "t_start": 0.0|null, "t_end": null, "max_points": 4000, "components": ["n","e","z"]}
resp: {"fs", "start_time", "duration_s", "n_samples", "t_start", "t_end",
       "downsampled": true, "n_display": 4000, "method": "minmax",
       "components": {"n": {"t": [...], "v": [...]}, ...}}   # when downsampled, t/v are the min/max envelope (2 points per bucket)
```

### `/recordings/spectra` request
```
{"path", "kind": "fas"|"psd"|"spectrogram", "window_length_s": 60, "overlap": 0.5, "taper_percent": 5,
 "detrend": "linear", "smoothing": {"type": "konno_ohmachi"|"none", "bandwidth": 40}, "freq_min": 0.1, "freq_max": 50,
 "n_freq": 300, "components": ["n","e","z"], "t_start": null, "t_end": null}
```
FAS response: `{"frequency": [...], "components": {"n": [...], ...}, "units": "counts*s", "definition": "..."}`.
PSD response: Welch, `{"frequency", "components", "units": "counts^2/Hz"}`.
Spectrogram: `{"components": {"n": {"t": [...], "f": [...], "db": [[...]]}}}` (10·log10 PSD).

### Processing steps (shared by preview, run, presets)
```
[{"op": "demean", "enabled": true, "params": {}},
 {"op": "detrend", "params": {}},                                       linear
 {"op": "polynomial", "params": {"order": 3}},                          baseline, order 1..10
 {"op": "filter", "params": {"kind": "highpass"|"lowpass"|"bandpass"|"bandstop", "freq_low": 0.5, "freq_high": 20, "order": 4, "zero_phase": true}},
 {"op": "notch", "params": {"frequency": 60, "quality": 30, "harmonics": 1, "zero_phase": true}},
 {"op": "taper", "params": {"percent": 5}},                             cosine (Tukey) taper, percent of total length per side pair
 {"op": "crop", "params": {"start_s": 10, "end_s": 1800}},
 {"op": "resample", "params": {"target_rate": 50, "method": "decimate"|"polyphase"}},   anti-aliased
 {"op": "rotate", "params": {"azimuth_deg": 12.0}},                     sensor N-axis azimuth (clockwise from true north) → true N/E
 {"op": "remove_response", "params": {"source": "stationxml"|"paz", "path": "...xml", "output": "VEL", "water_level": 60,
                                       "pre_filt": [0.01,0.02,45,50] | null,
                                       "paz": {"poles": [[re,im],...], "zeros": [[re,im],...], "gain": 1.0, "sensitivity": 1.0}}}]
```
`/processing/preview` req: `{"input_path", "steps", "t_start", "t_end", "max_points"}` →
`{"raw": <data resp>, "processed": <data resp>, "warnings": [{"step_index", "code", "message"}], "applied": [...steps with effective params...], "fs_out"}`.
`/processing/run` req: `{"input_path", "output_path", "steps"}` → job; job result `{"output_path", "meta", "warnings", "applied"}`.
`/processing/filter-response` req: `{"fs", "step": {<filter or notch step>}, "n_points": 1024}` → `{"frequency", "magnitude_db", "phase_deg", "warnings"}`.

Warning codes: `cutoff_above_nyquist`, `cutoff_not_positive`, `band_inverted`, `record_short_for_filter`,
`edge_effects`, `high_order`, `excessive_processing`, `resample_upsampling`, `resample_not_integer`,
`response_missing`, `polynomial_high_order`.

### HVSR parameters (`/hvsr/windows` and `/hvsr/analyze`)
```
{"input_path": "...npz", "output_dir": ".../analyses/<ulid>",  (analyze only)
 "params": {
   "window_length_s": 60, "overlap": 0.5,
   "screening": {"enabled": true,
                 "sta_lta": {"enabled": true, "sta_s": 1.0, "lta_s": 30.0, "min_ratio": 0.2, "max_ratio": 2.5},
                 "amplitude": {"enabled": false, "max_ratio_to_rms": 5.0}},
   "detrend": "linear", "taper_percent": 5,
   "smoothing": {"type": "konno_ohmachi", "bandwidth": 40},
   "freq_min": 0.2, "freq_max": 30, "n_freq": 300,
   "horizontal_method": "geometric_mean"|"rms"|"directional",
   "combination_stage": "after_smoothing",
   "mean_method": "geometric"|"arithmetic"|"median",
   "peak": {"search_min": 0.5, "search_max": 20, "min_prominence": 0.0},
   "vertical_floor": {"relative": 1e-6, "absolute": 1e-12},
   "min_valid_windows": 3,
   "bootstrap": {"enabled": true, "n_resamples": 200},
   "azimuthal": {"enabled": false, "step_deg": 10},
   "sesame": true },
 "window_overrides": {"3": {"accepted": false, "reason": "manual"}, "7": {"accepted": true, "reason": "manual"}},
 "manual_peak": {"frequency": 2.4} | null,
 "random_seed": 12345 | null}
```
`/hvsr/windows` → `{"windows": [{"index","start_s","end_s","accepted","reason","sta_lta_max","sta_lta_min","amp_ratio","has_nan"}], "counts": {"total","accepted","rejected"}, "screening_applied": {...}}`.
`/hvsr/analyze` → job; job result = `{"output_dir", "summary": {...}}`; `result.json` holds the full result:

```
{ "engine_version", "versions", "computed_at", "elapsed_s", "random_seed",
  "params": {...echo...}, "input": {"path","sha256","fs","n_samples","duration_s","start_time","station","is_synthetic"},
  "frequency": [...],                                  log-spaced analysis axis
  "windows": {"length_s","overlap","count_total","count_accepted","count_rejected",
              "items":[{"index","start_s","end_s","accepted","reason","sta_lta_max","sta_lta_min","amp_ratio","f0","a0"}]},
  "curves": {"selected": "geometric",
             "geometric":  {"values":[...], "lower":[...], "upper":[...], "band": "exp(mean(ln HV) ± std(ln HV, ddof=1))", "sigma_ln":[...]},
             "arithmetic": {"values","lower","upper","band": "mean(HV) ± std(HV, ddof=1)"},
             "median":     {"values","lower","upper","band": "16th–84th percentile of window curves"}},
  "components": {"n":[...], "e":[...], "z":[...], "h":[...]},  mean smoothed amplitude spectra over accepted windows (units counts*s)
  "directional": {"n_over_z": {<curves like above>}, "e_over_z": {...}} | null,
  "masking": {"policy": "...", "bins_masked_any_window", "invalid_bins": [...], "min_valid_windows"},
  "peaks": {"search_range": [a,b], "candidates": [{"frequency","amplitude","prominence","rank"}],
            "selected": {"frequency","amplitude","source":"automatic"|"manual"} | null,
            "status": "clear"|"multiple"|"none"|"insufficient_data", "message": "..."},
  "peak_variability": {"window_f0": [...], "window_a0": [...], "n", "median", "p16", "p84", "std", "std_ln",
                       "definition": "...", "bootstrap": {"n_resamples","seed","f0_p2_5","f0_p50","f0_p97_5","a0_p2_5","a0_p97_5","definition"} | null},
  "sesame": {"reference": "SESAME (2004) ... D23.12", "f0","a0",
             "reliability": [{"id":"R1","label","passed","value","threshold","detail"}, R2, R3],
             "clarity":     [{"id":"C1",...}, ... C6],
             "reliability_passed": bool, "clarity_passed_count": int, "clarity_passed": bool} | null,
  "quality_flags": [{"code","severity","message"}],
  "azimuthal": {"azimuths":[...], "frequency":[...], "matrix":[[...]], "peak_frequency":[...], "peak_amplitude":[...]} | null }
```
Analyze also writes to `exports/`: `hvsr_mean.csv`, `hvsr_windows.csv`, `component_spectra.csv`,
`summary.csv`, `summary.json`, `config.json`, and (if enabled) `azimuthal.csv`.

### Exports
`/exports/figure` req: `{"analysis_dir", "figure": "hvsr"|"spectra"|"windows"|"azimuthal"|"peak_distribution", "format": "png"|"svg"|"pdf", "output_path", "theme": "light"}` → `{"output_path"}`.
`/exports/report` req: `{"analysis_dir", "output_path", "context": {"project": {...}, "station": {...}, "recording": {...}, "source_files": [...], "processing_steps": [...], "app_version"}}` → job; result `{"output_path"}`.

## Laravel JSON API (consumed by the SPA)

Base `/api`. Responses are JSON; errors `{"message": "...", "errors": {...}}` (422 for validation),
`{"message"}` for 404/409/500. Timestamps ISO-8601. All ids exposed to the SPA are ULIDs.

| Method | Path | Notes |
|---|---|---|
| GET | `/app/status` | `{app_version, engine: <health or {status:"down"}>, data_dir, theme_default}` |
| GET/PUT | `/settings` | app settings key/value |
| GET/POST | `/projects` ; GET/PUT/DELETE `/projects/{p}` | project CRUD; GET includes `stations`, `recordings` (with runs + analyses), `presets`, `batches` |
| GET | `/projects/{p}/history` | activity log |
| POST/PUT/DELETE | `/projects/{p}/stations`, `/stations/{s}` | |
| POST | `/projects/{p}/uploads` (multipart `files[]`) | stage + inspect each; returns `[{upload_id, name, size, inspect: <inspect resp>}]` |
| POST | `/projects/{p}/recordings` | body `{name, station_id, upload_ids, import: <import request minus paths>}` → moves files to sources, calls engine import, stores recording; 422 with `validation` when blocking |
| GET/PUT/DELETE | `/recordings/{r}` | |
| GET | `/recordings/{r}/data?run=<run_ulid>&t_start&t_end&max_points` | proxies `/recordings/data` |
| POST | `/recordings/{r}/spectra` | proxies |
| POST | `/recordings/{r}/processing/preview` | proxies preview |
| POST | `/recordings/{r}/runs` | `{name, steps}` → creates run, starts engine job → `{run, job}` |
| GET/DELETE | `/runs/{id}` | includes `job` status when running |
| POST | `/engine/filter-response` | proxies |
| GET/POST/PUT/DELETE | `/projects/{p}/presets`, `/presets/{id}` | processing presets (steps + hvsr params) |
| POST | `/recordings/{r}/windows` | `{run_id, params, window_overrides}` → proxies `/hvsr/windows` |
| POST | `/recordings/{r}/analyses` | `{name, run_id, params, window_overrides, manual_peak, random_seed}` → creates analysis + job |
| GET/PUT/DELETE | `/analyses/{a}` | GET returns row + `result` (from result.json when done) + `job` |
| GET | `/analyses/{a}/window-curves` | proxies |
| POST | `/analyses/{a}/rerun` | re-run with the stored params (reproducibility) |
| POST | `/analyses/{a}/select-peak` | `{frequency}` or `{frequency: null}` → recompute peak block (engine re-run, fast) |
| GET | `/analyses/{a}/exports/{kind}` | `kind`: `hvsr-csv`, `windows-csv`, `spectra-csv`, `summary-csv`, `summary-json`, `config-json`, `azimuthal-csv` → file download |
| GET | `/analyses/{a}/figure?figure=hvsr&format=png` | file download |
| POST | `/analyses/{a}/report` | creates report job → `{job}`; GET `/analyses/{a}/report` downloads when ready |
| POST | `/projects/{p}/batches` | `{name, preset_id, recording_ids, run_steps: bool}` → creates a batch: for each recording a run (if steps) then an analysis, executed sequentially by a background dispatcher |
| GET | `/batches/{b}` ; POST `/batches/{b}/cancel` | |
| POST | `/projects/{p}/compare` | `{analysis_ids}` → `[{analysis, frequency, curve, lower, upper, peak}]` |
| GET | `/jobs/{id}` | proxies engine job status |

Batch execution: Laravel runs a lightweight dispatcher via `php artisan hvsr:batch-worker` is **not**
used (single launcher requirement). Instead the batch controller submits the first item's engine
job immediately and the SPA polls `/batches/{b}`; each poll advances the batch (submits the next
item when the previous finished). A failed item is recorded and skipped; the batch continues.

## Frontend structure

```
resources/js/
  app.ts                bootstraps Vue, Pinia, router, theme
  router.ts             /projects, /projects/:id, /projects/:id/import, /waveforms/:recording, /windows/:recording,
                        /hvsr/:analysis, /compare, /reports, /settings
  api/                  typed fetch wrappers (types.ts mirrors this contract)
  stores/               app (status/theme/engine), project (tree), jobs (polling)
  layout/               AppShell (top bar, navigator, workspace, processing panel, resizable splitters)
  components/plots/     PlotlyChart.vue wrapper + WaveformPlot, SpectraPlot, SpectrogramPlot, HvsrPlot, WindowsPlot, AzimuthHeatmap, ComparePlot
  components/ui/        Button, Panel, Field, NumberInput, Select, Toggle, Modal, EmptyState, ProgressBar, Toast
  pages/                Projects, ProjectOverview, ImportWizard, Waveforms, WindowSelection, HvsrAnalysis, BatchCompare, Reports, Manual (in-app docs via GET /api/docs/{doc}, rendered with marked), Settings
  stores/guide.ts + components/GuideWizard.vue   guided workflow wizard (8 steps, completion derived from the open project)
```
Assets: Inter + JetBrains Mono via `@fontsource-variable/*` (OFL), icons via `lucide-vue-next` (ISC),
`plotly.js-cartesian-dist-min` (MIT). No CDN links anywhere.

Brand (same as the enterprise app): QuakeLogic orange `#F26522` (primary, selected peak), charcoal `#3a3c41` (secondary, curves, PDF headings), slate neutrals; official Q logo tile (`public/quakelogic-q-logo.png`) in the top bar and the wordmark (`engine/hvsr_engine/reporting/assets/quakelogic-logo.png`) in the PDF header.
Light and dark themes via `.dark` on `<html>`, persisted in localStorage.

## Integration notes (as built)

* Every Laravel analysis payload carries both `run_id` and `processing_run_id` (same ULID) for
  the SPA; `summary` is the engine summary block plus flat fields `f0`, `a0`, `peak_status`,
  `peak_source`, `count_accepted`, `count_total`, `sesame_reliability`, `sesame_clarity_count`.
* `POST /api/projects/{p}/recordings` accepts component roles either as
  `import.roles: {upload_id: role}` or as `import.sources: [{upload_id, role}]` (what the SPA sends).
  Uploads are copied, not moved; a blocked import (422) leaves them staged for a retry.
* Extra engine endpoints used by Laravel: `POST /hvsr/select-peak` (`{analysis_dir, frequency|null}`)
  and `POST /analyses/summary` (`{dir}`) — see `docs/engine-api.md`.
* All engine POST routes return HTTP 200 (not FastAPI's default 201). Engine errors map to
  422/404/409/500 with the `{"error": {...}}` envelope.
* `GET /api/projects/{p}` refreshes the state of queued/running runs and analyses from the engine
  before serialising, so the navigator never shows stale states.
* PHP upload/memory limits for the `php -S` worker come from `launcher/php.d/hvsr.ini` through the
  `PHP_INI_SCAN_DIR` environment variable set by the launcher (`artisan serve` does not forward
  `-d` flags to its child process). The Windows bundle additionally ships a `php.ini`.
* The launcher generates a per-session `HVSR_ENGINE_TOKEN`; Laravel sends it as `X-Engine-Token`.
* STA/LTA screening uses the engine's absolute-value STA/LTA with a 2 s STA default (see
  `docs/hvsr-algorithms.md` §3) — the SPA defaults match.

## Parity additions (QLExplorer-HVSR feature set) — contract

### Windows (engine `params.windows`, used by `/hvsr/windows` and `/hvsr/analyze`)
```
"windows": {
  "mode": "fixed" | "auto_variable" | "custom",
  "length_s": 60, "overlap": 0.5,                       fixed mode (existing window_length_s/overlap keep working as aliases)
  "min_length_s": 30, "max_length_s": 60,               auto_variable: pack the longest possible windows (≤ max, ≥ min) into
                                                        the quiet parts of the record; quiet = every component below its level
                                                        threshold AND STA/LTA inside [min,max] (when enabled)
  "levels": {"enabled": false, "mode": "absolute"|"ratio_rms", "n": 0, "e": 0, "z": 0, "ratio": 5.0},
  "custom": [[start_s, end_s], ...]                     custom mode (free selection / repositioned windows; any lengths)
}
```
Every window item gains `"length_s"` and `"color_index"` (0..n-1 in time order; the UI maps it onto a rainbow palette).
`/hvsr/windows` accepts `"custom"` in all modes to append user-drawn windows. Analysis handles variable window
lengths (per-length FFT grids, one Konno–Ohmachi matrix per distinct length, all resampled onto the common log axis).
result.json adds `"time_frequency": {"times_s": [window start...], "frequency": [...], "matrix": [[...]]}` = per-window
H/V (accepted windows only; NaN rows for rejected) so the UI can draw the H/V-vs-time graph without recomputation, and
`"t10_hz": 10 / max_window_length_s` (SESAME reliability limit, drawn as the "T10" line).

### Forward modelling (engine `hvsr_engine/modelling.py`, service `POST /model/hvsr`)
```
req:  {"layers": [{"thickness_m": 50, "vs": 155, "vp": 320|null, "poisson": 0.347|null, "density": 1800, "qs": 30, "qp": 60}, ...,
                  {"thickness_m": null, "vs": 450, "vp": 800, "density": 2200}],   last layer = half-space
       "freq_min": 0.2, "freq_max": 100, "n_freq": 200, "vs30_offset_m": 0}
resp: {"frequency": [...], "hvsr": [...], "t_sh": [...], "t_p": [...],
       "layers": [{... echo with vp/poisson completed, "depth_top_m", "depth_bottom_m"}],
       "vs30": 274.1, "vseq": {"value": 155.0, "depth_m": 58.0, "definition": "..."},
       "f0_model": 0.85, "method": "Herak (2008) body-wave transfer-function ratio |T_SH|/|T_P| (Thomson–Haskell, vertical incidence, complex velocities with Q)",
       "notes": ["A forward model that fits the curve is not unique ..."]}
```
Poisson from Vp/Vs: ν = (r²−2)/(2(r²−1)); Vp from ν: Vp = Vs·sqrt((2−2ν)/(1−2ν)). Vs30 = 30 / Σ(h_i/Vs_i) over the 30 m
below `vs30_offset_m`; VsEq = H / Σ(h_i/Vs_i) down to the top of the half-space when that depth H < 30 m (else = Vs30).
Reference: Herak, M. (2008). ModelHVSR — a Matlab tool to model horizontal-to-vertical spectral ratio of ambient noise.
Computers & Geosciences 34(11), 1514–1526.

### Curves import/export
* Analysis exports gain `hvsr_mean.hv` (Geopsy .hv text: header lines starting with `#`, then columns
  `frequency average min max`, min/max = the dispersion band) — Laravel export kind `geopsy-hv`.
* `POST /curves/import` (service) `{"path"}` → `{"frequency", "values", "lower"|null, "upper"|null, "name", "format": "geopsy_hv"|"csv"}`
  (accepts Geopsy .hv and 2–4 column CSV/TXT). Laravel: `POST /api/projects/{p}/curves` (multipart `file`) → same JSON.

### Formats
`/files/inspect` recognises SESAME ASCII (`.saf`, header `SESAME ASCII data format`), GSE2 (`.gse`), SEG-2 (`.seg`/`.sg2`),
SAC and MiniSEED through ObsPy; response `format` is `"ascii" | "saf" | "seismic"` (seismic = any ObsPy-readable multi-trace
file, listed under `mseed.traces` exactly like MiniSEED). `/recordings/import` accepts `format: "saf"` (3 channels from the SAF
header CH0_ID/CH1_ID/CH2_ID, sample rate SAMP_FREQ, START_TIME) and `format: "seismic"` (same body as mseed).

### Survey / report details
Laravel `analyses.survey` JSON: `{"date","client","place_id","address","latitude","longitude","datum","elevation_m","weather","notes",
"photos": [{"file": "survey/photo1.jpg", "caption": ""}, ...]}` (max 2 photos stored under `analyses/<ulid>/survey/`).
`PUT /api/analyses/{a}/survey` (multipart: fields + `photo1`, `photo2`, `remove_photo1/2`), `GET` returns it. The report
context carries `survey`; the PDF gets a "Survey" section (table + the photos side by side) after the station metadata.

### Models and window sets
* `analyses.models` JSON: list of `{"id","name","layers":[...],"vs30_offset_m","created_at"}`; `PUT /api/analyses/{a}/models`
  replaces the list; `POST /api/engine/model-hvsr` proxies `/model/hvsr`.
* Window set: `GET /api/analyses/{a}/exports/windows-json` → `{"mode","params","windows":[{"start_s","end_s","accepted","reason"}]}`;
  `POST /api/recordings/{r}/windows/import` (JSON body of the same shape) → normalised `custom` list + overrides for the UI.
* Full-resolution samples for the player: `GET /api/recordings/{r}/samples?component=z&run=<ulid>&t_start&t_end`
  → `{"fs","t0","values":[...]}` (engine `/recordings/data` with `max_points` = n_samples; capped at 4,000,000 samples).
* Project backup: `GET /api/projects/{p}/backup` streams `<slug>-backup.zip` (project folder + `database.json` with all rows);
  `POST /api/projects/restore` (multipart `file`) recreates the project (new ULIDs if the slug exists → suffix).
