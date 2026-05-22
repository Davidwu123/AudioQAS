# Contributing

Thanks for contributing to AudioQAS.

## Before You Start

Recommended local environment:

- Python `3.10+`
- Node.js `18+`
- npm
- `ffmpeg` on `PATH`

Project setup:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
npm install
npx playwright install
```

System dependency examples:

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y ffmpeg
```

This repository currently requires `ffmpeg` to be available on `PATH` for video input handling.
We do not yet pin a minimum `ffmpeg` version in the project metadata.

## Run Locally

```bash
.venv/bin/python -m audioqas.web.run_local
```

Open:

```text
http://127.0.0.1:8000
```

## Test Commands

Python:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
```

Web preview / jsdom:

```bash
npm run test:web-preview
```

Browser E2E:

```bash
npm run test:e2e
```

## Contribution Focus

Current repository focus:

- web preview/runtime behavior
- audio evaluation service wiring
- result rendering consistency
- test coverage for runtime and display semantics

Please keep changes aligned with the current web product boundary rather than introducing unrelated platform flows.
