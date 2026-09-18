# Third-party notices

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

| Package | Version | License |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.5.1 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| contourpy | 1.4.0 | BSD-3-Clause |
| cycler | 0.12.1 | BSD-3-Clause |
| decorator | 5.3.1 | BSD-2-Clause |
| fastapi | 0.141.1 | MIT |
| fonttools | 4.65.0 | MIT |
| greenlet | 3.5.6 | MIT/PSF |
| h11 | 0.16.0 | MIT |
| idna | 3.19 | BSD-3-Clause |
| kiwisolver | 1.5.1 | BSD-3-Clause |
| lxml | 6.1.3 | BSD-3-Clause |
| matplotlib | 3.11.2 | PSF-based (Matplotlib license) |
| numpy | 2.5.3 | BSD-3-Clause |
| obspy | 1.5.1 | LGPL-3.0 |
| packaging | 26.3 | Apache-2.0/BSD-2-Clause |
| pandas | 2.3.3 | BSD-3-Clause |
| pillow | 12.3.0 | MIT-CMU |
| pydantic | 2.13.5 | MIT |
| pydantic-core | 2.46.5 | MIT |
| pyparsing | 3.3.2 | MIT |
| python-dateutil | 2.9.0.post0 | Apache-2.0/BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pytz | 2026.3.post1 | MIT |
| reportlab | 4.5.1 | BSD-3-Clause |
| requests | 2.34.2 | Apache-2.0 |
| scipy | 1.18.1 | BSD-3-Clause |
| setuptools | 84.0.0 | MIT |
| six | 1.17.0 | MIT |
| sqlalchemy | 2.0.53 | MIT |
| starlette | 1.6.0 | BSD-3-Clause |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| tzdata | 2026.4 | Apache-2.0 |
| urllib3 | 2.7.0 | MIT |
| uvicorn | 0.53.0 | BSD-3-Clause |

## PHP packages (composer.lock, production)

