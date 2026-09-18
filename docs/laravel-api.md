# QuakeLogic HVSR Studio — Laravel JSON API

The Laravel tier owns the SQLite database, the project folders on disk and the JSON API used by the
Vue SPA. It never performs numerical work: every scientific call is proxied to the Python service
(`App\Services\Engine\EngineClient`, contract in `docs/architecture.md` and `docs/engine-api.md`).

## Running

```
php artisan hvsr:setup                      # create data dir, migrate, seed built-in presets (idempotent)
php artisan hvsr:doctor                     # data dir / SQLite / engine / PHP extension checks
php -d upload_max_filesize=2048M -d post_max_size=2048M -d memory_limit=1024M \
    artisan serve --host=127.0.0.1 --port=8090
```

The launcher passes those `-d` flags because PHP's built-in server ignores `.user.ini`; without
them multi-hundred-MB MiniSEED uploads would be rejected. Configuration lives in `.env`:

| Key | Default | Meaning |
|---|---|---|
| `HVSR_DATA_DIR` | `data` | Root of all user data (relative paths resolve against the app root). Contains `hvsr-studio.sqlite` and `projects/`. |
| `HVSR_ENGINE_URL` | `http://127.0.0.1:8765` | Python service base URL. |
| `HVSR_ENGINE_TOKEN` | *(empty)* | Optional shared secret sent as `X-Engine-Token`. |
| `HVSR_MAX_UPLOAD_MB` | `2048` | Per-file upload limit enforced by validation. |
| `DB_DATABASE` | `data/hvsr-studio.sqlite` | SQLite file (relative to app root, or absolute; `C:\…` and UNC paths accepted). |

SQLite runs in WAL mode with a 5 s busy timeout. Session and cache use the `file` drivers, so the
database contains only the application tables listed below.

## Conventions

* Base path `/api`. Requests and responses are JSON (uploads are `multipart/form-data`).
* Every record exposed to the SPA carries its **ULID as `id`**; route parameters are ULIDs.
* Timestamps are ISO-8601 (UTC).
* Errors:
  * `422` validation — `{"message": "...", "errors": {"field": ["..."]}}`
  * `422` import blocked — `{"message": "...", "validation": {"blocking": true, "issues": [...]}}`
  * `404` unknown record, `409` state conflict (e.g. analysis still running), `503` engine down
    — `{"message": "Processing engine is not running", "hint": "..."}`
  * Engine-side errors are relayed as `{"message": "<engine message>"}` with the engine's status code.
* No authentication and no CSRF on `/api` (the app is single-user and bound to localhost).

## Project folder layout

```
<HVSR_DATA_DIR>/projects/<slug>/
  project.json
  uploads/<upload_ulid>/<original>        staged upload (deleted once consumed by a recording)
  sources/<recording_ulid>/<original>     managed copies of the source files (sha256 in recording_files)
  traces/<recording_ulid>.npz             canonical parsed recording written by the engine
  runs/<run_ulid>/processed.npz, steps.json
  analyses/<analysis_ulid>/result.json, curves.npz, exports/*, report.pdf
```
`App\Services\Projects\ProjectStorage::safe()` guarantees every path stays under the data directory
(`..` segments and absolute escapes are rejected); uploaded filenames are reduced to a sanitised basename.

## Routes

### Application
| Method | Path | Description |
|---|---|---|
| GET | `/app/status` | `{app_version, app_name, engine: <engine /health or {status:"down", hint}>, engine_url, data_dir, theme_default, php_version}` |
| GET | `/settings` | `{theme_default, default_preset_id, plot_max_points, show_synthetic_banner, engine_url, data_dir, app_version}` |
| PUT | `/settings` | Body: any of `theme_default` (`light|dark|system`), `default_preset_id`, `plot_max_points` (500–50000), `show_synthetic_banner`. Returns the merged settings. |

### Projects & stations
| Method | Path | Body / notes |
|---|---|---|
| GET | `/projects` | List (`[{id, name, slug, description, counts{stations,recordings,analyses}, created_at, updated_at}]`) |
| POST | `/projects` | `{name, description?, settings?}` → 201 full project. Creates the folder layout. |
| GET | `/projects/{p}` | Full project: `stations[]`, `recordings[]` (each with `files[]`, `runs[]`, `analyses[]`), `presets[]` (built-in + project), `batches[]` |
| PUT | `/projects/{p}` | `{name?, description?, settings?}` |
| DELETE | `/projects/{p}` | Deletes rows **and** the project folder. |
| GET | `/projects/{p}/history` | Activity log, newest first (`[{id, action, subject_type, subject_id, details, created_at}]`) |
| POST | `/projects/{p}/stations` | `{code, name?, latitude?, longitude?, elevation?, orientation_deg?, notes?}` |
| PUT | `/stations/{s}` / DELETE `/stations/{s}` | |

