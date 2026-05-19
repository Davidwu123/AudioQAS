# AGENTS.md

This file provides guidance to coding agents working with this repository.

## Scope

This repository currently focuses on the **web preview** of AudioQAS.

Primary files:

- `design/web-preview.html`
- `design/web-preview-data.js`
- `design/web-preview-app.js`
- `design/DESIGN.md`
- `docs/web-product-spec.md`

## Run & Verify

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install pytest
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
.venv/bin/python -m audioqas.web.run_local
```

## Preview Architecture

- `web-preview.html`: structure shell
- `web-preview-data.js`: business data and display mapping
- `web-preview-app.js`: DOM state/render/event layer

## Product Boundaries

- PC browser only
- Do not restore legacy desktop-app framing in product docs
- Feature scope must follow `design/web-preview.html` exactly.
- Support only what the current web preview defines:
  - `添加文件`
  - `对比评测`
- Under `添加文件`, do not assume multi-file upload is a confirmed product capability unless the preview copy/interaction is updated explicitly.
- Treat `对比评测` as the only confirmed multi-group flow.
- Do not introduce a separate batch-results product flow unless the web preview is updated first.
- Keep four top-level pages:
  - `纯人声评测`
  - `综合音频分析`
  - `历史`
  - `设置`
- Keep detail data split into:
  - `模型维度`
  - `信号分析`
  - `完整表格`

## Maintenance Rules

- Shared business data belongs in `design/web-preview-data.js`
- Rendering logic belongs in `design/web-preview-app.js`
- `design/web-preview.html` should remain thin
- Any business/display logic change should be covered by tests
