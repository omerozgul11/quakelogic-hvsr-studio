# Engine service API (hvsr_service)

The Python processing service wraps the pure scientific package `hvsr_engine` behind a small
HTTP/JSON interface on **127.0.0.1:8765**. Laravel is its only client. It keeps no database:
it reads and writes the files that Laravel names (canonical `.npz` recordings, processing
outputs, analysis directories) and keeps an in-memory table of background jobs.

## Running

```bash
# development (Linux/macOS)
engine/.venv/bin/python -m hvsr_service --port 8765
# options
--host 127.0.0.1        bind address (never expose beyond localhost)
--port 8765
--workers N             job worker threads (default: cpu_count / 2, minimum 1)
--token SECRET          require header X-Engine-Token: SECRET (default: $HVSR_ENGINE_TOKEN)
--log-level info
```
Environment variables: `HVSR_ENGINE_HOST`, `HVSR_ENGINE_PORT`, `HVSR_ENGINE_TOKEN`.
Interactive OpenAPI docs: `http://127.0.0.1:8765/docs` (local only).

Module layout: `hvsr_service/app.py` (factory), `jobs.py` (thread-pool job manager),
`cache.py` (LRU of loaded recordings, keyed by path+mtime+size, 8 entries), `security.py`
(token check + error envelope middleware), `schemas.py` (request models), `summary.py`
(compact result summary), `routes/*.py`.

## Conventions