Example:
```http
POST /api/projects
{"name": "Downtown survey", "description": "Ambient-noise HVSR, 2026 campaign"}

201 {"id":"01J...","name":"Downtown survey","slug":"downtown-survey","folder":"downtown-survey",
     "counts":{"stations":0,"recordings":0,"analyses":0},"stations":[],"recordings":[],"presets":[...],"batches":[]}
```

### Import
| Method | Path | Body / notes |
|---|---|---|
| POST | `/projects/{p}/uploads` | multipart `files[]` (1–20 files). Each file is staged under `uploads/<ulid>/` and inspected by the engine. Returns `[{upload_id, name, size, sha256, inspect}]` where `inspect` is the engine `/files/inspect` response (format, delimiter guess, columns, preview, MiniSEED traces…). |
| POST | `/projects/{p}/recordings` | `{name, station_id?, notes?, upload_ids: [..1–3], import: {format: "ascii"|"mseed", ascii?: {...}, mseed?: {...}, metadata?: {...}, roles?: {upload_id: "all"|"n"|"e"|"z"}}}`. The `ascii`/`mseed`/`metadata` blocks are passed verbatim to the engine import request (see architecture.md); Laravel adds the absolute source paths, `roles`, the station code/orientation and `output_path`. |

Import outcome:
* success → `201` recording (`status: "ready"`, `sample_rate`, `start_time`, `duration_s`, `n_samples`, `units`, `validation{blocking:false, issues[]}`, `files[]`, `meta`).
* blocking validation → `422 {"message": "...", "validation": {"blocking": true, "issues": [{code, severity, message, details}]}}`; the recording row and its folder are removed, the uploads are discarded.

```http
POST /api/projects/01J.../recordings
{"name":"Site A","upload_ids":["01J...U1"],
 "import":{"format":"ascii",
   "ascii":{"delimiter":"\t","decimal":".","header_rows":3,"comment_prefix":"#",
            "columns":{"n":1,"e":2,"z":3},
            "time":{"mode":"seconds_column","column":0},
            "units":"counts","unit_kind":"raw","scale_factor":1.0},
   "metadata":{"station":"SYNA","network":"XX","is_synthetic":true}}}
```

### Recordings
| Method | Path | Body / notes |
|---|---|---|
| GET | `/recordings/{r}` | Recording with `files`, `runs`, `analyses` |
| PUT | `/recordings/{r}` | `{name?, station_id?, notes?, is_synthetic?}` |
| DELETE | `/recordings/{r}` | Removes sources, trace, runs and analyses folders |
| GET | `/recordings/{r}/data?run=&t_start=&t_end=&max_points=&components=n,e,z` | Display-ready (min/max downsampled) waveform data. `run` = processing-run ULID to view processed data instead of the canonical trace. |
| POST | `/recordings/{r}/spectra` | `{kind: fas|psd|spectrogram, run_id?, ...engine spectra params}` |
| POST | `/recordings/{r}/processing/preview` | `{steps[], t_start?, t_end?, max_points?}` → `{raw, processed, warnings[], applied[], fs_out}` (synchronous, in-memory) |
| POST | `/recordings/{r}/windows` | `{run_id?, params, window_overrides?}` → window table with screening results |

### Processing runs
| Method | Path | Body / notes |
|---|---|---|
| POST | `/recordings/{r}/runs` | `{name?, steps: [{op, enabled?, params}]}` → `201 {run, job}`. Writes `runs/<ulid>/steps.json`, submits the engine job. |
| GET | `/runs/{id}` | Syncs the engine job: `status` (`queued|running|done|failed|cancelled`), `progress`, `error`, `applied`, `warnings`, `meta`, `output_path`, `job` (live job while active). |
| DELETE | `/runs/{id}` | Cancels the job if active and deletes the run folder. |
| POST | `/engine/filter-response` | `{fs, step: {op: filter|notch, params}, n_points?}` → `{frequency, magnitude_db, phase_deg, warnings}` |
| GET | `/jobs/{id}` / POST `/jobs/{id}/cancel` | Raw engine job status / cooperative cancel |

