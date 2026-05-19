# Web Preview User Flow Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automated web-preview tests that follow real user operation flows and verify rendered results stay aligned with the reviewed `web-preview` product shape.

**Architecture:** Keep the existing API tests and data-mapping tests as lower-level guards, then add a new Node-based DOM test layer that boots the real `design/web-preview.html` + `design/web-preview-data.js` + `design/web-preview-app.js` together. The new layer must drive clicks, file selection, mocked fetch responses, and DOM assertions so the product is verified by what the user actually sees, not by internal helper output alone.

**Tech Stack:** Node test runner, `jsdom`, static HTML/JS preview assets, existing pytest suite

---

## File Structure

- Create: `tests/web_preview_user_flow.test.mjs`
  - End-to-end-like DOM flow tests for `web-preview`
  - Owns test harness helpers for loading HTML, stubbing `fetch`, simulating upload, and reading rendered DOM
- Modify: `package.json`
  - Add `jsdom`-backed test command for the new DOM flow layer
  - Keep existing `tests/web_preview_data.test.mjs`
- Modify: `todo.md`
  - Mark DOM-level user-flow coverage as started/completed once implemented
- Optional Create: `tests/fixtures/web_preview_payloads.mjs`
  - Shared realistic mocked API payloads if `tests/web_preview_user_flow.test.mjs` becomes too large

The new DOM test file should stay focused on reviewed product flows, not helper internals. Data-format helper assertions remain in `tests/web_preview_data.test.mjs`.

### Case Matrix To Cover

These are the required first-wave cases:

1. `纯人声评测 / 单文件测评 / DNSMOS`
2. `纯人声评测 / 单文件测评 / NISQA`
3. `综合音频分析 / 单文件分析 / AudioBox Aesthetics`
4. `纯人声评测 / 对比评测 / 自由对比`
5. `纯人声评测 / 对比评测 / 基准对比`
6. `综合音频分析 / 对比分析`
7. `历史 / success`
8. `历史 / empty`
9. `历史 / error`
10. `设置 / trace 开关联动`
11. `设置 / 默认对比模式联动`
12. `上传失败提示`
13. `阶段性伪进度显示`

Every case must assert preview-aligned DOM output, not just that state changed.

### DOM Assertions Standard

The new tests must assert:

- Active page and active scene switch correctly
- Upload/compare actions call the expected API endpoint
- Real result cards render the reviewed dimension sets
- File summary, trace text, advice text, ranking text, and table headers/cells match the preview structure
- Detail view switching updates the rendered table, not just internal state
- History and settings behavior affect visible output
- Error flows show user-facing copy already defined in `web-preview-app.js`

Do not add a looser “snapshot only” strategy. Snapshots can help later, but initial coverage must be explicit semantic assertions.

### Test Harness Rules

The DOM harness should:

- Load `design/web-preview.html` as the source of truth
- Inline or evaluate `design/web-preview-data.js` and `design/web-preview-app.js` in a `jsdom` window
- Stub `window.fetch`, `window.alert`, `requestAnimationFrame`, `performance.now`, and hidden file input behavior
- Provide helper methods such as:
  - `bootPreview({ fetchMap })`
  - `click(selector)`
  - `uploadSingle(page, fileName)`
  - `uploadCompare(kind, filesByGroup)`
  - `text(selector)`
  - `texts(selector)`
- Flush async work after click/upload so assertions read the fully rendered DOM

Do not change production `web-preview` code just to make tests convenient unless the production code is already too tightly coupled to be testable.

### Test Strategy Boundaries

- `tests/test_web_api.py` continues guarding API contract shape
- `tests/web_preview_data.test.mjs` continues guarding mapping helpers
- `tests/web_preview_user_flow.test.mjs` becomes the source of truth for user-operation rendering behavior

This avoids mixing DOM flow assertions into Python string checks or helper-unit tests.

### Task 1: Add jsdom-based user-flow test harness

**Files:**
- Create: `tests/web_preview_user_flow.test.mjs`
- Modify: `package.json`
- Reference: `design/web-preview.html`
- Reference: `design/web-preview-data.js`
- Reference: `design/web-preview-app.js`

- [ ] **Step 1: Write the failing harness smoke test**

Add the first test to `tests/web_preview_user_flow.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";

test("web preview boots in jsdom and defaults to eval single scene", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
    },
  });

  assert.equal(app.text('[data-page="eval"] .card-title').includes("会议人声"), true);
  assert.equal(app.document.querySelector('[data-page="eval"]').classList.contains("active"), true);
  assert.equal(app.document.querySelector('[data-scene-root="eval"] [data-scene="single"]').classList.contains("active"), true);
});
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs
```

