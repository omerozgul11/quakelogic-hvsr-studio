# Launcher

`launch.py` is the single entry point. It:

1. locates PHP and the Python engine environment (bundled `runtime/<platform>/` first, then `engine/.venv`, then PATH);
2. creates `.env` from `.env.example` on first run and generates the application key;
3. runs `php artisan hvsr:setup` (SQLite migrations + built-in presets, idempotent);
4. starts the processing engine (`python -m hvsr_service`) with a per-session shared token;
5. starts the web server (`php artisan serve`) bound to 127.0.0.1;
6. waits for both health checks, opens the browser, and stops both processes when the launcher exits.

Wrappers: `HVSR Studio.bat` (Windows, repo/dist root), `launcher/hvsr-studio.sh` (Linux),
`launcher/hvsr-studio.command` (macOS). Options: `--port`, `--engine-port`, `--no-browser`, `--debug`, `--workers`.
Logs: `data/logs/{launcher,engine,web}.log`.
