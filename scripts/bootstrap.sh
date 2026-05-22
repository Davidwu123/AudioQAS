#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Error: ffmpeg is required but was not found on PATH." >&2
  echo "Install examples:" >&2
  echo "  macOS: brew install ffmpeg" >&2
  echo "  Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg" >&2
  exit 1
fi

echo "[1/4] Creating virtual environment"
"$PYTHON_BIN" -m venv .venv

echo "[2/4] Installing Python development dependencies"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

echo "[3/4] Installing Node dependencies"
npm install

echo "[4/4] Installing Playwright browsers"
npx playwright install

cat <<'EOF'

Development setup complete.

Run app:
  .venv/bin/python -m audioqas.web.run_local

Run Python tests:
  QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q

Run jsdom tests:
  npm run test:web-preview

Run Playwright E2E:
  npm run test:e2e
EOF