### Presets
| Method | Path | Body / notes |
|---|---|---|
| GET | `/projects/{p}/presets` | Built-in (`builtin: true`, project_id null) followed by project presets |
| POST | `/projects/{p}/presets` | `{name, description?, steps?, hvsr_params?}` |
| PUT | `/presets/{id}` / DELETE | Built-in presets answer `409` — duplicate into the project instead |

Built-in presets (seeded by `hvsr:setup`): *Standard ambient noise (60 s, KO 40)*, *Short windows (25 s)*,
*Low-frequency site (120 s, 0.1–10 Hz)*. Each carries `steps` (demean + linear detrend) and a full
`hvsr_params` block.

### Analyses
| Method | Path | Body / notes |
|---|---|---|
| POST | `/recordings/{r}/analyses` | `{name?, run_id?, params, window_overrides?, manual_peak?: {frequency}, random_seed?}` → 201. The input is the run's `processed.npz` when `run_id` is given (the run must be `done`), else the canonical trace. A random seed is generated and stored when omitted. |
| GET | `/analyses/{a}?include=result|none` | Syncs the engine job; when `done` stores `summary` (peaks, SESAME, window counts, quality flags, variability, seed) and — with `include=result` (default) — returns the full `result.json` as `result`. `job` carries live progress while active; `report_status`/`report_ready` describe the PDF. |
| PUT | `/analyses/{a}` | `{name}` |
| DELETE | `/analyses/{a}` | Cancels if active, deletes the result folder |
| POST | `/analyses/{a}/cancel` | Cooperative cancel |
| GET | `/analyses/{a}/window-curves` | `{frequency, curves[][], accepted[]}` (per-window HVSR curves) |
| POST | `/analyses/{a}/rerun` | Re-submits with the stored params, overrides and **the same random seed** (reproducibility) |
| POST | `/analyses/{a}/select-peak` | `{frequency: 2.4}` selects a manual peak, `{frequency: null}` restores automatic selection. Returns the analysis with the updated `result`. |
| GET | `/analyses/{a}/exports/{kind}` | File download. `kind` ∈ `hvsr-csv, windows-csv, spectra-csv, summary-csv, summary-json, config-json, azimuthal-csv` (mapped to `exports/hvsr_mean.csv`, `hvsr_windows.csv`, `component_spectra.csv`, `summary.csv`, `summary.json`, `config.json`, `azimuthal.csv`). `404` when the engine did not produce the file (e.g. azimuthal analysis disabled), `409` while the analysis is not finished. |
| GET | `/analyses/{a}/figure?figure=hvsr&format=png&theme=light` | Asks the engine to render `figure` ∈ `hvsr, spectra, windows, azimuthal, peak_distribution` as `png|svg|pdf` into `exports/` and downloads it |
| POST | `/analyses/{a}/report` | Starts the PDF report job → `202 {job, analysis}`; the context sent to the engine contains project, station, recording (incl. validation), source files with sha256, processing steps of the run, and the app version. `409` while a report job is running. |
| GET | `/analyses/{a}/report` | Downloads `report.pdf` (`409` while generating, `404` when none exists) |

Download filenames are `<recording>_<analysis>_<file>` with unsafe characters replaced by `_`.

### Batches
| Method | Path | Body / notes |
|---|---|---|
| POST | `/projects/{p}/batches` | `{name, preset_id?, recording_ids[], run_steps?: true}` → 201 batch (`items[]` with `status`, `run_id`, `analysis_id`, `error`, `progress`, `summary`; `counts{total,queued,running,done,failed,skipped,cancelled}`) |
| GET | `/batches/{b}` | Returns the batch **and advances it** (see below) |
| POST | `/batches/{b}/cancel` | Cancels the current engine job, marks remaining items `cancelled` |
| DELETE | `/batches/{b}` | |

**How batches advance.** There is no queue worker (the single launcher only starts PHP and Python).
`App\Services\Batches\BatchAdvancer::advance()` runs on creation and on every `GET /batches/{b}`
poll from the SPA. Items execute strictly one at a time: if `run_steps` is true and the preset has
`steps`, a processing run is created first; when it finishes, an HVSR analysis with the preset's
`hvsr_params` is submitted; when that finishes the item is `done` and the next item starts. Any
error — engine failure, validation problem, failed job — marks that item `failed` with its message
and the batch **continues with the next item**. The batch is `done` when no item is queued or
running. Because each poll can advance several states when jobs complete quickly, the SPA should
poll every ~1–2 s while `status` is `queued|running`.

