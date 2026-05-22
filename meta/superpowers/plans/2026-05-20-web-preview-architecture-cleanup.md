# Web Preview Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web preview feature-complete while converging the frontend into a cleaner architecture: preview and runtime pages must share display semantics, app/data boundaries must be explicit, and obvious duplication/state sprawl must be removed.

**Architecture:** Continue the existing convergence direction by moving display semantics and view-model shaping into `audioqas/web/static/web-preview-data.js`, while shrinking `audioqas/web/static/web-preview-app.js` into DOM lookup, event binding, and render orchestration. Execute the cleanup in phases: first finish single-file renderer unification, then unify compare renderer output, then split state and action boundaries, and finally remove residual duplication and stabilize tests.

**Tech Stack:** Vanilla JS, shared UMD-style preview data module, jsdom/node tests, pytest static checks

---

### Scope Snapshot

**Already completed baseline**
- Logging/request-id chain is available
- Settings and preprocess trace are wired
- Compare summary now uses shared summary helpers
- Single overview + metric cards now use shared helpers
- Single detail table now uses a shared DOM helper
- Current test baseline is green before the next cleanup phase

**Remaining architecture work**
- Final residual duplication review and documentation sync
- Full-suite verification after the latest visual alignment adjustments

---

### Phase 1: Finish Single Renderer Unification

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `audioqas/web/static/web-preview-data.js`
- Modify: `tests/python/test_web_preview_app.py`
- Modify: `tests/web/web_preview_data.test.mjs`
- Modify: `tests/web/web_preview_user_flow.test.mjs`

- [x] **Step 1: Introduce shared single DOM helpers**
- [x] **Step 2: Move hero/model/signal card display semantics into `buildSingleFileViewModel()`**
- [x] **Step 3: Replace duplicated `eval/analysis` single render blocks with shared helper calls**
- [x] **Step 4: Add/refresh tests that lock the shared helper structure**
- [x] **Step 5: Verify**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py -q
node --test tests/web/web_preview_data.test.mjs tests/web/web_preview_user_flow.test.mjs
```

Expected:
- All single-file rendering tests pass
- No duplicated large `eval/analysis` single renderer blocks remain

---

### Phase 2: Unify Compare Ranking/Table Rendering

**Files:**
- Modify: `audioqas/web/static/web-preview-data.js`
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `tests/web/web_preview_data.test.mjs`
- Modify: `tests/web/web_preview_user_flow.test.mjs`
- Modify: `tests/web/web_preview_user_flow_real.test.mjs`

- [x] **Step 1: Add shared compare ranking/table view-model helpers**

Target:
- Introduce helper(s) that compute:
  - ranking card copy
  - ranking score/status text
  - compare table tag copy
  - compare detail row context for free/base mode

- [x] **Step 2: Make `renderCompareSection()` consume the shared compare ranking/table helpers**

- [x] **Step 3: Make `renderCompareFromRuntime()` consume the same helpers**

- [x] **Step 4: Remove duplicated ranking/table copy building from app layer**

- [x] **Step 5: Add failing/locking tests for compare shared rendering structure**

Minimum assertions:
- free/base mode both use the same shared ranking semantics
- runtime compare and preview compare keep the same display copy rules
- app layer no longer hardcodes separate ranking copy templates for runtime vs preview

- [x] **Step 6: Verify**

Run:
```bash
node --test tests/web/web_preview_data.test.mjs tests/web/web_preview_user_flow.test.mjs tests/web/web_preview_user_flow_real.test.mjs
```

Expected:
- All compare user-flow/data tests pass
- No new style/copy divergence appears between preview and runtime

---

### Phase 3: Tighten App/Data Boundary

**Files:**
- Modify: `audioqas/web/static/web-preview-data.js`
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `tests/python/test_web_preview_app.py`

- [x] **Step 1: Audit remaining display semantics still assembled inside `web-preview-app.js`**

Focus areas:
- compare table tag text
- any remaining status-text or display-label branches
- page-specific summary strings that can be emitted by data helpers

- [x] **Step 2: Move those display semantics into data-layer helpers**

- [x] **Step 3: Add static architecture assertions**

Target assertions:
- app layer uses shared helper outputs
- data layer remains the place where display semantics are shaped

- [x] **Step 4: Verify**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py -q
```

Expected:
- Static architecture tests pass
- app/data responsibility boundary is clearer than current baseline

---

### Phase 4: Slice Runtime State

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `tests/python/test_web_preview_app.py`
- Modify: `tests/web/web_preview_user_flow.test.mjs`

- [x] **Step 1: Split `runtimeState` into explicit slices**

Target slices:
- `runtimeState.single`
- `runtimeState.compare`
- `runtimeState.history`
- `runtimeState.settings`
- `runtimeState.requests`

If full object rename is too disruptive, at minimum create nested slice objects with clear responsibilities instead of wide top-level mutation.

- [x] **Step 2: Update helper functions to consume the new slices**

- [x] **Step 3: Add tests that lock the new state structure**

- [x] **Step 4: Verify**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py -q
node --test tests/web/web_preview_user_flow.test.mjs
```

Expected:
- State structure assertions pass
- Upload/compare/reset/history flows continue working

---

### Phase 5: Introduce Action Helpers For Event Flows

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `tests/web/web_preview_user_flow.test.mjs`
- Modify: `tests/web/web_preview_user_flow_real.test.mjs`

- [x] **Step 1: Extract action helpers**

Target helpers:
- single upload action
- compare upload action
- reset action
- export action
- settings persistence action
- history filter/detail actions

- [x] **Step 2: Replace inline event-listener mutations with those action helpers**

- [x] **Step 3: Verify that listeners become thin adapters**

- [x] **Step 4: Verify**

Run:
```bash
node --test tests/web/web_preview_user_flow.test.mjs tests/web/web_preview_user_flow_real.test.mjs
```

Expected:
- No user-flow regressions
- Action paths are easier to trace and reason about

---

### Phase 6: Remove Residual Duplication And Stabilize Tests

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `audioqas/web/static/web-preview-data.js`
- Modify: `tests/python/test_web_api.py`
- Modify: `tests/python/test_web_preview_app.py`
- Modify: `tests/web/web_preview_data.test.mjs`
- Modify: `tests/web/web_preview_user_flow.test.mjs`
- Modify: `tests/web/web_preview_user_flow_real.test.mjs`

- [x] **Step 1: Remove dead/obsolete helpers and copy templates**
- [x] **Step 2: Continue isolating environment-sensitive tests from local persisted state**
- [x] **Step 3: Add final regression assertions for architecture cleanliness**
- [x] **Step 4: Verify**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
```

Expected:
- Full suite green
- No dependence on local `.tmp/web_state` residue
- Fewer duplicated render/copy paths than the current baseline

---

### Final Verification Checklist

- [x] Single-file preview/runtime pages share the same rendering semantics
- [x] Compare preview/runtime pages share the same summary/ranking/table semantics
- [x] `web-preview-app.js` is mainly orchestration, not semantic formatting
- [x] `runtimeState` is clearer and less sprawling
- [x] Tests still pass with isolated temp state
- [x] Preview style remains the source of truth for runtime visuals
