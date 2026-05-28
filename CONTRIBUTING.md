# Contributing

Thanks for contributing to AudioQAS.

## Before You Start

Recommended local environment:

- Python `3.10+`
- ffmpeg `6.0+`
- Node.js `18+` and npm only when running `--with-test`

Project setup:

```bash
./scripts/audioqas-bootstrap --with-test
```

Default `./scripts/audioqas-bootstrap` is for product runtime only. It does not install pytest, Node/npm packages, `node_modules`, or Playwright browsers.
Use `--with-test` when you need the regression test toolchain.

## Run Locally

```bash
./scripts/audioqas-bootstrap
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
