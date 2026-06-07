# AGENTS.md

This file provides guidance to coding agents working with this repository.

## Scope

This repository currently focuses on the **web preview** of AudioQAS.

Primary files:

- `audioqas/web/static/web-preview.html`
- `audioqas/web/static/web-preview-data.js`
- `audioqas/web/static/web-preview-app.js`
- `docs/design-system-detailed.md`
- `docs/web-product-spec.md`

## Run & Verify

```bash
./scripts/audioqas-bootstrap --with-test --no-start --no-open
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
./scripts/audioqas-bootstrap
```

Default `./scripts/audioqas-bootstrap` installs product runtime dependencies only.
Use `--with-test` for pytest, Node/npm dependencies, `node_modules`, and Playwright browsers.

## Preview Architecture

- `web-preview.html`: structure shell
- `web-preview-data.js`: business data and display mapping
- `web-preview-app.js`: DOM state/render/event layer

## Code Reading & Debugging Entry

- For code logic questions, module analysis, call-chain tracing, or bug triage, use the existing `.codegraph/` index first when available.
- Prefer `codegraph_context`, `codegraph_trace`, `codegraph_callers`, and `codegraph_callees` to locate relevant files, functions, routes, and dependencies before broad manual source searches.
- Treat codegraph as navigation and hypothesis support; verify final conclusions against the current source files, logs, tests, or reproduction evidence.
- If `.codegraph/` is missing, stale, or unavailable, fall back to `rg` plus direct source reading.

## Product Boundaries

- PC browser only
- Do not restore legacy desktop-app framing in product docs
- Feature scope must follow `audioqas/web/static/web-preview.html` exactly.
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

- Shared business data belongs in `audioqas/web/static/web-preview-data.js`
- Rendering logic belongs in `audioqas/web/static/web-preview-app.js`
- `audioqas/web/static/web-preview.html` should remain thin
- Any business/display logic change should be covered by tests

## Review Checklist

- Review changes in this order:
  1. behavior correctness
  2. result/data-field semantic consistency
  3. duplicated logic, unused dependencies, and boundary leakage
  4. test coverage for both runnable behavior and semantic correctness
- Do not stop at "tests pass" or "page renders normally". If a field name, trace value, or preprocessing flag is semantically inaccurate, treat it as a bug.
- When refactoring shared logic, verify all callers keep the same product meaning, not just the same execution path.
- When removing desktop-era code or dependencies, confirm there is no remaining runtime import or documented product dependency before deleting them from requirements or docs.

## Execution Mode

- Default to continuous execution once a plan is approved. Do not pause for small confirmations between ordinary implementation steps.
- When the user states a high-level goal and does not ask for step-by-step confirmation, treat it as goal-driven continuous execution until blocked by a root-level red-line decision, a major direction change, or a plan gap that cannot be resolved safely from repository context.
- For multi-phase or structural work, write/update the corresponding plan under `meta/superpowers/plans/` first, then execute phase-by-phase against that plan.
- During execution, only interrupt for confirmation when:
  1. a root `AGENTS.md` red-line operation is required
  2. the implementation direction must change in a non-trivial way
  3. the current plan is blocked by a gap that cannot be resolved safely from repository context
- Otherwise, keep working autonomously, keep tests up to date, and report progress at meaningful checkpoints instead of asking for routine approval.
