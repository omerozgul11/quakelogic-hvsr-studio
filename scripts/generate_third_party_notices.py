#!/usr/bin/env python3
"""Regenerate THIRD_PARTY_NOTICES.md from composer.lock, package.json/node_modules and requirements.lock.txt."""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_LICENSES = {  # license names for the pinned Python packages (from their PyPI metadata)
    "numpy": "BSD-3-Clause", "scipy": "BSD-3-Clause", "obspy": "LGPL-3.0", "pandas": "BSD-3-Clause",
    "matplotlib": "PSF-based (Matplotlib license)", "reportlab": "BSD-3-Clause", "fastapi": "MIT", "uvicorn": "BSD-3-Clause",
    "pydantic": "MIT", "pydantic-core": "MIT", "python-multipart": "Apache-2.0", "starlette": "BSD-3-Clause",
    "anyio": "MIT", "h11": "MIT", "click": "BSD-3-Clause", "typing-extensions": "PSF-2.0", "idna": "BSD-3-Clause",
    "sniffio": "MIT/Apache-2.0", "annotated-types": "MIT", "lxml": "BSD-3-Clause", "sqlalchemy": "MIT",
    "decorator": "BSD-2-Clause", "requests": "Apache-2.0", "urllib3": "MIT", "certifi": "MPL-2.0",
    "charset-normalizer": "MIT", "packaging": "Apache-2.0/BSD-2-Clause", "pillow": "MIT-CMU", "kiwisolver": "BSD-3-Clause",
    "cycler": "BSD-3-Clause", "fonttools": "MIT", "pyparsing": "MIT", "python-dateutil": "Apache-2.0/BSD-3-Clause",
    "pytz": "MIT", "tzdata": "Apache-2.0", "six": "MIT", "contourpy": "BSD-3-Clause", "numpy-quaternion": "MIT",
    "greenlet": "MIT/PSF", "setuptools": "MIT", "chardet": "LGPL-2.1", "annotated-doc": "MIT", "typing-inspection": "MIT",
    "pydantic-extra-types": "MIT", "email-validator": "CC0-1.0", "dnspython": "ISC", "httpx": "BSD-3-Clause", "httpcore": "BSD-3-Clause",
}

def python_packages():
    rows = []
    for line in (ROOT / "engine" / "requirements.lock.txt").read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)", line)
        if m:
            rows.append((m.group(1).lower(), m.group(2), PY_LICENSES.get(m.group(1).lower(), "see package metadata")))
    return rows

def php_packages():
    lock = json.loads((ROOT / "composer.lock").read_text())
    return [(p["name"], p["version"], ", ".join(p.get("license", []) or ["see package"])) for p in lock["packages"]]

def npm_packages():
    pkg = json.loads((ROOT / "package.json").read_text())
    names = sorted({**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})})
    rows = []
    for name in names:
        meta = ROOT / "node_modules" / name / "package.json"
        if meta.exists():
            m = json.loads(meta.read_text())
            lic = m.get("license") or (m.get("licenses") or [{}])[0].get("type", "see package")
            rows.append((name, m.get("version", "?"), lic if isinstance(lic, str) else lic.get("type", "see package")))
        else:
            rows.append((name, pkg.get("dependencies", {}).get(name) or pkg.get("devDependencies", {}).get(name), "see package"))
    return rows

def table(rows):
    out = ["| Package | Version | License |", "|---|---|---|"]
    out += [f"| {n} | {v} | {l} |" for n, v, l in rows]
    return "\n".join(out)

def main():
    text = f"""# Third-party notices

QuakeLogic HVSR Studio is released under the MIT License (see LICENSE). It bundles the
open-source components listed below, each under its own license. No component requires a
commercial runtime fee. License texts are distributed with the components themselves
(`vendor/<package>/LICENSE*`, `node_modules/<package>/LICENSE*` in the source tree, and the
`*.dist-info/` folders of the bundled Python environment) and must be preserved when
redistributing the application.

Notable notices:

* **ObsPy** is licensed under the GNU LGPL v3. It is used unmodified as a library through its
  public API (MiniSEED reading, STA/LTA, instrument-response removal). The LGPL license text
  ships in its dist-info folder. Source: https://github.com/obspy/obspy
* **Plotly.js** (MIT) is bundled locally (`plotly.js-cartesian-dist-min`); no CDN is used.
* **Inter** and **JetBrains Mono** fonts are bundled under the SIL Open Font License 1.1
  (`@fontsource-variable/*`).
* **Lucide** icons are ISC licensed.
* **PHP** (PHP License v3.01) and **CPython** (PSF License) runtimes are bundled unmodified in
  the Windows distribution (`runtime/win-x64/`). CPython builds come from the
  python-build-standalone project (MIT for the build scripts). Static PHP builds for
  Linux/macOS development come from static-php-cli (MIT for the build tool).
* **Laravel** framework and its dependencies are MIT licensed unless noted below.
* The SESAME (2004) guidelines are cited as the source of the reliability and clarity
  criteria; no SESAME code is used.

## Python packages (engine/requirements.lock.txt)

{table(python_packages())}

## PHP packages (composer.lock, production)

{table(php_packages())}

## npm packages (package.json)

{table(npm_packages())}
"""
    (ROOT / "THIRD_PARTY_NOTICES.md").write_text(text, encoding="utf-8")
    print("THIRD_PARTY_NOTICES.md written")

if __name__ == "__main__":
    sys.exit(main())
