# Single File Real Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the web preview single-file flow show real API-backed results for both `纯人声评测` and `综合音频分析` without changing the current product structure.

**Architecture:** Keep the existing `web-preview` shell and route all single-file rendering through a new front-end display-model mapping layer. `audioqas/web/static/web-preview-data.js` owns reusable mapping/formatting helpers, while `audioqas/web/static/web-preview-app.js` owns runtime state, staged pseudo-progress, and DOM updates based on the mapped single-file view model.

**Tech Stack:** Static HTML, browser-side JavaScript, FastAPI upload endpoint, pytest, Node test runner

---

### Task 1: Add failing tests for single-file display mapping

**Files:**
- Modify: `tests/web/web_preview_data.test.mjs`
- Modify: `tests/python/test_web_preview_app.py`
- Reference: `audioqas/web/static/web-preview-data.js`
- Reference: `audioqas/web/static/web-preview-app.js`

- [ ] **Step 1: Write the failing Node tests for real single-file display models**

Add tests to `tests/web/web_preview_data.test.mjs` that assert a new mapping API exists and supports:

```js
test("speech single-file mapping keeps DNSMOS primary dimensions", () => {
  const payload = {
    domain: "speech",
    model: {
      model_key: "dnsmos",
      result: {
        model_name: "DNSMOS",
        grade: "Good",
        duration: 12.3,
        original_sr: 16000,
        original_channels: 1,
        preprocessed: true,
        preprocessed_path: "/tmp/a.wav",
        dimensions: {
          OVRL: { score: 3.8, grade: "Good", description: "ok" },
          SIG: { score: 4.1, grade: "Good", description: "clear" },
          BAK: { score: 3.2, grade: "Fair", description: "noise" },
        },
      },
    },
    signal: {
      metrics: {
        LUFS: { value: -15.6, unit: "LUFS", grade: "Good", description: "ok" },
        LRA: { value: 6.4, unit: "LU", grade: "Good", description: "ok" },
      },
    },
  };

  const view = preview.buildSingleFileViewModel("eval", payload, "demo.wav");
  assert.equal(view.fileName, "demo.wav");
  assert.equal(view.primaryMetric.key, "OVRL");
  assert.deepEqual(view.modelCards.map((card) => card.key), ["OVRL", "SIG", "BAK"]);
});

test("speech single-file mapping keeps full NISQA dimensions", () => {
  const payload = {
    domain: "speech",
    model: {
      model_key: "nisqa",
      result: {
        model_name: "NISQA",
        grade: "Good",
        duration: 10.1,
        original_sr: 48000,
        original_channels: 1,
        preprocessed: false,
        preprocessed_path: "",
        dimensions: {
          OVRL: { score: 4.0, grade: "Good", description: "overall" },
          NOI: { score: 3.9, grade: "Good", description: "noise" },
          DIS: { score: 4.1, grade: "Good", description: "continuity" },
          COL: { score: 3.8, grade: "Fair", description: "coloration" },
          LOUD: { score: 4.2, grade: "Good", description: "loudness" },
        },
      },
    },
    signal: null,
  };

  const view = preview.buildSingleFileViewModel("eval", payload, "nisqa.wav");
  assert.deepEqual(view.modelCards.map((card) => card.key), ["OVRL", "NOI", "DIS", "COL", "LOUD"]);
});
```

- [ ] **Step 2: Write the failing app-structure test for single-file runtime state**

Add a test to `tests/python/test_web_preview_app.py` asserting the app source contains the new per-page single runtime state and no longer relies only on `evalFile`/`analysisFile`:

```python
def test_web_preview_app_tracks_single_file_runtime_state():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "single:" in text
    assert 'status: "idle"' in text
    assert "result: null" in text
    assert "error: null" in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py -q
npm run test:web-preview
```

Expected:
- pytest fails because the single runtime state is not present
- Node tests fail because `buildSingleFileViewModel(...)` does not exist yet

- [ ] **Step 4: Commit**

```bash
git add tests/python/test_web_preview_app.py tests/web/web_preview_data.test.mjs
git commit -m "test: define single-file real result view model expectations"
```

### Task 2: Implement single-file display-model mapping helpers

**Files:**
- Modify: `audioqas/web/static/web-preview-data.js`
- Test: `tests/web/web_preview_data.test.mjs`

- [ ] **Step 1: Add shared formatting helpers for single-file result rendering**

Extend `audioqas/web/static/web-preview-data.js` with focused helpers for:

```js
function formatChannels(channelCount) {
  return channelCount === 1 ? "Mono" : channelCount === 2 ? "Stereo" : `${channelCount}ch`;
}

function buildTraceText(result) {
  if (!result.preprocessed) return `原始文件 → 直接送入 ${result.model_name}`;
  return `原始文件 → 预处理后送入 ${result.model_name}`;
}
```

