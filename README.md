<div align="center">

# AudioQAS

### Local-first Web Workbench for Audio Quality Assessment

**Speech evaluation · Mixed-content analysis · Signal metrics · 100% local**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](#)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](#)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18+-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](#)

[![PC Browser](https://img.shields.io/badge/Target-PC_Browser_only-orange.svg)](#)

</div>

---

## Get Started

Repository:

```text
https://github.com/Davidwu123/AudioQAS
```

One-command install and launch:

```bash
curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash
```

The `github.com/Davidwu123/AudioQAS` URL is the repository page for humans.
The `raw.githubusercontent.com/Davidwu123/AudioQAS/...` URL is the raw script content used by `curl`.

The installer uses the current directory as the parent workspace. If the current directory is already the AudioQAS repo, it runs there; otherwise it uses `./AudioQAS`.

Existing repository:

```bash
./scripts/audioqas-bootstrap
```

> Some Python dependencies are heavy (`torch`, `torchaudio`, `onnxruntime`). Expect longer install time on first run.
> The default setup installs product runtime dependencies only. It does not install pytest, Node/npm packages, `node_modules`, or Playwright browsers.

### Developer Setup

Use this if you want to run tests or contribute:

```bash
./scripts/audioqas-bootstrap --with-test
```

`--with-test` installs pytest, Node/npm dependencies, and Playwright Chromium for regression testing.

That's it — no production deployment, no cloud services, everything runs locally.

---

## What Can You Do Today

| | |
|---|---|
| **Speech Quality Evaluation** | Upload pure-voice audio, get DNSMOS / NISQA scores + signal analysis |
| **Mixed-content Analysis** | Upload music+voice or video tracks, get AudioBox Aesthetics + signal analysis |
| **Single-file Flow** | One file → model results + signal metrics + preprocessing trace + engineering advice |
| **Multi-group Compare** | 2–6 groups → ranking + recommendation + free/base comparison modes |
| **History** | Real task history backed by local state, auto-refresh on page switch |
| **Settings** | Default model, preprocessing trace toggle, compare mode — all persisted locally |
| **Export** | CSV / JSON export with `request_id` in filename |

---

## Why AudioQAS

Most audio quality tools are either:

- **Cloud-only** — your audio leaves your machine
- **Command-line only** — no visual feedback, no compare, no history
- **Single-model** — one MOS score, no cross-model or signal-level view

AudioQAS is different:

- **100% local** — no API keys, no external services, audio never leaves your machine
- **Web workbench** — dark-theme glass-panel UI designed for audio engineers, not casual users
- **Multi-model** — DNSMOS, NISQA, AudioBox Aesthetics, each with independent results and cache
- **Signal metrics alongside AI** — LUFS, True Peak, Clipping, THD, LRA — not just MOS numbers
- **Full preprocessing trace** — every step from raw file to model input is visible and auditable
- **Compare that makes sense** — free comparison for ranking, baseline comparison for delta analysis

---

## Key Features

| | |
|---|---|
| **4-page structure** | 纯人声评测 · 综合音频分析 · 历史 · 设置 |
| **3 AI models** | DNSMOS (OVRL/SIG/BAK) · NISQA (OVRL/NOI/DIS/COL/LOUD) · AudioBox (PQ/CE/CU/PC) |
| **Signal analysis** | LUFS · LRA · True Peak · Clipping · THD — always present, not optional |
| **Compare up to 6 groups** | A/B/C/D/E/F with dynamic `+` expansion |
| **Free vs Baseline compare** | Switch modes, all rankings and deltas update instantly |
| **Preprocessing trace** | resample → mono convert → video extract → passthrough — every step visible |
| **Real byte progress** | XHR `upload.onprogress` for real upload tracking, fetch fallback in jsdom |
| **Result cache by model** | Switch models without losing other model's cached results |
| **Error + done coexistence** | Failed compare still shows last successful results with error banner |
| **Export with request_id** | `audioqas_eval_single_abc123.json` — every export is traceable |

---

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     Browser (PC only)                          │
│                                                               │
│  web-preview.html ─── web-preview-app.js ─── web-preview-data │
│         │                          │                           │
│    DOM render()            runtimeState + resultCache         │
│         │                          │                           │
└─────────┼──────────────────────────┼───────────────────────────┘
          │                          │
          ▼                          ▼
┌───────────────────────────────────────────────────────────────┐
│                  FastAPI (uvicorn, localhost:8000)              │
│                                                               │
│  api.py ─── tasks.py ─── services.py ─── registry.py          │
│     │           │            │                                  │
│     │      task orchestrate   │                                  │
│     │           │            │                                  │
│     ▼           ▼            ▼                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐             │
│  │ DNSMOS  │ │  NISQA  │ │AudioBox │ │Analysis │             │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘             │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │preprocessor │  │history_store │  │settings_store│          │
│  └─────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────────────────────────────────────────┘
```

<details>
<summary><strong>Repository layout</strong></summary>

```
audioqas/
  web/           FastAPI app, runtime logic, static frontend
    api.py       REST endpoints
    tasks.py     Task orchestration (single / compare / batch)
    services.py  Model dispatch
    registry.py  Model + signal metric registry
    runtime.py   Runtime state management
    run_local.py Local server entry point
    static/      Frontend assets (HTML + JS + CSS)
    history_store.py   Local JSON-backed history
    settings_store.py  Local JSON-backed settings
  core/
    preprocessor.py    Audio preprocessing pipeline
  models/
    dnsmos.py          DNSMOS model wrapper
    nisqa.py           NISQA model wrapper
    audiobox_aesthetics.py  AudioBox Aesthetics wrapper
    analysis.py        Signal analysis module

design/              Design token reference asset
docs/                Product spec, acceptance checklist, design docs
tests/
  python/            pytest suite
  web/               jsdom user-flow tests
  e2e/               Playwright browser tests
  fixtures/          Shared test WAV files
```

</details>

---

## API Surface

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/` | Web UI |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/bootstrap` | Initial page config |
| `GET` | `/api/navigation` | Navigation structure |
| `GET` | `/api/models` | Available model list |
| `GET` | `/api/signal-metrics` | Signal metric definitions |
| `GET` | `/api/history` | Task history list |
| `GET` | `/api/history/{id}` | Single history item |
| `GET` | `/api/settings` | Current settings |
| `POST` | `/api/evaluate/single` | Single-file evaluation |
| `POST` | `/api/evaluate/compare` | Multi-group compare |
| `POST` | `/api/evaluate/batch` | Batch evaluation |
| `POST` | `/api/evaluate/upload` | File upload (single) |
| `POST` | `/api/evaluate/upload-batch` | File upload (batch) |
| `POST` | `/api/evaluate/compare-upload` | File upload (compare) |
| `POST` | `/api/settings` | Update settings |

---

## Run Tests

AudioQAS uses:

- `pytest` for Python API, service, preprocessing, and runtime tests
- `jsdom` for web preview user-flow tests
- `Playwright` for browser E2E tests

```bash
# Python test suite
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q

# jsdom user-flow tests
npm run test:web-preview

# Playwright browser tests
npm run test:e2e
```

<details>
<summary><strong>Test details</strong></summary>

- **pytest** covers: web API contracts, task orchestration, model services, schemas, settings/history store, preprocessing, logging, and DOM-level UI assertions
- **jsdom** covers: single-file upload/render, compare flow, history states, settings persistence, progress lifecycle, export filename, XHR/fetch fallback
- **Playwright** covers: real browser upload, page navigation, DOM snapshot verification — runs against static file server, no full backend dependency

</details>

---

## Runtime Artifacts

Local runtime writes to the repository root (all safe to delete):

| Path | Content |
|------|---------|
| `.tmp/preprocessed` | Audio preprocessing intermediates |
| `.tmp/web_uploads` | Uploaded file cache |
| `.tmp/web_state` | History + settings JSON |
| `.tmp/log/` | `audioqas.log` + `audioqas.error.log` |

Deleting `.tmp/web_state` clears local history and settings.

<details>
<summary><strong>Log configuration</strong></summary>

Logs are configured at startup via environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUDIOQAS_LOG_LEVEL` | `DEBUG` | Log level |
| `AUDIOQAS_LOG_DIR` | `.tmp/log/` | Log directory |
| `AUDIOQAS_LOG_MAX_MB` | `20` | Max single file size before rotation |
| `AUDIOQAS_LOG_BACKUP_COUNT` | `3` | Number of rotated backups |

Log format includes: timestamp, thread ID, level, `request_id`, scene, event, file:line, module tag.

Each business request (single / compare / batch / settings) gets one `request_id` — no per-file splitting.

</details>

---

## Scope & Limits

Current scope is intentional, not aspirational:

- **PC browser only** — no mobile layout, no responsive touch flow
- **Local development workflow** — no production packaging, no CI/CD deployment
- **4 pages only** — 纯人声评测, 综合音频分析, 历史, 设置
- **No batch product flow** — single file + compare cover core needs; batch API exists but has no dedicated UI

---

## License

MIT

---

<div align="center">

**Built for audio engineers who need real metrics, not just numbers**

[Report Bug](https://github.com/Davidwu123/AudioQAS/issues) · [Request Feature](https://github.com/Davidwu123/AudioQAS/issues)

</div>
