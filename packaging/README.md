# Packaging

## Windows x64 (portable zip + installer)

```
# On Windows (PowerShell):
powershell -ExecutionPolicy Bypass -File packaging\windows\build-dist.ps1 -Installer

# On Linux/macOS (cross-build; needs .tools/uv, PHP + composer.phar, Node):
python3 packaging/build_dist.py
```

Output in `dist/`:

* `QuakeLogic-HVSR-Studio/` — the staged application folder (portable: unzip anywhere, run `HVSR Studio.bat`)
* `QuakeLogic-HVSR-Studio-<version>-win-x64.zip` — the portable distribution
* `QuakeLogic-HVSR-Studio-<version>-setup-win-x64.exe` — per-user installer (with `-Installer`; needs Inno Setup 6)

What the distribution contains: the Laravel application with production `vendor/`, the built
frontend (`public/build`), the Python engine sources, a bundled PHP 8.4 NTS runtime with a
`php.ini`, a bundled CPython 3.12 with all pinned scientific packages installed as Windows wheels,
the launcher, docs and synthetic examples. Nothing is downloaded at run time.

The installer installs per-user into `%LocalAppData%\Programs\QuakeLogic HVSR Studio` so that
the application folder (SQLite database, project folders, logs) is writable without
administrator rights. If an administrator chooses an all-users location instead, the launcher
detects the read-only folder and keeps the database, projects and logs under
`%LocalAppData%\QuakeLogic\HVSR Studio` automatically.

## macOS / Linux

No binary bundle is produced for these platforms; see `docs/user-guide.md` → "Install from
source" (`scripts/setup-dev.sh` downloads a static PHP, Composer, Node and a pinned Python and
builds everything; `launcher/hvsr-studio.sh` / `.command` starts the application).
