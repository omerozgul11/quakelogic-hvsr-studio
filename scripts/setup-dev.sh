#!/usr/bin/env bash
# QuakeLogic HVSR Studio — developer / from-source setup for Linux and macOS.
# Downloads a self-contained toolchain into .tools/ and runtime/ (nothing is installed
# system-wide), installs dependencies, builds the frontend and prepares the database.
# Internet access is required for this script only; the application then runs offline.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OS="$(uname -s)"; ARCH="$(uname -m)"
case "$OS-$ARCH" in
  Linux-x86_64)  PLAT=linux-x64;   SPC=linux-x86_64;  NODE=linux-x64;  UV=x86_64-unknown-linux-gnu ;;
  Linux-aarch64) PLAT=linux-arm64; SPC=linux-aarch64; NODE=linux-arm64; UV=aarch64-unknown-linux-gnu ;;
  Darwin-arm64)  PLAT=macos-arm64; SPC=macos-aarch64; NODE=darwin-arm64; UV=aarch64-apple-darwin ;;
  Darwin-x86_64) PLAT=macos-x64;   SPC=macos-x86_64;  NODE=darwin-x64;  UV=x86_64-apple-darwin ;;
  *) echo "Unsupported platform $OS-$ARCH"; exit 1 ;;
esac
PHP_VERSION="${PHP_VERSION:-8.4.23}"
NODE_VERSION="${NODE_VERSION:-24.21.0}"
UV_VERSION="${UV_VERSION:-0.12.15}"
mkdir -p .tools "runtime/$PLAT"

if [ ! -x "runtime/$PLAT/php/php" ] && ! command -v php >/dev/null; then
  echo "==> Downloading static PHP $PHP_VERSION"
  mkdir -p "runtime/$PLAT/php"
  curl -fsSL "https://dl.static-php.dev/static-php-cli/common/php-$PHP_VERSION-cli-$SPC.tar.gz" | tar -xz -C "runtime/$PLAT/php"
fi
PHP="$ROOT/runtime/$PLAT/php/php"; [ -x "$PHP" ] || PHP="$(command -v php)"
[ -f .tools/composer.phar ] || { echo "==> Downloading Composer"; curl -fsSL -o .tools/composer.phar https://getcomposer.org/download/latest-stable/composer.phar; }
if [ ! -x .tools/node/bin/node ] && ! command -v npm >/dev/null; then
  echo "==> Downloading Node.js $NODE_VERSION"
  mkdir -p .tools/node
  curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-$NODE.tar.gz" | tar -xz -C .tools/node --strip-components=1
fi
if [ ! -x .tools/uv ] && ! command -v uv >/dev/null; then
  echo "==> Downloading uv $UV_VERSION"
  curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$UV.tar.gz" | tar -xz -C .tools --strip-components=1
fi
export PATH="$ROOT/.tools:$ROOT/.tools/node/bin:$PATH"
export COMPOSER_HOME="$ROOT/.tools/composer-home" UV_PYTHON_INSTALL_DIR="$ROOT/.tools/uv-python"

echo "==> PHP dependencies"; "$PHP" .tools/composer.phar install --no-interaction --no-progress
echo "==> Python 3.12 environment"; (cd engine && uv python install 3.12 && uv sync --extra dev --python 3.12)
echo "==> Frontend"; npm ci --no-audit --no-fund && npm run build
[ -f .env ] || cp .env.example .env
grep -q '^APP_KEY=base64' .env || "$PHP" artisan key:generate --force
echo "==> Database"; "$PHP" artisan hvsr:setup --no-interaction
echo
echo "Setup complete. Start the application with:  launcher/hvsr-studio.sh"
