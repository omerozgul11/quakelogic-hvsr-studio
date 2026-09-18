#!/usr/bin/env python3
"""QuakeLogic HVSR Studio — single launcher.

Starts the Python processing service and the Laravel web server, waits until
both answer their health checks, opens the browser, and shuts everything down
again when this process exits (Ctrl+C / window closed / SIGTERM).

Everything binds to 127.0.0.1. No network access is required.

Runtime discovery order
  PHP:    $HVSR_PHP  → runtime/<platform>/php/php[.exe]  → `php` on PATH
  Python: $HVSR_PYTHON → runtime/<platform>/python/python[.exe] (or bin/python3)
          → engine/.venv/{Scripts,bin}/python[.exe] → the interpreter running this script
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = os.name == "nt"
DEFAULT_WEB_PORT = 8090
DEFAULT_ENGINE_PORT = 8765


def platform_dir() -> str:
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    if IS_WINDOWS:
        return f"win-{arch}"
    if sys.platform == "darwin":
        return f"macos-{arch}"
    return f"linux-{arch}"


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def find_php() -> Path | None:
    candidate = os.environ.get("HVSR_PHP")
    if candidate and Path(candidate).exists():
        return Path(candidate)
    bundled = APP_ROOT / "runtime" / platform_dir() / "php" / ("php.exe" if IS_WINDOWS else "php")
    if bundled.exists():
        return bundled
    found = shutil.which("php")
    return Path(found) if found else None


def python_has_service(python: Path) -> bool:
    try:
        env = dict(os.environ, PYTHONPATH=str(APP_ROOT / "engine"))
        result = subprocess.run(
            [str(python), "-c", "import hvsr_service, hvsr_engine, numpy, scipy, obspy"],
            capture_output=True, timeout=60, env=env,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def find_python() -> Path | None:
    candidate = os.environ.get("HVSR_PYTHON")
    if candidate and Path(candidate).exists():
        return Path(candidate)
    runtime = APP_ROOT / "runtime" / platform_dir() / "python"
    venv = APP_ROOT / "engine" / ".venv"
    candidates = [
        runtime / "python.exe", runtime / "bin" / "python3", runtime / "bin" / "python",
        venv / "Scripts" / "python.exe", venv / "bin" / "python",
        Path(sys.executable),
    ]
    for path in candidates:
        if path.exists() and python_has_service(path):
            return path
    return None


def url_port(url: str | None, default: int) -> int:
    try:
        from urllib.parse import urlparse
        port = urlparse(url or "").port
        return int(port) if port else default
    except ValueError:
        return default


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def pick_port(preferred: int) -> int:
    port = preferred
    while not port_is_free(port):
        port += 1
        if port > preferred + 50:
            raise RuntimeError(f"No free port found near {preferred}")
    return port


def http_json(url: str, headers: dict[str, str] | None = None, timeout: float = 2.0) -> dict | None:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (localhost only)
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def wait_for(name: str, probe, timeout: float, process: subprocess.Popen | None, log) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"{name} exited early with code {process.returncode}. See the log files in data/logs.")
        data = probe()
        if data:
            return data
        time.sleep(0.4)
    raise RuntimeError(f"{name} did not become ready within {timeout:.0f} s. See the log files in data/logs.")


def stream_output(process: subprocess.Popen, log_path: Path, echo: bool, prefix: str) -> threading.Thread:
    def pump():
        with log_path.open("a", encoding="utf-8", errors="replace") as handle:
            assert process.stdout is not None
            for line in iter(process.stdout.readline, b""):
                text = line.decode("utf-8", errors="replace")
                handle.write(text)
                handle.flush()
                if echo:
                    sys.stdout.write(f"[{prefix}] {text}")
                    sys.stdout.flush()

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()
    return thread


def terminate(process: subprocess.Popen | None, name: str, log) -> None:
    if process is None or process.poll() is not None:
        return
    log(f"Stopping {name} (pid {process.pid})")
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    except OSError:
        pass


def is_writable(directory: Path) -> bool:
    try:
        probe = directory / f".write-test-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def user_data_root() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "QuakeLogic" / "HVSR Studio"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "QuakeLogic HVSR Studio"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "quakelogic-hvsr-studio"


def generate_app_key(php: Path) -> str:
    result = subprocess.run([str(php), "artisan", "key:generate", "--show", "--no-interaction"],
                            cwd=APP_ROOT, capture_output=True, text=True, check=True)
    key = result.stdout.strip().splitlines()[-1].strip()
    if not key.startswith("base64:"):
        raise RuntimeError("Could not generate an application key")
    return key


def ensure_env_file(php: Path, log) -> tuple[Path, dict[str, str]]:
    """Return (env file path, extra environment overrides).

    When the application folder is writable (portable / per-user install) the
    standard Laravel .env file is used.  When it is read-only (e.g. an
    all-users install under Program Files) the launcher keeps its settings in
    the per-user data folder instead and passes them as environment variables,
    which take precedence over .env inside Laravel.
    """
    overrides: dict[str, str] = {}
    if is_writable(APP_ROOT) and is_writable(APP_ROOT / "storage"):
        env_path = APP_ROOT / ".env"
        if not env_path.exists():
            example = APP_ROOT / ".env.example"
            if not example.exists():
                raise RuntimeError(".env.example is missing; the application files are incomplete.")
            shutil.copyfile(example, env_path)
            log("Created .env from .env.example")
        values = read_env_file(env_path)
        if not values.get("APP_KEY"):
            log("Generating application key")
            subprocess.run([str(php), "artisan", "key:generate", "--force", "--no-interaction"], cwd=APP_ROOT, check=True)
        return env_path, overrides

    user_root = user_data_root()
    user_root.mkdir(parents=True, exist_ok=True)
    env_path = user_root / "launcher.env"
    values = read_env_file(env_path)
    if not values.get("APP_KEY"):
        log(f"Application folder is read-only; keeping settings in {user_root}")
        values["APP_KEY"] = generate_app_key(php)
        env_path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    storage = user_root / "storage"
    for sub in ("app", "framework/cache/data", "framework/sessions", "framework/views", "logs"):
        (storage / sub).mkdir(parents=True, exist_ok=True)
    overrides.update({
        "APP_KEY": values["APP_KEY"],
        "LARAVEL_STORAGE_PATH": str(storage),
        "HVSR_DATA_DIR": str(user_root / "data"),
        "DB_DATABASE": str(user_root / "data" / "hvsr-studio.sqlite"),
        "APP_CONFIG_CACHE": str(storage / "framework" / "cache" / "config.php"),
    })
    return env_path, overrides


def run_setup(php: Path, env: dict[str, str], log) -> None:
    log("Preparing database and presets")
    subprocess.run([str(php), "artisan", "hvsr:setup", "--no-interaction"], cwd=APP_ROOT, env=env, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start QuakeLogic HVSR Studio")
    parser.add_argument("--port", type=int, default=None, help="web port (default from .env APP_URL or 8090)")
    parser.add_argument("--engine-port", type=int, default=None, help="engine port (default from .env or 8765)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--debug", action="store_true", help="echo service output to this console")
    parser.add_argument("--workers", type=int, default=None, help="engine worker threads")
    args = parser.parse_args(argv)

    def log(message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp}] {message}", flush=True)

    print("QuakeLogic HVSR Studio — launcher")
    print(f"Application root: {APP_ROOT}")

    php = find_php()
    if php is None:
        print("ERROR: PHP was not found. Install PHP 8.3+ or place a bundled runtime in "
              f"runtime/{platform_dir()}/php/. See docs/user-guide.md.")
        return 2
    python = find_python()
    if python is None:
        print("ERROR: no Python environment with the HVSR engine was found. Run scripts/setup-dev "
              f"or place a bundled runtime in runtime/{platform_dir()}/python/.")
        return 2
    log(f"PHP:    {php}")
    log(f"Python: {python}")

    env_path, overrides = ensure_env_file(php, log)
    dotenv = read_env_file(env_path)
    dotenv.update(overrides)

    data_dir = Path(os.environ.get("HVSR_DATA_DIR") or dotenv.get("HVSR_DATA_DIR") or "data")
    if not data_dir.is_absolute():
        data_dir = (APP_ROOT / data_dir).resolve()
    logs_dir = data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    preferred_web = args.port or url_port(dotenv.get("APP_URL"), DEFAULT_WEB_PORT)
    preferred_engine = args.engine_port or url_port(dotenv.get("HVSR_ENGINE_URL"), DEFAULT_ENGINE_PORT)

    # Already running? Then just open the browser.
    status = http_json(f"http://127.0.0.1:{preferred_web}/api/app/status")
    if status and isinstance(status, dict) and status.get("app_version"):
        log(f"HVSR Studio is already running on port {preferred_web}; opening the browser.")
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{preferred_web}/")
        return 0

    web_port = pick_port(preferred_web)
    engine_port = pick_port(preferred_engine if preferred_engine != web_port else preferred_engine + 1)
    token = secrets.token_urlsafe(24)

    child_env = dict(os.environ)
    child_env.update(overrides)
    child_env.update({
        "HVSR_DATA_DIR": str(data_dir),
        "DB_DATABASE": overrides.get("DB_DATABASE", str(data_dir / "hvsr-studio.sqlite")),
        "HVSR_ENGINE_URL": f"http://127.0.0.1:{engine_port}",
        "HVSR_ENGINE_TOKEN": token,
        "APP_URL": f"http://127.0.0.1:{web_port}",
        "PHP_CLI_SERVER_WORKERS": "6",
        "PHP_INI_SCAN_DIR": str(APP_ROOT / "launcher" / "php.d"),
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(APP_ROOT / "engine"),
        "MPLBACKEND": "Agg",
    })

    try:
        run_setup(php, child_env, log)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: database setup failed (exit {exc.returncode}).")
        return 3

    engine_cmd = [str(python), "-m", "hvsr_service", "--host", "127.0.0.1", "--port", str(engine_port), "--token", token]
    if args.workers:
        engine_cmd += ["--workers", str(args.workers)]
    php_cmd = [str(php), "artisan", "serve", "--host=127.0.0.1", f"--port={web_port}", "--no-reload"]

    popen_kwargs: dict = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_env)
    if IS_WINDOWS:
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    engine_proc: subprocess.Popen | None = None
    php_proc: subprocess.Popen | None = None
    exit_code = 0

    def shutdown(*_):
        terminate(php_proc, "web server", log)
        terminate(engine_proc, "processing engine", log)

    try:
        log(f"Starting processing engine on 127.0.0.1:{engine_port}")
        engine_proc = subprocess.Popen(engine_cmd, cwd=APP_ROOT / "engine", **popen_kwargs)
        stream_output(engine_proc, logs_dir / "engine.log", args.debug, "engine")

        log(f"Starting web server on 127.0.0.1:{web_port}")
        php_proc = subprocess.Popen(php_cmd, cwd=APP_ROOT, **popen_kwargs)
        stream_output(php_proc, logs_dir / "web.log", args.debug, "web")

        wait_for("Processing engine", lambda: http_json(f"http://127.0.0.1:{engine_port}/health", {"X-Engine-Token": token}),
                 90, engine_proc, log)
        wait_for("Web server", lambda: http_json(f"http://127.0.0.1:{web_port}/api/app/status"), 60, php_proc, log)

        url = f"http://127.0.0.1:{web_port}/"
        log(f"Ready: {url}")
        print("\n  Close this window (or press Ctrl+C) to stop QuakeLogic HVSR Studio.\n", flush=True)
        if not args.no_browser:
            webbrowser.open(url)

        stop_requested = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop_requested.set())
        while not stop_requested.is_set():
            time.sleep(1)
            for proc, name in ((engine_proc, "processing engine"), (php_proc, "web server")):
                if proc.poll() is not None:
                    raise RuntimeError(f"The {name} stopped unexpectedly (exit code {proc.returncode}). See data/logs.")
    except KeyboardInterrupt:
        print()
        log("Shutting down")
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        exit_code = 1
    finally:
        shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