* JSON in, JSON out. All POST endpoints answer **200** on success.
* Errors always use the envelope
  ```json
  {"error": {"code": "not_found", "message": "Recording file not found: …", "details": {}}}
  ```
  | HTTP | code | cause |
  |---|---|---|
  | 401 | `unauthorized` | token configured and header missing/wrong |
  | 404 | `not_found` | file, directory or job does not exist |
  | 409 | `cancelled` | operation cancelled |
  | 422 | `invalid_request` | body failed schema validation (`details.errors`) |
  | 422 | `invalid_parameters`, `import_error`, `processing_error`, `invalid_filter`, `band_inverted`, … | engine rejected the request (ValueError / any `EngineError`; `code` is the engine's own identifier) |
  | 500 | `engine_unavailable` | an `hvsr_engine` module could not be imported |
  | 500 | `internal_error` | anything else (traceback logged to stdout) |
* Nested parameter blocks (`params`, `steps`, `ascii`, `mseed`, `context`, …) are passed through
  to the engine untouched, so the engine documentation (`docs/architecture.md`,
  `docs/hvsr-algorithms.md`) is the authority on their contents and defaults.
* Long operations return a **job** immediately; poll `GET /jobs/{id}`.

## Job lifecycle

```
POST /processing/run | /hvsr/analyze | /exports/report
        │  200 {"id": "…", "status": "queued", ...}
        ▼
GET /jobs/{id}   →  queued → running (progress 0..1, message) → done | failed | cancelled
POST /jobs/{id}/cancel   sets a cancellation event; the engine checks it between windows/steps
```
Job record:
```json
{"id": "3f9c…", "kind": "hvsr", "status": "running", "progress": 0.42, "message": "window 21/50",
 "result": null, "error": null, "meta": {"input_path": "…", "output_dir": "…"},
 "created_at": "…Z", "started_at": "…Z", "finished_at": null}
```
On failure `error` is `{"code","message","details","traceback"}` and the worker thread survives.
The last 200 jobs are kept; `GET /jobs?limit=50` lists the most recent first.

## Endpoints

### `GET /health`
```json
{"status": "ok", "service_version": "1.0.0", "engine_version": "1.0.0", "python": "3.12.14",
 "versions": {"numpy": "2.5.3", "scipy": "1.18.1", "obspy": "1.5.1", "pandas": "2.3.3", "matplotlib": "3.11.2"},
 "workers": 4, "jobs_running": 0}
```
`status` is `degraded` when `hvsr_engine` cannot be imported. Exempt from the token check.

### `POST /files/inspect`
`{"path": "/abs/file.txt"}` → format detection and preview (ASCII delimiter/header/columns/time
column guess, MiniSEED trace list) as specified in `docs/architecture.md`.

### `POST /recordings/import`
Body: the import request of the contract (`recording_id`, `output_path`, `sources[]`, `format`,
`ascii` | `mseed`, `metadata`). Synchronous. Response
```json
{"ok": true, "meta": {"fs": 100.0, "start_time": "…Z", "n_samples": 120000, "units": "counts", "channels": {...}},
 "validation": {"blocking": false, "issues": [{"code": "short_record", "severity": "warning", "message": "…", "details": {}}]}}
```
`ok=false` (blocking issues) means no file was written. The cache is cleared after every import.

### `POST /recordings/data`
```json
{"path": "…/traces/<ulid>.npz", "t_start": 0, "t_end": 120, "max_points": 4000, "components": ["n","e","z"]}
```
→ `{"fs","start_time","duration_s","n_samples","t_start","t_end","downsampled","n_display","method":"minmax","components":{"n":{"t":[…],"v":[…]},…}}`.
When `downsampled` is true, `t`/`v` are a min/max envelope (two points per bucket).

### `POST /recordings/spectra`
`{"path", "kind": "fas"|"psd"|"spectrogram", ...engine spectra params}` → FAS/PSD/spectrogram arrays.

### `POST /processing/preview` (sync)
`{"input_path", "steps": [...], "t_start", "t_end", "max_points"}` →
`{"raw": <data>, "processed": <data>, "warnings": [{"step_index","code","message"}], "applied": [...], "fs_out"}`.

### `POST /processing/run` (job)
`{"input_path", "output_path", "steps"}` → job; result `{"output_path","meta","warnings","applied"}`.
The written `.npz` carries `meta.steps` (effective parameters) and `meta.parent`.

### `POST /processing/filter-response`
`{"fs": 100, "step": {"op": "filter", "params": {...}}, "n_points": 1024}` →
`{"frequency","magnitude_db","phase_deg","warnings"}`.

### `POST /hvsr/windows`
`params.windows` selects the window mode (`fixed` | `auto_variable` | `custom`, see
docs/hvsr-algorithms.md §3a); `window_length_s` / `overlap` remain valid aliases. The response adds
`mode`, `min_length_s`, `max_length_s`, `t10_hz`, `windows_params`, and every window item has
`length_s` and `color_index`.

`{"input_path", "params": {window_length_s, overlap, screening…}, "window_overrides": {"3": {"accepted": false, "reason": "manual"}}}`
→ `{"windows": [...], "counts": {"total","accepted","rejected"}, "screening_applied": {...}}`.

### `POST /hvsr/analyze` (job)
`{"input_path", "output_dir", "params", "window_overrides", "manual_peak", "random_seed"}` → job.
Writes `result.json`, `curves.npz`, `exports/*` into `output_dir`. Job result:
`{"output_dir", "summary": <compact summary, see /analyses/summary>}`.

`result.json` additionally contains `t10_hz` (SESAME 10-cycle limit), `windows.mode`,
`windows.mean_accepted_length_s` and `time_frequency` (`times_s`, `end_times_s`, `accepted`,
`frequency`, `matrix` = per-window H/V in time order). `exports/` gains `hvsr_mean.hv` (Geopsy format).

### `POST /hvsr/select-peak`
`{"analysis_dir", "frequency": 2.4 | null}` → `{"result": <full result.json>, "summary": {...}}`.
`null` restores automatic selection. Rewrites `result.json` and the summary exports.

### `POST /analyses/load` · `POST /analyses/window-curves` · `POST /analyses/summary`
All take `{"dir": "…/analyses/<ulid>"}`.
* `load` → the full `result.json`.
* `window-curves` → `{"frequency": [...], "curves": [[...], ...], "accepted": [...]}` (NaN → null).
* `summary` → compact block for the application database: `engine_version, computed_at, elapsed_s,
  random_seed, input, windows{counts}, curves_selected, peaks, peak_variability (without the per-window
  arrays), sesame (ids/pass/value/threshold), masking counts, quality_flags, azimuthal_enabled,
  interpretation_notes`.

### `POST /exports/figure` (sync)
```json
{"analysis_dir": "…", "figure": "hvsr"|"spectra"|"windows"|"azimuthal"|"peak_distribution",
 "format": "png"|"svg"|"pdf", "output_path": "…/exports/hvsr.png", "theme": "light"|"dark",
 "recording_path": null}
```
→ `{"output_path"}`. The `windows` figure needs the waveforms: `recording_path` if given, else
`result.input.path`. PNG is rendered at 200 dpi.

### `POST /exports/report` (job)
```json
{"analysis_dir": "…", "output_path": "…/report.pdf", "recording_path": null,
 "context": {"project": {"name","description"}, "station": {"code","name","latitude","longitude","elevation","sensor_orientation_deg"},
             "recording": {"name","sample_rate","start_time","duration_s","n_samples","units","channels","is_synthetic"},
             "source_files": [{"name","role","size_bytes","sha256"}], "processing_steps": [...], "app_version": "1.0.0"}}
```
→ job; result `{"output_path"}`. The report (US Letter, reportlab) contains: summary, station and
recording metadata, processing settings, window statistics, figures, peak and variability,
SESAME (2004) criteria table, interpretation limitations and a reproducibility block.

### `POST /model/hvsr` (sync)
Forward model of the H/V curve from a layered ground model (Herak 2008, |T_SH|/|T_P|).
```
{"layers": [{"thickness_m": 50, "vs": 155, "vp": 320, "poisson": null, "density": 1800, "qs": 30, "qp": 60}, ..., {"vs": 450, "vp": 800}],
 "freq_min": 0.2, "freq_max": 100, "n_freq": 200, "vs30_offset_m": 0}
→ {"frequency", "hvsr", "t_sh", "t_p", "layers" (completed, with depth_top_m/depth_bottom_m/half_space), "vs30", "vseq": {"value","depth_m","definition"},
   "f0_model", "a0_model", "method", "reference", "notes"}
```
Invalid layers (non-positive thickness/Vs, ν outside [0, 0.5)) → 422.

### `POST /curves/import` (sync)
`{"path"}` → `{"frequency", "values", "lower"|null, "upper"|null, "name", "format": "geopsy_hv"|"csv", "n_points", "source"}` for
Geopsy `.hv` files and 2–4 column delimited tables.

### Formats accepted by `/files/inspect` and `/recordings/import`
`format` is `ascii`, `mseed`, `saf` (SESAME ASCII; `inspect.saf` = header, channels, columns, plus a MiniSEED-style `mseed.traces`
list) or `seismic` (any ObsPy-readable file — GSE2, SEG-2, SAC, MiniSEED…; `mseed.format_detected` names it). Import bodies for
`seismic` are identical to `mseed`; for `saf` the three channels are mapped from `CH0_ID..CH2_ID` (override with `saf: {"n": col, "e": col, "z": col}`).

### Report context: survey block
`context.survey = {date, client, place_id, address, latitude, longitude, datum, elevation_m, weather, notes, photos: [{file|path, caption}]}`
renders a "Survey" table and up to two photos (paths relative to `analysis_dir` or absolute) after the station metadata.

### `GET /jobs` · `GET /jobs/{id}` · `POST /jobs/{id}/cancel`
See *Job lifecycle*.

## Security model

The service listens on the loopback interface only. Optionally a shared secret can be required
(`--token` / `HVSR_ENGINE_TOKEN`); Laravel sends it as `X-Engine-Token`. There is no user
concept, no persistent state and no outbound network access.