Expected:
- FAIL because `bootPreview(...)` and jsdom harness do not exist yet

- [ ] **Step 3: Add the minimal harness and test command**

Implement in `tests/web_preview_user_flow.test.mjs`:

- imports for `fs`, `path`, `vm`, and `jsdom`
- `bootPreview(...)` helper that:
  - reads `design/web-preview.html`
  - creates `JSDOM`
  - stubs `window.fetch`
  - stubs `window.alert`
  - sets deterministic `requestAnimationFrame`
  - evaluates data/app scripts inside the DOM window

Update `package.json`:

```json
{
  "scripts": {
    "test:web-preview": "node --test tests/web_preview_data.test.mjs tests/web_preview_user_flow.test.mjs"
  }
}
```

- [ ] **Step 4: Run the new smoke test**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs
```

Expected:
- PASS for the boot smoke test

- [ ] **Step 5: Run the existing preview tests**

Run:

```bash
npm run test:web-preview
```

Expected:
- Existing Node tests still PASS

- [ ] **Step 6: Commit**

```bash
git add package.json tests/web_preview_user_flow.test.mjs
git commit -m "test: add web preview user-flow dom harness"
```

### Task 2: Cover single-file user flows against reviewed preview output

**Files:**
- Modify: `tests/web_preview_user_flow.test.mjs`
- Optional Create: `tests/fixtures/web_preview_payloads.mjs`
- Reference: `docs/web-acceptance-checklist.md`

- [ ] **Step 1: Write the failing DNSMOS single-file flow test**

Add:

```js
test("speech single-file dnsmos flow renders preview-aligned result blocks", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload": buildJsonResponse(buildDnsmosSinglePayload()),
    },
  });

  await app.uploadSingle("eval", "demo.wav");

  assert.equal(app.text("[data-eval-file-summary]"), "12.3s · 16000Hz · Mono · 当前模型 DNSMOS");
  assert.equal(app.text("[data-eval-advice]"), "建议先整理峰值和响度，再复评。");
  assert.equal(app.text("[data-eval-trace]"), "原始文件 → 重采样到 16kHz → 送入 DNSMOS");
  assert.deepEqual(app.texts("[data-eval-model-grid] .score-card .label"), ["OVRL", "SIG", "BAK"]);
});
```

- [ ] **Step 2: Run the single-file test to verify it fails**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs --test-name-pattern "single-file"
```

Expected:
- FAIL until upload simulation and DOM flush helpers are correct

- [ ] **Step 3: Implement single-file helpers only as needed**

Add minimal helpers:

- `buildJsonResponse(payload)`
- `uploadSingle(page, fileName)`
- `flush()`
- `text(selector)`
- `texts(selector)`

The upload helper must:

- trigger the same hidden file input path used by the page
- attach a fake `File`
- dispatch the `change` event
- wait for async rendering to finish

- [ ] **Step 4: Add NISQA and AudioBox single-file tests**

Add:

- `speech single-file nisqa flow renders OVRL / NOI / DIS / COL / LOUD`
- `analysis single-file audiobox flow renders PQ / CE / CU / PC`
- detail view switching assertions for:
  - `模型维度`
  - `信号分析`
  - `完整表格`

Each test must assert visible DOM labels and at least one rendered numeric value.

- [ ] **Step 5: Run all single-file flow tests**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs --test-name-pattern "single-file|audiobox|nisqa"
```

Expected:
- PASS

- [ ] **Step 6: Run full Node preview suite**

Run:

```bash
npm run test:web-preview
```

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add tests/web_preview_user_flow.test.mjs tests/fixtures/web_preview_payloads.mjs package.json
git commit -m "test: cover single-file web preview user flows"
```

### Task 3: Cover compare user flows with free/base mode assertions

**Files:**
- Modify: `tests/web_preview_user_flow.test.mjs`
- Optional Modify: `tests/fixtures/web_preview_payloads.mjs`
- Reference: `design/web-preview.html`
- Reference: `design/web-preview-app.js`

- [ ] **Step 1: Write the failing speech compare free-mode test**

Add:

```js
test("speech compare free mode renders recommended version and ranking", async () => {
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload": buildJsonResponse(buildDnsmosComparePayload()),
    },
  });

  await app.openCompare("eval");
  await app.addCompareGroup("eval");
  await app.uploadCompare("eval", {
    A: "a.wav",
    B: "b.wav",
  });

  assert.match(app.text('[data-compare-summary="eval"] strong'), /推荐版本/);
  assert.ok(app.text('[data-compare-ranking="eval"] .ranking-list').includes("综合表现最稳"));
});
```

