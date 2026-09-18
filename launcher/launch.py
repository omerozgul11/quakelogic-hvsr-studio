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
# Helper processes must never open console windows of their own (the hidden launcher has none).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0
LOG_FILE: Path | None = None


def log(message: str) -> None:
    """Print to the console (when there is one) and append to the launcher log file."""
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        pass
    if LOG_FILE is not None:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


def set_log_file(path: Path) -> None:
    global LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE = path


def run_quiet(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: float = 300) -> str:
    """Run a helper command without a console window; raise RuntimeError with its output on failure."""
    result = subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env, capture_output=True, text=True,
                            timeout=timeout, creationflags=NO_WINDOW, encoding="utf-8", errors="replace")
    output = (result.stdout or "") + (result.stderr or "")
    for line in output.strip().splitlines()[-40:]:
        log(f"  | {line}")
    if result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-12:])
        raise RuntimeError(f"`{Path(cmd[0]).name} {' '.join(cmd[1:3])}` failed (exit {result.returncode}):\n{tail}")
    return output


def has_console() -> bool:
    if not IS_WINDOWS:
        return True
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:  # noqa: BLE001
        return True
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
            capture_output=True, timeout=120, env=env, creationflags=NO_WINDOW,
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
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False,
                           creationflags=NO_WINDOW)
        else:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    except OSError:
        pass