### Comparison
| Method | Path | Body / notes |
|---|---|---|
| POST | `/projects/{p}/compare` | `{analysis_ids[]}` → `[{analysis_id, name, recording_name, station_code, run_name, mean_method, band, frequency[], curve[], lower[], upper[], peak, peak_status, windows{accepted,total}, sesame{...}, quality_flags[], params{window_length_s, smoothing, horizontal_method}}]`. Unfinished or unknown analyses are returned as `{analysis_id, error}` entries instead of failing the whole request. |

## Database tables

`projects`, `stations`, `recordings`, `recording_files`, `uploads`, `processing_presets`,
`processing_runs`, `analyses`, `batches`, `batch_items`, `activity_log`, `settings`
(migration `database/migrations/2026_01_01_000001_create_hvsr_tables.php`). JSON columns hold
import settings, validation issues, processing steps, HVSR parameters, window overrides, result
summaries and activity details; every processing decision is therefore recorded next to the result
files, and `analysis.rerun` reproduces an analysis from the stored parameters and seed.

## Testing

`php artisan test` — 40 feature/unit tests run against an in-memory SQLite database with
`App\Services\Engine\FakeEngineClient` bound to `EngineClientInterface`. The fake answers with
contract-shaped payloads, writes stand-in result files and simulates job progress (`pollsToFinish`,
`failJobs`, `down`, `importBlocking`), so the whole API — import, runs, analyses, exports, reports,
batches with a failing item, comparison, engine-down 503, path traversal — is covered without the
Python service.

## Parity additions (added 2026-09-16)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/analyses/{a}/survey` | survey/report details `{date, client, place_id, address, latitude, longitude, datum, elevation_m, weather, notes, photos[]}` |
| PUT/POST | `/api/analyses/{a}/survey` | multipart: any of those fields + `photo1`/`photo2` (jpg/png ≤ 10 MB), `caption1`/`caption2`, `remove_photo1`/`remove_photo2`; photos are stored under `analyses/<ulid>/survey/photoN.<ext>`; the report context carries `survey` with absolute photo paths |
| GET | `/api/analyses/{a}/survey/photo/{1|2}` | the stored photo |
| PUT | `/api/analyses/{a}/models` | `{models: [{id?, name, layers[], vs30_offset_m?, created_at?}]}` replaces the stored forward models (ids generated when missing) |
| POST | `/api/engine/model-hvsr` | proxies the engine `POST /model/hvsr`; validates numeric layers, last layer = half-space (`thickness_m: null`), Vp or Poisson per layer, ν ∈ (0, 0.5) |
| POST | `/api/projects/{p}/curves` | multipart `file` (.hv/.csv/.txt/.dat ≤ 20 MB) → engine `POST /curves/import` → `{frequency, values, lower, upper, name, format}`; the staged file is removed afterwards |
| GET | `/api/analyses/{a}/exports/geopsy-hv` | `exports/hvsr_mean.hv` (Geopsy .hv) |
| GET | `/api/analyses/{a}/exports/windows-json` | window set `{format, analysis, recording, mode, params, windows:[{start_s, end_s, accepted, reason}]}` |
| POST | `/api/recordings/{r}/windows/import` | body = a window set → `{mode:"custom", custom:[[start,end],…], window_overrides:{i:{accepted:false,reason:"manual"}}, counts}` (inverted/out-of-record windows skipped, ends clipped to the record) |
| GET | `/api/recordings/{r}/samples?component=n|e|z&run=&t_start=&t_end=` | full-resolution samples `{fs, t0, n, values}` for the seismogram player (≤ 4,000,000 samples; 422 if the engine had to down-sample) |
| GET | `/api/projects/{p}/backup` | streams `<slug>-backup.zip`: `database.json` (format `quakelogic-hvsr-studio-backup/1`, every row of the project) + the project folder under `project/` (staged uploads excluded) |
| POST | `/api/projects/restore` | multipart `file` (zip ≤ 4 GB) → recreates the project under a free slug, fresh ids, ULIDs kept unless they collide, absolute paths rewritten to the new folder → 201 with the project tree |

`POST /api/projects/{p}/recordings` now accepts `import.format` ∈ `ascii, mseed, saf, seismic` (`saf` passes `import.saf`, `seismic` uses the `import.mseed` trace mapping). `POST /api/recordings/{r}/windows` passes `params.windows` (`mode` fixed/auto_variable/custom, `custom` list) through to the engine; window items carry `length_s` and `color_index`.

Migration `2026_09_16_000001_add_survey_and_models_to_analyses` adds `analyses.survey` and `analyses.models` (JSON, guarded with `hasColumn`).