- [ ] **Step 2: Run the compare test to verify it fails**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs --test-name-pattern "compare"
```

Expected:
- FAIL until compare upload helpers exist

- [ ] **Step 3: Implement compare flow helpers**

Add minimal helpers:

- `openCompare(kind)`
- `addCompareGroup(kind)`
- `uploadCompare(kind, filesByGroup)`

These helpers must exercise the real UI path:

- click compare entry button
- add groups through `[data-add-group]`
- attach files to hidden compare inputs
- allow app code to trigger `/api/evaluate/compare-upload`

- [ ] **Step 4: Add compare assertions for base mode and NISQA dimensions**

Add tests for:

- `speech compare base mode recomputes summary relative to selected base group`
- `speech compare nisqa flow keeps OVRL / NOI / DIS / COL / LOUD in rendered output`
- `analysis compare flow renders AudioBox summary, ranking, and detailed pipeline`

Each test must assert:

- summary block copy
- ranking content
- active compare mode chip
- compare table headers
- at least one pipeline cell text

- [ ] **Step 5: Run compare flow tests**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs --test-name-pattern "compare|base mode|nisqa"
```

Expected:
- PASS

- [ ] **Step 6: Run full Node preview suite**

Run:

```bash
npm run test:web-preview
```

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add tests/web_preview_user_flow.test.mjs tests/fixtures/web_preview_payloads.mjs
git commit -m "test: cover compare web preview user flows"
```

### Task 4: Cover history, settings, progress, and error flows

**Files:**
- Modify: `tests/web_preview_user_flow.test.mjs`
- Optional Modify: `tests/fixtures/web_preview_payloads.mjs`
- Modify: `todo.md`

- [ ] **Step 1: Write the failing history success/empty/error tests**

Add tests for:

- `/api/history` success with one item
- `/api/history` success with empty list
- `/api/history` rejected fetch

Assert:

- visible list item content on success
- `暂无历史任务` on empty
- `历史加载失败：...` on error

- [ ] **Step 2: Run those tests to verify they fail**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs --test-name-pattern "history"
```

Expected:
- FAIL until harness supports boot-time history scenarios correctly

- [ ] **Step 3: Add settings linkage tests**

Add tests for:

- `trace toggle hides result trace blocks but preserves history summary pills`
- `compare default toggle changes newly opened compare scene mode`

These tests must navigate through the actual `设置` page buttons, not mutate globals directly.

- [ ] **Step 4: Add upload error and staged progress tests**

Add tests for:

- failed single upload triggers alert copy containing `本机评测失败`
- loading flow updates progress label through staged values before final render

The progress test may assert intercepted progress labels in order, for example:

- `上传中 10%`
- `预处理中 25%`
- `模型评测中 60%`
- `信号分析中 85%`
- final `100%`

- [ ] **Step 5: Update todo tracking**

Update `todo.md`:

- mark `单文件 / 对比页更完整 DOM 级结果断言` as completed
- mark user-flow DOM coverage as completed or started explicitly

- [ ] **Step 6: Run targeted Node tests**

Run:

```bash
node --test tests/web_preview_user_flow.test.mjs --test-name-pattern "history|settings|失败|进度"
```

Expected:
- PASS

- [ ] **Step 7: Run full verification**

Run:

```bash
npm run test:web-preview
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
```

Expected:
- Node suite PASS
- pytest suite PASS

- [ ] **Step 8: Commit**

```bash
git add tests/web_preview_user_flow.test.mjs tests/fixtures/web_preview_payloads.mjs todo.md
git commit -m "test: add web preview user-flow coverage for history and settings"
```

## Self-Review

Spec coverage check:

- User operation flow automation: covered by Tasks 1-4
- Preview-aligned rendering assertions: covered by explicit DOM assertions in Tasks 2-4
- Single-file, compare, history, settings flows: each has dedicated tasks
- Error and progress behavior: covered in Task 4

Placeholder scan:

- No `TODO` or deferred implementation markers remain in tasks
- Every verification step has a concrete command

Type consistency check:

- File names and commands consistently use `tests/web_preview_user_flow.test.mjs`
- Preview command remains `npm run test:web-preview`
- New helper names are reused consistently across tasks

Plan complete and saved to `docs/superpowers/plans/2026-05-19-web-preview-user-flow-tests.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