def find_app_browser() -> Path | None:
    """A Chromium-based browser able to open the interface as a standalone application window.

    Order: $HVSR_BROWSER → Microsoft Edge (ships with Windows 10/11) → Google Chrome → Chromium.
    """
    override = os.environ.get("HVSR_BROWSER")
    if override and Path(override).exists():
        return Path(override)
    candidates: list[Path] = []
    if IS_WINDOWS:
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidates += [Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                               Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                               Path(base) / "Chromium" / "Application" / "chrome.exe"]
    elif sys.platform == "darwin":
        candidates += [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                       Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                       Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
                       Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")]
    for name in ("msedge", "microsoft-edge", "microsoft-edge-stable", "google-chrome", "google-chrome-stable",
                 "chromium", "chromium-browser", "brave-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for path in candidates:
        if path.exists():
            return path
    return None


def open_app_window(url: str, data_dir: Path, log) -> subprocess.Popen | None:
    """Open the interface in its own application window (no tabs, no address bar).

    A private browser profile under the data directory makes the window an independent
    process, so the launcher can shut the services down when the window is closed even
    when the same browser is already open for ordinary web browsing.
    """
    browser = find_app_browser()
    if browser is None:
        return None
    profile = data_dir / "app-window-profile"
    profile.mkdir(parents=True, exist_ok=True)
    cmd = [str(browser), f"--app={url}", f"--user-data-dir={profile}", "--window-size=1500,950",
           "--no-first-run", "--no-default-browser-check", "--disable-session-crashed-bubble",
           "--disable-features=Translate,msEdgeShoppingUI,msHub", "--disable-extensions",
           "--class=QuakeLogicHVSRStudio"]
    kwargs: dict = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if IS_WINDOWS:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        log(f"Could not open the application window ({exc}); falling back to the default browser.")
        return None
    log(f"Application window opened with {browser.name}")
    return proc


def notify_error(message: str) -> None:
    """Show start-up errors in a dialog when there is no console to read them in."""
    if IS_WINDOWS and (not has_console() or sys.executable.lower().endswith("pythonw.exe") or os.environ.get("HVSR_QUIET")):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "QuakeLogic HVSR Studio", 0x10)
        except Exception:  # noqa: BLE001
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


def generate_app_key(php: Path, env: dict[str, str]) -> str:
    output = run_quiet([str(php), "artisan", "key:generate", "--show", "--no-interaction"], APP_ROOT, env)
    key = output.strip().splitlines()[-1].strip()
    if not key.startswith("base64:"):
        raise RuntimeError("Could not generate an application key")
    return key


def ensure_env_file(php: Path, env: dict[str, str], log) -> tuple[Path, dict[str, str]]:
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
            run_quiet([str(php), "artisan", "key:generate", "--force", "--no-interaction"], APP_ROOT, env)
        return env_path, overrides

    user_root = user_data_root()
    user_root.mkdir(parents=True, exist_ok=True)
    env_path = user_root / "launcher.env"
    values = read_env_file(env_path)
    if not values.get("APP_KEY"):
        log(f"Application folder is read-only; keeping settings in {user_root}")
        values["APP_KEY"] = generate_app_key(php, env)
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
    run_quiet([str(php), "artisan", "hvsr:setup", "--no-interaction"], APP_ROOT, env)


def php_environment(php: Path) -> dict[str, str]:
    """Environment for every PHP process: our ini overrides + an absolute extension_dir for the bundled PHP.

    PHP resolves a relative `extension_dir` against the current directory, not against php.exe,
    so a generated ini pins it to the bundled `ext` folder. Both directories are handed to PHP
    through PHP_INI_SCAN_DIR, which also reaches the `php -S` worker that `artisan serve` spawns.
    """
    env = dict(os.environ)
    scan_dirs = [str(APP_ROOT / "launcher" / "php.d")]
    ext_dir = php.parent / "ext"
    if ext_dir.is_dir():
        ini_dir = user_data_root() / "php.d"
        try:
            ini_dir.mkdir(parents=True, exist_ok=True)
            (ini_dir / "hvsr-paths.ini").write_text(
                f'; generated by the QuakeLogic HVSR Studio launcher\nextension_dir = "{ext_dir}"\n', encoding="utf-8")
            scan_dirs.append(str(ini_dir))
        except OSError:
            pass
    env["PHP_INI_SCAN_DIR"] = os.pathsep.join(scan_dirs)
    env["PHP_CLI_SERVER_WORKERS"] = "6"
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start QuakeLogic HVSR Studio")
    parser.add_argument("--port", type=int, default=None, help="web port (default from .env APP_URL or 8090)")
    parser.add_argument("--engine-port", type=int, default=None, help="engine port (default from .env or 8765)")
    parser.add_argument("--no-browser", action="store_true", help="do not open any window or browser")
    parser.add_argument("--browser", action="store_true", help="open in the default web browser instead of the application window")
    parser.add_argument("--debug", action="store_true", help="echo service output to this console")
    parser.add_argument("--workers", type=int, default=None, help="engine worker threads")
    args = parser.parse_args(argv)

    set_log_file(user_data_root() / "logs" / "launcher.log")
    log("QuakeLogic HVSR Studio - launcher")
    log(f"Application root: {APP_ROOT}")
    log(f"Interpreter: {sys.executable}")

    php = find_php()
    if php is None:
        message = ("PHP was not found. Install PHP 8.3+ or place a bundled runtime in "
                   f"runtime/{platform_dir()}/php/. See docs/user-guide.md.")
        log(f"ERROR: {message}")
        notify_error(message)
        return 2
    python = find_python()
    if python is None:
        message = ("No Python environment with the HVSR engine was found. Run scripts/setup-dev "
                   f"or place a bundled runtime in runtime/{platform_dir()}/python/.")
        log(f"ERROR: {message}")
        notify_error(message)
        return 2
    log(f"PHP:    {php}")
    log(f"Python: {python}")

    php_env = php_environment(php)
    env_path, overrides = ensure_env_file(php, php_env, log)
    dotenv = read_env_file(env_path)
    dotenv.update(overrides)

    data_dir = Path(os.environ.get("HVSR_DATA_DIR") or dotenv.get("HVSR_DATA_DIR") or "data")
    if not data_dir.is_absolute():
        data_dir = (APP_ROOT / data_dir).resolve()
    logs_dir = data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    set_log_file(logs_dir / "launcher.log")

    preferred_web = args.port or url_port(dotenv.get("APP_URL"), DEFAULT_WEB_PORT)
    preferred_engine = args.engine_port or url_port(dotenv.get("HVSR_ENGINE_URL"), DEFAULT_ENGINE_PORT)

    # Already running? Then just open the browser.
    status = http_json(f"http://127.0.0.1:{preferred_web}/api/app/status")
    if status and isinstance(status, dict) and status.get("app_version"):
        log(f"HVSR Studio is already running on port {preferred_web}; opening a new window.")
        if not args.no_browser:
            existing_url = f"http://127.0.0.1:{preferred_web}/"
            data_dir_hint = Path(os.environ.get("HVSR_DATA_DIR") or dotenv.get("HVSR_DATA_DIR") or "data")
            if not data_dir_hint.is_absolute():
                data_dir_hint = (APP_ROOT / data_dir_hint).resolve()
            window = None if args.browser else open_app_window(existing_url, data_dir_hint, log)
            if window is None:
                webbrowser.open(existing_url)
            else:
                window.wait()
        return 0

    web_port = pick_port(preferred_web)
    engine_port = pick_port(preferred_engine if preferred_engine != web_port else preferred_engine + 1)
    token = secrets.token_urlsafe(24)

    child_env = dict(php_env)
    child_env.update(overrides)
    child_env.update({
        "HVSR_DATA_DIR": str(data_dir),
        "DB_DATABASE": overrides.get("DB_DATABASE", str(data_dir / "hvsr-studio.sqlite")),
        "HVSR_ENGINE_URL": f"http://127.0.0.1:{engine_port}",
        "HVSR_ENGINE_TOKEN": token,
        "APP_URL": f"http://127.0.0.1:{web_port}",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(APP_ROOT / "engine"),
        "MPLBACKEND": "Agg",
    })

    try:
        run_setup(php, child_env, log)
    except RuntimeError as exc:
        log(f"ERROR: database setup failed: {exc}")
        notify_error(f"Database setup failed.\n\n{exc}\n\nDetails: {LOG_FILE}")
        return 3

    engine_cmd = [str(python), "-m", "hvsr_service", "--host", "127.0.0.1", "--port", str(engine_port), "--token", token]
    if args.workers:
        engine_cmd += ["--workers", str(args.workers)]
    php_cmd = [str(php), "artisan", "serve", "--host=127.0.0.1", f"--port={web_port}", "--no-reload"]

    popen_kwargs: dict = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_env)
    if IS_WINDOWS:
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | NO_WINDOW

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
        window_proc: subprocess.Popen | None = None
        if not args.no_browser:
            window_proc = None if args.browser else open_app_window(url, data_dir, log)
            if window_proc is None:
                webbrowser.open(url)
        if window_proc is not None:
            print("\n  Close the QuakeLogic HVSR Studio window to stop the application.\n", flush=True)
        else:
            print("\n  Close this window (or press Ctrl+C) to stop QuakeLogic HVSR Studio.\n", flush=True)

        stop_requested = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop_requested.set())
        while not stop_requested.is_set():
            time.sleep(1)
            if window_proc is not None and window_proc.poll() is not None:
                log("Application window closed")
                break
            for proc, name in ((engine_proc, "processing engine"), (php_proc, "web server")):
                if proc.poll() is not None:
                    raise RuntimeError(f"The {name} stopped unexpectedly (exit code {proc.returncode}). See data/logs.")
    except KeyboardInterrupt:
        print()
        log("Shutting down")
    except RuntimeError as exc:
        log(f"ERROR: {exc}")
        notify_error(f"{exc}\n\nDetails: {LOG_FILE}")
        exit_code = 1
    finally:
        shutdown()
    return exit_code


def entry() -> int:
    """Never exit silently: any unexpected failure is logged and shown in a dialog."""
    try:
        return main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001
        import traceback
        details = traceback.format_exc()
        log("FATAL: " + details)
        notify_error(f"QuakeLogic HVSR Studio could not start.\n\n{type(exc).__name__}: {exc}\n\nDetails: {LOG_FILE}")
        return 1


if __name__ == "__main__":
    sys.exit(entry())
