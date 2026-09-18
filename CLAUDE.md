# QuakeLogic HVSR Studio

Standalone, offline desktop-style application for HVSR (horizontal-to-vertical spectral ratio)
analysis of three-component seismic recordings. Own project; not part of the enterprise app.

Read `docs/architecture.md` first — it is the interface contract between the three tiers.

* Laravel 13 / PHP 8.4 (repo root) — SQLite app DB, project folders, JSON API. No numerics in PHP.
* `engine/` — Python 3.12: `hvsr_engine` (pure science, pytest) + `hvsr_service` (FastAPI on 127.0.0.1:8765).
* `resources/js` — Vue 3 + TypeScript + Tailwind 4 + Plotly SPA. No CDN assets; everything bundled.

Dev toolchain on this Linux host: `source .tools/env.sh` (static PHP 8.4, Composer, Node 24, uv).
Python: `engine/.venv/bin/python` (created by `uv sync --extra dev` in `engine/`).
Run PHP tests with `php artisan test`, engine tests with `engine/.venv/bin/python -m pytest engine/tests`.

Rules: bind to localhost only; never call the network at runtime; never silently interpolate,
resample, rotate or substitute data; record every processing operation and parameter.