| Package | Version | License |
|---|---|---|
| brick/math | 0.18.0 | MIT |
| carbonphp/carbon-doctrine-types | 3.2.1 | MIT |
| dflydev/dot-access-data | v3.0.3 | MIT |
| doctrine/inflector | 2.1.0 | MIT |
| doctrine/lexer | 3.0.1 | MIT |
| dragonmantank/cron-expression | v3.6.0 | MIT |
| egulias/email-validator | 4.0.4 | MIT |
| fruitcake/php-cors | v1.4.0 | MIT |
| graham-campbell/result-type | v1.2.0 | MIT |
| guzzlehttp/guzzle | 8.2.0 | MIT |
| guzzlehttp/promises | 3.0.2 | MIT |
| guzzlehttp/psr7 | 3.1.0 | MIT |
| guzzlehttp/uri-template | v2.0.1 | MIT |
| laravel/framework | v13.32.0 | MIT |
| laravel/prompts | v0.3.24 | MIT |
| laravel/serializable-closure | v2.0.16 | MIT |
| laravel/tinker | v3.0.2 | MIT |
| league/commonmark | 2.10.1 | BSD-3-Clause |
| league/config | v1.2.0 | BSD-3-Clause |
| league/flysystem | 3.36.0 | MIT |
| league/flysystem-local | 3.35.3 | MIT |
| league/mime-type-detection | 1.17.0 | MIT |
| league/uri | 7.8.1 | MIT |
| league/uri-interfaces | 7.8.1 | MIT |
| monolog/monolog | 3.12.0 | MIT |
| nesbot/carbon | 3.14.0 | MIT |
| nette/schema | v1.3.6 | BSD-3-Clause, GPL-2.0-only, GPL-3.0-only |
| nette/utils | v4.1.5 | BSD-3-Clause, GPL-2.0-only, GPL-3.0-only |
| nikic/php-parser | v5.9.0 | BSD-3-Clause |
| nunomaduro/termwind | v2.4.0 | MIT |
| phpoption/phpoption | 1.10.0 | Apache-2.0 |
| psr/clock | 1.0.0 | MIT |
| psr/container | 2.0.2 | MIT |
| psr/event-dispatcher | 1.0.0 | MIT |
| psr/http-client | 1.0.3 | MIT |
| psr/http-factory | 1.1.0 | MIT |
| psr/http-message | 2.0 | MIT |
| psr/log | 3.0.2 | MIT |
| psr/simple-cache | 3.0.0 | MIT |
| psy/psysh | v0.12.24 | MIT |
| ramsey/collection | 2.1.1 | MIT |
| ramsey/uuid | 4.9.3 | MIT |
| symfony/clock | v8.1.0 | MIT |
| symfony/console | v8.1.7 | MIT |
| symfony/css-selector | v8.1.6 | MIT |
| symfony/deprecation-contracts | v3.7.1 | MIT |
| symfony/error-handler | v8.1.5 | MIT |
| symfony/event-dispatcher | v8.1.5 | MIT |
| symfony/event-dispatcher-contracts | v3.7.1 | MIT |
| symfony/finder | v8.1.7 | MIT |
| symfony/http-foundation | v8.1.7 | MIT |
| symfony/http-kernel | v8.1.7 | MIT |
| symfony/mailer | v8.1.7 | MIT |
| symfony/mime | v8.1.7 | MIT |
| symfony/polyfill-ctype | v1.37.0 | MIT |
| symfony/polyfill-intl-grapheme | v1.41.0 | MIT |
| symfony/polyfill-intl-idn | v1.42.0 | MIT |
| symfony/polyfill-intl-normalizer | v1.42.0 | MIT |
| symfony/polyfill-mbstring | v1.38.2 | MIT |
| symfony/polyfill-php80 | v1.37.0 | MIT |
| symfony/polyfill-php82 | v1.38.1 | MIT |
| symfony/polyfill-php84 | v1.38.1 | MIT |
| symfony/polyfill-php85 | v1.41.0 | MIT |
| symfony/polyfill-php86 | v1.41.0 | MIT |
| symfony/polyfill-uuid | v1.37.0 | MIT |
| symfony/process | v8.1.7 | MIT |
| symfony/routing | v8.1.6 | MIT |
| symfony/service-contracts | v3.7.3 | MIT |
| symfony/string | v8.1.7 | MIT |
| symfony/translation | v8.1.5 | MIT |
| symfony/translation-contracts | v3.7.1 | MIT |
| symfony/uid | v8.1.5 | MIT |
| symfony/var-dumper | v8.1.7 | MIT |
| tijsverkoyen/css-to-inline-styles | v2.4.0 | BSD-3-Clause |
| vlucas/phpdotenv | v5.7.0 | BSD-3-Clause |
| voku/portable-ascii | 2.1.1 | MIT |

## npm packages (package.json)

| Package | Version | License |
|---|---|---|
| @fontsource-variable/inter | 5.3.0 | OFL-1.1 |
| @fontsource-variable/jetbrains-mono | 5.3.0 | OFL-1.1 |
| @tailwindcss/vite | 4.3.3 | MIT |
| @types/plotly.js | 3.0.13 | MIT |
| @vitejs/plugin-vue | 6.0.9 | MIT |
| @vue/tsconfig | 0.9.1 | MIT |
| laravel-vite-plugin | 3.2.0 | MIT |
| lucide-vue-next | 0.577.0 | ISC |
| marked | 16.4.1 | MIT |
| pinia | 3.0.4 | MIT |
| plotly.js-cartesian-dist-min | 3.7.0 | MIT |
| tailwindcss | 4.3.3 | MIT |
| typescript | 5.9.3 | Apache-2.0 |
| vite | 8.3.0 | MIT |
| vue | 3.5.42 | MIT |
| vue-router | 4.6.4 | MIT |
| vue-tsc | 3.3.11 | MIT |
