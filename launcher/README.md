# Launcher

`launch.py` is the single entry point. It:

1. locates PHP and the Python engine environment (bundled `runtime/<platform>/` first, then `engine/.venv`, then PATH);
2. creates `.env` from `.env.example` on first run and generates the application key;
3. runs `php artisan hvsr:setup` (SQLite migrations + built-in presets, idempotent);
4. starts the processing engine (`python -m hvsr_service`) with a per-session shared token;
5. starts a pool of PHP web back ends (`php -S` on private ports, see `webpool.py`) behind a threaded reverse proxy on the public port, so long uploads or engine calls never block status polls or the heartbeat (PHP's built-in server handles one request at a time per process and cannot fork on Windows);
6. waits for both health checks, opens the interface in a dedicated application window (Edge/Chrome/Chromium
   `--app` mode with a private profile; falls back to the default browser), and stops both processes when that
   window is closed or the launcher exits.

Wrappers: `HVSR Studio.vbs` (Windows, hidden console, via pythonw.exe), `HVSR Studio.bat` (Windows, console), `launcher/hvsr-studio.sh` (Linux),
`launcher/hvsr-studio.command` (macOS). Options: `--port`, `--engine-port`, `--browser` (tab instead of app window), `--no-browser`, `--debug`, `--workers`.
Environment: `HVSR_BROWSER` = path to a Chromium-based browser to use for the window; `HVSR_QUIET=1` shows fatal errors in a dialog.
Logs: `data/logs/{launcher,engine,web}.log`.
