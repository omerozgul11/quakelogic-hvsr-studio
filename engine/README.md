# QuakeLogic HVSR Studio — Python engine

* `hvsr_engine/` — pure scientific package (NumPy/SciPy/ObsPy/pandas). No HTTP, no database.
* `hvsr_service/` — FastAPI service on 127.0.0.1:8765 used by the Laravel application.
* `tests/` — pytest suite (`.venv/bin/python -m pytest tests`).
* `validation/` — analytic reference cases and the hvsrpy cross-check (`run_validation.py`),
  and the generator of the synthetic example datasets (`make_examples.py`).

Setup: `uv sync --extra dev` (add `--extra validation` for the hvsrpy cross-check).
Algorithms: `../docs/hvsr-algorithms.md`. Validation results: `../docs/validation.md`.
