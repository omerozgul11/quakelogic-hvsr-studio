#!/usr/bin/env python3
"""Build a standalone Windows x64 distribution of QuakeLogic HVSR Studio.

Runs on Windows (recommended) or on Linux/macOS (cross-build: the Python
dependencies are fetched as Windows wheels; PHP vendor code is pure PHP).

Steps
  1. build the frontend (npm ci + npm run build)            [needs Node on PATH]
  2. copy the application into <out>/QuakeLogic-HVSR-Studio
  3. composer install --no-dev inside the stage             [needs PHP + composer.phar]
  4. download PHP <series> NTS x64 (windows.php.net) → runtime/win-x64/php  + php.ini
  5. download python-build-standalone <series> x64 → runtime/win-x64/python
  6. install engine/requirements.lock.txt into that Python (Windows wheels only)
  7. download vc_redist.x64.exe for the installer
  8. zip the stage → <out>/QuakeLogic-HVSR-Studio-<version>-win-x64.zip

Afterwards `packaging/windows/installer.iss` can be compiled with Inno Setup 6.

Internet access is needed at BUILD time only; the produced distribution runs offline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = os.name == "nt"

COPY_INCLUDE = [
    "app", "bootstrap", "config", "database", "public", "resources/views", "routes", "storage",
    "artisan", "composer.json", "composer.lock", ".env.example",
    "engine/hvsr_engine", "engine/hvsr_service", "engine/pyproject.toml", "engine/requirements.lock.txt", "engine/README.md",
    "launcher", "docs", "examples", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "HVSR Studio.bat", "HVSR Studio.vbs",
]
COPY_EXCLUDE_DIRS = {"__pycache__", "node_modules", ".pytest_cache", ".venv", "logs"}
STORAGE_DIRS = ["storage/app/private", "storage/app/public", "storage/framework/cache/data",
                "storage/framework/sessions", "storage/framework/testing", "storage/framework/views",
                "storage/logs", "bootstrap/cache"]


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    log("$ " + " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=cwd or ROOT, env=env, check=True)


def download(url: str, dest: Path, sha256: str | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (sha256 is None or file_sha256(dest) == sha256):
        log(f"cached {dest.name}")
        return dest
    log(f"downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "QuakeLogic-HVSR-Studio-packager/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, dest.open("wb") as handle:  # noqa: S310
        shutil.copyfileobj(response, handle)
    if sha256 and file_sha256(dest) != sha256:
        dest.unlink()
        raise RuntimeError(f"Checksum mismatch for {dest.name}")
    return dest


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "QuakeLogic-HVSR-Studio-packager/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def app_version() -> str:
    text = (ROOT / "engine" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else "0.0.0"


def find_php() -> str:
    for candidate in (os.environ.get("HVSR_PHP"), str(ROOT / "runtime" / "linux-x64" / "php" / "php"),
                      str(ROOT / "runtime" / "win-x64" / "php" / "php.exe"), shutil.which("php")):
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("PHP not found (set HVSR_PHP or put php on PATH)")


def find_composer() -> list[str]:
    php = find_php()
    for candidate in (ROOT / ".tools" / "composer.phar", ROOT / "composer.phar"):
        if candidate.exists():
            return [php, str(candidate)]
    # Always drive Composer through PHP + composer.phar (a .bat shim cannot be exec'd reliably on Windows).
    phar = download("https://getcomposer.org/download/latest-stable/composer.phar", ROOT / ".tools" / "composer.phar")
    return [php, str(phar)]


def find_uv() -> str | None:
    for candidate in (str(ROOT / ".tools" / "uv"), str(ROOT / ".tools" / "uv.exe"), shutil.which("uv")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        if any(part in COPY_EXCLUDE_DIRS for part in rel.parts):
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def stage_application(stage: Path, skip_frontend: bool) -> None:
    node_env = dict(os.environ)
    tools_node = ROOT / ".tools" / "node" / "bin"
    if tools_node.exists():
        node_env["PATH"] = f"{tools_node}{os.pathsep}{node_env.get('PATH', '')}"
    if not skip_frontend:
        log("Building frontend")
        npm = "npm.cmd" if IS_WINDOWS else "npm"
        run([npm, "ci", "--no-audit", "--no-fund"], env=node_env)
        run([npm, "run", "build"], env=node_env)
    if not (ROOT / "public" / "build" / "manifest.json").exists():
        raise RuntimeError("public/build/manifest.json missing — build the frontend first")

    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for item in COPY_INCLUDE:
        src = ROOT / item
        if not src.exists():
            log(f"skipping missing {item}")
            continue
        copy_tree(src, stage / item)
    for rel in STORAGE_DIRS:
        target = stage / rel
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
    for junk in ("storage/logs/laravel.log",):
        path = stage / junk
        if path.exists():
            path.unlink()
    # Remove developer caches; package:discover regenerates packages.php/services.php for the
    # production vendor set (the dev copies reference dev-only packages such as laravel/pail).
    for cached in (stage / "bootstrap" / "cache").glob("*.php"):
        cached.unlink()
    bat = stage / "HVSR Studio.bat"
    bat.write_bytes(bat.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def composer_install(stage: Path) -> None:
    log("Installing PHP dependencies (production)")
    env = dict(os.environ, COMPOSER_HOME=str(ROOT / ".tools" / "composer-home"), COMPOSER_NO_INTERACTION="1")
    run(find_composer() + ["install", "--no-dev", "--optimize-autoloader", "--no-interaction", "--no-progress",
                           "--no-scripts"], cwd=stage, env=env)
    run([find_php(), "artisan", "package:discover", "--ansi"], cwd=stage, env=env)


def install_php(stage: Path, downloads: Path, series: str) -> None:
    log(f"Fetching PHP {series} NTS x64 for Windows")
    releases = fetch_json("https://windows.php.net/downloads/releases/releases.json")
    info = releases.get(series)
    if not info:
        raise RuntimeError(f"PHP series {series} not in releases.json (available: {', '.join(releases)})")
    key = next((k for k in info if k.startswith("nts-") and k.endswith("-x64")), None)
    if not key:
        raise RuntimeError(f"No NTS x64 build listed for PHP {series}")
    zip_info = info[key]["zip"]
    archive = download(f"https://windows.php.net/downloads/releases/{zip_info['path']}", downloads / zip_info["path"],
                       zip_info.get("sha256"))
    target = stage / "runtime" / "win-x64" / "php"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
    (target / "php.ini").write_text(
        "; QuakeLogic HVSR Studio — bundled PHP configuration\n"
        "extension_dir = \"ext\"\n"
        "extension=pdo_sqlite\nextension=sqlite3\nextension=mbstring\nextension=openssl\nextension=curl\n"
        "extension=fileinfo\nextension=zip\nextension=gd\nextension=intl\n"
        "memory_limit = 1024M\nupload_max_filesize = 4096M\npost_max_size = 4096M\nmax_execution_time = 600\n"
        "max_input_time = 600\ndate.timezone = UTC\nopcache.enable_cli = 0\n"
        "display_errors = Off\nlog_errors = On\n", encoding="utf-8")
    log(f"PHP {info['version']} staged")


def install_python(stage: Path, downloads: Path, series: str) -> Path:
    log(f"Fetching python-build-standalone {series} x64 for Windows")
    release = fetch_json("https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest")
    pattern = re.compile(rf"^cpython-{re.escape(series)}\.\d+\+\d+-x86_64-pc-windows-msvc-install_only\.tar\.gz$")
    asset = next((a for a in release["assets"] if pattern.match(a["name"])), None)
    if not asset:
        raise RuntimeError(f"No install_only asset for CPython {series} in release {release['tag_name']}")
    archive = download(asset["browser_download_url"], downloads / asset["name"])
    target = stage / "runtime" / "win-x64" / "python"
    if target.exists():
        shutil.rmtree(target)
    tmp = downloads / "python-extract"
    if tmp.exists():
        shutil.rmtree(tmp)
    with tarfile.open(archive) as tf:
        tf.extractall(tmp, filter="data")
    shutil.move(str(tmp / "python"), str(target))
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"Python {asset['name'].split('+')[0].replace('cpython-', '')} staged")
    return target


def install_python_deps(python_dir: Path, downloads: Path) -> None:
    lock = ROOT / "engine" / "requirements.lock.txt"
    site = python_dir / "Lib" / "site-packages"
    log("Installing Python dependencies (Windows wheels)")
    if IS_WINDOWS:
        subprocess.run([str(python_dir / "python.exe"), "-m", "ensurepip", "--upgrade"], check=False)
        run([python_dir / "python.exe", "-m", "pip", "install", "--no-cache-dir", "--upgrade", "pip"])
        run([python_dir / "python.exe", "-m", "pip", "install", "--no-cache-dir", "--only-binary=:all:", "-r", lock])
        return
    uv = find_uv()
    if not uv:
        raise RuntimeError("Cross-building needs `uv` (place it in .tools/ or on PATH), or run this script on Windows.")
    run([uv, "pip", "install", "--python-platform", "x86_64-pc-windows-msvc", "--python-version", "3.12",
         "--only-binary", ":all:", "--target", site, "--no-cache", "-r", lock])
    # matplotlib needs a writable config dir; the service sets MPLCONFIGDIR at runtime (launcher sets MPLBACKEND=Agg).



def make_zip(stage: Path, out: Path) -> Path:
    if out.exists():
        out.unlink()
    log(f"Zipping to {out.name}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in stage.rglob("*"):
            if path.is_file():
                zf.write(path, Path(stage.name) / path.relative_to(stage))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="dist", help="output directory (default dist/)")
    parser.add_argument("--php-series", default="8.4")
    parser.add_argument("--python-series", default="3.12")
    parser.add_argument("--skip-frontend", action="store_true", help="reuse the existing public/build")
    parser.add_argument("--skip-runtimes", action="store_true", help="do not download PHP/Python (source-only stage)")
    parser.add_argument("--no-zip", action="store_true")
    args = parser.parse_args()

    out = (ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    stage = out / "QuakeLogic-HVSR-Studio"
    downloads = out / "downloads"
    version = app_version()
    log(f"QuakeLogic HVSR Studio {version} — Windows x64 distribution → {stage}")

    stage_application(stage, args.skip_frontend)
    composer_install(stage)
    (stage / "VERSION").write_text(version + "\n", encoding="utf-8")
    if not args.skip_runtimes:
        install_php(stage, downloads, args.php_series)
        python_dir = install_python(stage, downloads, args.python_series)
        install_python_deps(python_dir, downloads)
        download("https://aka.ms/vs/17/release/vc_redist.x64.exe", downloads / "vc_redist.x64.exe")
    if not args.no_zip:
        make_zip(stage, out / f"QuakeLogic-HVSR-Studio-{version}-win-x64.zip")
    log("Done. Compile packaging/windows/installer.iss with Inno Setup 6 to produce the installer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