- [ ] **Step 2: Add the single-file view model builder**

Implement a new pure function in `audioqas/web/static/web-preview-data.js`:

```js
function buildSingleFileViewModel(page, payload, fileName) {
  const result = payload.model.result;
  const dimensions = result.dimensions || {};
  const orderedModelCards = page === "eval" && payload.model.model_key === "nisqa"
    ? ["OVRL", "NOI", "DIS", "COL", "LOUD"]
    : Object.keys(dimensions);

  return {
    fileName,
    modelName: result.model_name,
    summary: `${result.duration.toFixed(1)}s · ${result.original_sr}Hz · ${formatChannels(result.original_channels)} · 当前模型 ${result.model_name}`,
    traceText: buildTraceText(result),
    primaryMetric: { key: orderedModelCards[0], ...dimensions[orderedModelCards[0]] },
    modelCards: orderedModelCards
      .filter((key) => dimensions[key])
      .map((key) => ({ key, ...dimensions[key] })),
    signalCards: Object.entries(payload.signal?.metrics || {}).map(([key, metric]) => ({ key, ...metric })),
  };
}
```

- [ ] **Step 3: Export the new helper from the module**

Update the module return value in `audioqas/web/static/web-preview-data.js` so tests and app code can access:

```js
return {
  pageMeta,
  viewClassMap,
  compareGroupDefs,
  compareData,
  modelContent,
  getCompareDataset,
  getModelLabel,
  getVisibleGroupsByCount,
  computeComparisonData,
  formatSigned,
  formatScore,
  getStatusClass,
  getDetailColumns,
  buildDetailHeaders,
  buildDetailCell,
  buildSingleFileViewModel,
};
```

- [ ] **Step 4: Run tests to verify the mapping layer passes**

Run:

```bash
npm run test:web-preview
```

Expected:
- Node tests PASS

- [ ] **Step 5: Commit**

```bash
git add audioqas/web/static/web-preview-data.js tests/web/web_preview_data.test.mjs
git commit -m "feat: add single-file result display model mapping"
```

### Task 3: Implement single-file runtime state and staged pseudo-progress

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Test: `tests/python/test_web_preview_app.py`

- [ ] **Step 1: Replace ad hoc file-only runtime state with single-file runtime state**

Update `runtimeState` in `audioqas/web/static/web-preview-app.js` to include:

```js
const runtimeState = {
  single: {
    eval: { file: null, status: "idle", result: null, error: null },
    analysis: { file: null, status: "idle", result: null, error: null },
  },
  compareGroups: {
    eval: {},
    analysis: {},
  },
  compareResults: {
    eval: null,
    analysis: null,
  },
};
```

- [ ] **Step 2: Add explicit staged pseudo-progress helpers**

Add helpers in `audioqas/web/static/web-preview-app.js` such as:

```js
function setSingleProgress(page, label, width) {
  const single = document.querySelector(`[data-scene-root="${page}"] [data-scene="single"]`);
  const progressLabel = single?.querySelector(".progress-label");
  const progressFill = single?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = label;
  if (progressFill) progressFill.style.width = width;
}

function markSingleLoading(page, file) {
  runtimeState.single[page] = { file, status: "loading", result: null, error: null };
  setSingleProgress(page, "上传中 10%", "10%");
}
```

- [ ] **Step 3: Update `evaluateUploadedFile(...)` to use the runtime state**

Refactor the beginning and end of `evaluateUploadedFile(...)`:

```js
async function evaluateUploadedFile(page, file) {
  markSingleLoading(page, file);
  setSingleProgress(page, "预处理中 25%", "25%");
  // fetch...
  setSingleProgress(page, "模型评测中 60%", "60%");
  // await response...
  setSingleProgress(page, "信号分析中 85%", "85%");
  // after json...
  runtimeState.single[page] = { file, status: "success", result: payload, error: null };
  applySingleEvaluation(page, payload, file.name);
  setSingleProgress(page, "100%", "100%");
}
```

On failure:

```js
runtimeState.single[page] = { file, status: "error", result: null, error: String(error) };
setSingleProgress(page, "失败", "0%");
```

- [ ] **Step 4: Run the Python app tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py -q
```

Expected:
- pytest PASS

- [ ] **Step 5: Commit**

```bash
git add audioqas/web/static/web-preview-app.js tests/python/test_web_preview_app.py
git commit -m "feat: add single-file runtime state and staged progress"
```

### Task 4: Make single-file DOM rendering consume the new mapped view model

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `audioqas/web/static/web-preview-data.js`
- Test: `tests/web/web_preview_data.test.mjs`

- [ ] **Step 1: Switch `applySingleEvaluation(...)` to use `buildSingleFileViewModel(...)`**

Refactor the function start:

```js
function applySingleEvaluation(page, payload, fileName) {
  const view = buildSingleFileViewModel(page, payload, fileName);
  const result = payload.model.result;
  const signal = payload.signal;
  // consume `view` instead of reading `result.dimensions` directly everywhere
}
```

- [ ] **Step 2: Render speech-page real results from the mapped view**

Update the eval branch so it uses:

```js
if (title) title.textContent = view.fileName;
if (fileSummary) fileSummary.textContent = view.summary;
if (trace) trace.textContent = view.traceText;
if (heroValue) heroValue.textContent = Number(view.primaryMetric.score).toFixed(2);
if (summaryText) summaryText.textContent = view.primaryMetric.description;
if (grid) {
  grid.innerHTML = view.modelCards.map((card) => `
    <div class="score-card">
      <div class="label">${card.key}</div>
      <div class="number ${scoreClassFromGrade(card.grade)}">${Number(card.score).toFixed(2)}</div>
      <div class="bar"><span style="width:${Math.min(Number(card.score) / 5 * 100, 100)}%;background:var(--accent)"></span></div>
      <div class="grade ${scoreClassFromGrade(card.grade)}">${card.grade}</div>
      <div class="desc">${card.description}</div>
    </div>
  `).join("");
}
```

This step must preserve all five NISQA cards when the selected model is `nisqa`.

- [ ] **Step 3: Render analysis-page real results from the mapped view**

Update the analysis branch similarly:

```js
if (title) title.textContent = view.fileName;
if (heroValue) heroValue.textContent = Number(view.primaryMetric.score).toFixed(1);
if (grid) {
  grid.innerHTML = view.modelCards.map((card) => `
    <div class="score-card">
      <div class="label">${card.key}</div>
      <div class="number ${scoreClassFromGrade(card.grade)}">${Number(card.score).toFixed(1)}</div>
      <div class="bar"><span style="width:${Math.min(Number(card.score) / 10 * 100, 100)}%;background:var(--accent)"></span></div>
      <div class="grade ${scoreClassFromGrade(card.grade)}">${card.grade}</div>
      <div class="desc">${card.description}</div>
    </div>
  `).join("");
}
```

- [ ] **Step 4: Keep the signal metrics section real-data-driven**

Continue rendering metric cards from `payload.signal.metrics`, but normalize through `view.signalCards` so the DOM code only depends on one model:

```js
const metricCards = document.querySelectorAll(`[data-page="${page}"] .metric`);
metricCards.forEach((card, index) => {
  const metric = view.signalCards[index];
  if (!metric) return;
  // assign label/value/grade/description
});
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
npm run test:web-preview
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py tests/python/test_web_preview_data.py -q
```

Expected:
- all tests PASS

- [ ] **Step 6: Commit**

```bash
git add audioqas/web/static/web-preview-app.js audioqas/web/static/web-preview-data.js tests/web/web_preview_data.test.mjs tests/python/test_web_preview_data.py tests/python/test_web_preview_app.py
git commit -m "feat: render single-file real results from mapped view models"
```

### Task 5: Final verification for the single-file real-results slice

**Files:**
- Verify: `audioqas/web/static/web-preview-data.js`
- Verify: `audioqas/web/static/web-preview-app.js`
- Verify: `tests/web/web_preview_data.test.mjs`
- Verify: `tests/python/test_web_preview_app.py`
- Verify: `tests/python/test_web_api.py`

- [ ] **Step 1: Run the complete automated verification**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
```

Expected:
- pytest PASS
- Node tests PASS

- [ ] **Step 2: Start the local preview for manual verification**

Run:

```bash
.venv/bin/python -m audioqas.web.run_local
```

Expected:
- local server starts on `http://127.0.0.1:8000`

- [ ] **Step 3: Manually verify the single-file flow**

Check in the browser:

```text
1. 纯人声评测 -> 单文件测评 -> 上传文件 -> 看到真实结果
2. 切换 NISQA -> 单文件测评 -> 上传文件 -> 看到 5 个 NISQA 维度
3. 综合音频分析 -> 单文件分析 -> 上传文件 -> 看到真实 AudioBox 结果
4. 进度条显示阶段性伪进度，而不是固定 35%
5. 上传失败时看到失败态
```

- [ ] **Step 4: Commit**

```bash
git add audioqas/web/static/web-preview-data.js audioqas/web/static/web-preview-app.js tests/web/web_preview_data.test.mjs tests/python/test_web_preview_app.py
git commit -m "feat: complete single-file real results flow"
```
