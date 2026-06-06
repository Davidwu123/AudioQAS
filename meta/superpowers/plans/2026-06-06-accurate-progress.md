# Accurate Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fake web-preview progress with observable, stage-based real progress for single-file and compare evaluation, then verify through API tests, web UI tests, E2E, and runtime logs.

**Architecture:** Keep existing synchronous upload APIs for compatibility, and add async task APIs for the web preview: upload creates a task, backend records progress events while evaluation runs, frontend polls task status and renders only server-reported progress. Upload byte progress remains browser XHR based; model internals are represented as truthful started/done stages, not fabricated smooth percentages.

**Tech Stack:** FastAPI, Python `ThreadPoolExecutor`, in-memory task store, existing AudioQAS `EvaluationService`, vanilla JS web preview, Node `node:test`/jsdom, Playwright, pytest.

---

## Current Findings

- `audioqas/web/static/web-preview-app.js` currently fakes progress in fallback fetch by calling `onProgress(10)`, `onProgress(50)`, and `onProgress(100)`.
- `evaluateUploadedFile()` and `evaluateCompareUpload()` pin post-upload processing at fixed `55%`.
- `animateVisibleProgress()` rewrites visible label and width to animated numeric percentages during render, so it can overwrite meaningful labels.
- `audioqas/web/api.py` synchronous upload endpoints only return after model/signal processing finishes, so the frontend cannot observe processing progress from the current API.
- The previous plan `meta/superpowers/plans/2026-05-19-web-preview-user-flow-tests.md` intentionally described staged fake progress. This plan supersedes that behavior.

## Product Boundary

- A progress percentage means completed observable work units, not model-internal compute percentage.
- Upload percentage is real byte progress when XHR upload progress is available.
- Processing percentage is real stage completion: upload saved, preprocess/model/signal started or finished, per compare file A-F.
- During model execution, the UI may remain on the current percentage with a label such as `B 文件模型评测中`; it must not animate upward without a backend event.
- Parallel compare processing is explicitly deferred. This plan should keep compare processing sequential while making progress accurate. A later plan can add bounded worker concurrency and reuse the same progress task store.

## File Structure

- Modify `audioqas/web/progress.py`: new in-memory task registry and progress event helpers.
- Modify `audioqas/web/tasks.py`: add optional progress callbacks to `EvaluationService.evaluate_single()` and `EvaluationService.evaluate_compare()`.
- Modify `audioqas/web/api.py`: add async task endpoints for single and compare upload, preserve existing sync endpoints.
- Modify `audioqas/web/static/web-preview-app.js`: call async task endpoints, poll status, render server progress, remove fake animation behavior.
- Modify `tests/python/test_web_api.py`: cover task creation, status progression, completion, failure, and log-visible progress events.
- Modify `tests/python/test_web_tasks.py`: cover progress callback order in `EvaluationService`.
- Modify `tests/web/web_preview_user_flow.test.mjs`: cover UI progress from server status for single and compare scenarios.
- Modify `tests/e2e/web_preview_e2e.spec.mjs`: verify visible UI no longer relies on fake progress.
- Optional modify `tests/e2e/web_preview_real_backend.spec.mjs`: verify real backend completion still shows final progress.

---

### Task 1: Backend Progress Contract

**Files:**
- Create: `audioqas/web/progress.py`
- Test: `tests/python/test_web_api.py`
- Test: `tests/python/test_web_tasks.py`

- [ ] **Step 1: Write failing progress callback test**

Add to `tests/python/test_web_tasks.py`:

```python
def test_evaluate_single_reports_observable_progress_stages(tmp_path):
    service = make_service()
    events = []

    result = service.evaluate_single(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        file_path=str(tmp_path / "demo.wav"),
        include_signal=True,
        progress_callback=lambda event: events.append(event),
    )

    assert result.model.model_key == "dnsmos"
    assert [event["stage"] for event in events] == [
        "preprocess_started",
        "model_started",
        "model_finished",
        "signal_started",
        "signal_finished",
        "finished",
    ]
    assert events[-1]["percent"] == 100
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_tasks.py::test_evaluate_single_reports_observable_progress_stages -q
```

Expected: FAIL because `progress_callback` is not accepted yet.

- [ ] **Step 3: Add progress primitives**

Create `audioqas/web/progress.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


TERMINAL_STATES = {"finished", "failed"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProgressTask:
    id: str
    scene: str
    status: str = "queued"
    percent: int = 0
    label: str = "排队中"
    detail: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scene": self.scene,
            "status": self.status,
            "percent": self.percent,
            "label": self.label,
            "detail": self.detail,
            "result": self.result,
            "error": self.error,
            "events": list(self.events),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProgressTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, ProgressTask] = {}
        self._lock = Lock()

    def create(self, *, scene: str, task_id: str | None = None) -> ProgressTask:
        task = ProgressTask(id=task_id or f"task_{uuid4().hex[:10]}", scene=scene)
        with self._lock:
            self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.snapshot() if task else None

    def update(
        self,
        task_id: str,
        *,
        status: str | None = None,
        percent: int | None = None,
        label: str | None = None,
        detail: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            task = self._tasks[task_id]
            if status is not None:
                task.status = status
            if percent is not None:
                task.percent = max(0, min(100, int(percent)))
            if label is not None:
                task.label = label
            if detail is not None:
                task.detail = detail
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
            if event is not None:
                task.events.append({**event, "percent": task.percent, "timestamp": utc_now_iso()})
            task.updated_at = utc_now_iso()
            return task.snapshot()
```

- [ ] **Step 4: Add progress callback support in `EvaluationService`**

Modify `audioqas/web/tasks.py`:

```python
from collections.abc import Callable
from typing import Any

ProgressCallback = Callable[[dict[str, Any]], None]
```

Add helper:

```python
def _emit_progress(callback: ProgressCallback | None, **event: Any) -> None:
    if callback:
        callback(event)
```

Update `evaluate_single()` signature:

```python
progress_callback: ProgressCallback | None = None,
progress_prefix: str | None = None,
```

Emit events around existing work:

```python
prefix = f"{progress_prefix} " if progress_prefix else ""
_emit_progress(progress_callback, stage="preprocess_started", percent=10, label=f"{prefix}预处理中")
_emit_progress(progress_callback, stage="model_started", percent=25, label=f"{prefix}模型评测中")
model_result = model_runner.score(file_path)
_emit_progress(progress_callback, stage="model_finished", percent=60, label=f"{prefix}模型评测完成")
if include_signal:
    _emit_progress(progress_callback, stage="signal_started", percent=70, label=f"{prefix}信号分析中")
signal_result = self._runners.signal_runner.analyze(file_path) if include_signal else None
if signal_result is not None:
    _emit_progress(progress_callback, stage="signal_finished", percent=90, label=f"{prefix}信号分析完成")
_emit_progress(progress_callback, stage="finished", percent=100, label=f"{prefix}处理完成")
```

Keep the actual model call and signal call in the same order as today. Do not add parallelism here.

- [ ] **Step 5: Run targeted tests to verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_tasks.py::test_evaluate_single_reports_observable_progress_stages -q
```

Expected: PASS.

---

### Task 2: Async Task API

**Files:**
- Modify: `audioqas/web/api.py`
- Modify: `tests/python/test_web_api.py`

- [ ] **Step 1: Write failing single task API test**

Add to `tests/python/test_web_api.py`:

```python
def test_single_upload_task_reports_progress_and_result():
    client = make_client()
    response = client.post(
        "/api/evaluate/upload-task",
        data={"domain": "speech", "model_key": "dnsmos", "include_signal": "true"},
        files={"file": ("demo.wav", b"audio", "audio/wav")},
        headers={"X-Request-Id": "req_progress_single"},
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    status = client.get(f"/api/evaluate/tasks/{task_id}").json()

    assert status["status"] == "finished"
    assert status["percent"] == 100
    assert status["result"]["task"]["model"]["model_key"] == "dnsmos"
    assert [event["stage"] for event in status["events"]]
```

- [ ] **Step 2: Write failing compare task API test**

Add to `tests/python/test_web_api.py`:

```python
def test_compare_upload_task_reports_file_level_progress_and_result():
    client = make_client()
    response = client.post(
        "/api/evaluate/compare-upload-task",
        data=[
            ("domain", "speech"),
            ("model_key", "dnsmos"),
            ("include_signal", "true"),
            ("base_key", "A"),
            ("keys", "A"),
            ("keys", "B"),
            ("keys", "C"),
        ],
        files=[
            ("files", ("a.wav", b"audio-a", "audio/wav")),
            ("files", ("b.wav", b"audio-b", "audio/wav")),
            ("files", ("c.wav", b"audio-c", "audio/wav")),
        ],
        headers={"X-Request-Id": "req_progress_compare"},
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    status = client.get(f"/api/evaluate/tasks/{task_id}").json()

    assert status["status"] == "finished"
    assert status["percent"] == 100
    assert len(status["result"]["items"]) == 3
    labels = [event["label"] for event in status["events"]]
    assert any("A 文件" in label for label in labels)
    assert any("B 文件" in label for label in labels)
    assert any("C 文件" in label for label in labels)
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_api.py::test_single_upload_task_reports_progress_and_result tests/python/test_web_api.py::test_compare_upload_task_reports_file_level_progress_and_result -q
```

Expected: FAIL because the new endpoints do not exist.

- [ ] **Step 4: Implement task store and endpoints**

In `audioqas/web/api.py`, import:

```python
from concurrent.futures import ThreadPoolExecutor
from audioqas.web.progress import ProgressTaskStore
```

Inside `create_app()` create:

```python
progress_store = ProgressTaskStore()
task_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audioqas-task")
```

Add:

```python
def _progress_callback(task_id: str):
    def callback(event: dict) -> None:
        progress_store.update(
            task_id,
            status="running",
            percent=event.get("percent"),
            label=event.get("label"),
            detail=event.get("stage"),
            event=event,
        )
        with set_event("progress_updated"):
            logger.info(
                "progress_updated task_id=%s stage=%s percent=%s label=%s",
                task_id,
                event.get("stage"),
                event.get("percent"),
                event.get("label"),
            )
    return callback
```

Add status endpoint:

```python
@app.get("/api/evaluate/tasks/{task_id}")
def evaluate_task_status(task_id: str) -> dict:
    snapshot = progress_store.get(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="task not found")
    return snapshot
```

Add `POST /api/evaluate/upload-task` and `POST /api/evaluate/compare-upload-task` by reusing the existing upload validation and serialization logic. The endpoint should:

1. Save upload content synchronously.
2. Create a progress task.
3. Submit evaluation work to `task_executor`.
4. Return `{"task_id": task.id}`.

The worker should:

1. Call `_configure_task_service()`.
2. Call the relevant `task_service.evaluate_*` method with `progress_callback`.
3. Store serialized result and `status="finished", percent=100`.
4. On exception, store `status="failed"`, `error=str(exc)`, and log `progress_failed`.

For the first implementation, it is acceptable that FastAPI TestClient often observes a finished task immediately because the fake service is fast. The API contract still supports polling.

- [ ] **Step 5: Run targeted API tests to verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_api.py::test_single_upload_task_reports_progress_and_result tests/python/test_web_api.py::test_compare_upload_task_reports_file_level_progress_and_result -q
```

Expected: PASS.

---

### Task 3: Frontend Accurate Progress

**Files:**
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `tests/web/web_preview_user_flow.test.mjs`
- Modify: `tests/python/test_web_preview_app.py`

- [ ] **Step 1: Write failing frontend single progress test**

Update or add in `tests/web/web_preview_user_flow.test.mjs`:

```javascript
test("single upload renders backend task progress without fake animation", async () => {
  const taskStatus = [
    { id: "task-single", status: "running", percent: 25, label: "预处理中", result: null, error: null, events: [] },
    { id: "task-single", status: "running", percent: 60, label: "模型评测完成", result: null, error: null, events: [] },
    { id: "task-single", status: "finished", percent: 100, label: "评测完成", result: buildDnsmosSinglePayload(), error: null, events: [] },
  ];
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/upload-task": { task_id: "task-single" },
      "/api/evaluate/tasks/task-single": () => buildJsonResponse(taskStatus.shift() ?? taskStatus.at(-1)),
    },
  });
  try {
    const progressLog = app.captureTextAssignments('[data-page="eval"] [data-scene="single"] .progress-label');
    await app.uploadSingle("eval", "demo.wav");
    progressLog.disconnect();

    assertOrderedIncludes(progressLog.values, ["预处理中", "模型评测完成", "评测完成"]);
    assert.equal(progressLog.values.some((value) => value === "0%"), false);
    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/upload-task"), true);
  } finally {
    await app.close();
  }
});
```

- [ ] **Step 2: Write failing frontend compare progress test**

Add:

```javascript
test("compare upload renders file-level backend task progress", async () => {
  const statuses = [
    { id: "task-compare", status: "running", percent: 45, label: "A 文件信号分析完成 · 1/3 文件完成", result: null, error: null, events: [] },
    { id: "task-compare", status: "running", percent: 70, label: "B 文件信号分析完成 · 2/3 文件完成", result: null, error: null, events: [] },
    { id: "task-compare", status: "finished", percent: 100, label: "对比完成 · 3/3 文件完成", result: buildDnsmosComparePayload(), error: null, events: [] },
  ];
  const app = await bootPreview({
    fetchMap: {
      "/api/history": [],
      "/api/evaluate/compare-upload-task": { task_id: "task-compare" },
      "/api/evaluate/tasks/task-compare": () => buildJsonResponse(statuses.shift() ?? statuses.at(-1)),
    },
  });
  try {
    await app.openCompare("eval");
    const progressLog = app.captureTextAssignments('[data-page="eval"] [data-scene="compare"] .progress-label');
    await app.uploadCompare("eval", { A: "a.wav", B: "b.wav", C: "c.wav" });
    progressLog.disconnect();

    assertOrderedIncludes(progressLog.values, ["1/3 文件完成", "2/3 文件完成", "对比完成"]);
    assert.equal(app.fetchCalls.some((call) => call.url === "/api/evaluate/compare-upload-task"), true);
  } finally {
    await app.close();
  }
});
```

- [ ] **Step 3: Run frontend tests to verify RED**

Run:

```bash
node --test tests/web/web_preview_user_flow.test.mjs --test-name-pattern "backend task progress|file-level backend task progress"
```

Expected: FAIL because frontend still calls sync endpoints or fake animation.

- [ ] **Step 4: Implement task upload and polling in frontend**

In `audioqas/web/static/web-preview-app.js`:

1. Replace sync upload endpoint usage with `/api/evaluate/upload-task` and `/api/evaluate/compare-upload-task`.
2. Add:

```javascript
function setProgressForScene(page, scene, label, percent) {
  const root = document.querySelector(`[data-scene-root="${page}"] [data-scene="${scene}"]`);
  const progressLabel = root?.querySelector(".progress-label");
  const progressFill = root?.querySelector(".progress-fill");
  if (progressLabel) progressLabel.textContent = label;
  if (progressFill) progressFill.style.width = `${Math.max(0, Math.min(100, Number(percent) || 0))}%`;
}

async function pollEvaluationTask(taskId, onStatus) {
  while (true) {
    const response = await fetch(`/api/evaluate/tasks/${taskId}`);
    if (!response.ok) throw new Error(`Task status failed: ${response.status}`);
    const payload = await response.json();
    onStatus(payload);
    if (payload.status === "finished") return payload.result;
    if (payload.status === "failed") throw new Error(payload.error || "Task failed");
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}
```

3. Remove the `animateVisibleProgress()` call from `render()`.
4. Make `animateVisibleProgress()` a no-op or delete it only if no tests depend on the symbol.
5. Ensure done progress labels come from task status and failure does not show `100%`.

- [ ] **Step 5: Add source-level guard**

Update `tests/python/test_web_preview_app.py`:

```python
def test_app_does_not_use_fake_visible_progress_animation():
    text = APP_PATH.read_text()
    assert "animateVisibleProgress();" not in text
    assert "onProgress(10); onProgress(50);" not in text
    assert "/api/evaluate/upload-task" in text
    assert "/api/evaluate/compare-upload-task" in text
```

- [ ] **Step 6: Run targeted frontend tests to verify GREEN**

Run:

```bash
node --test tests/web/web_preview_user_flow.test.mjs --test-name-pattern "backend task progress|file-level backend task progress"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_preview_app.py::test_app_does_not_use_fake_visible_progress_animation -q
```

Expected: PASS.

---

### Task 4: Log and UI Acceptance

**Files:**
- Modify: `tests/e2e/web_preview_e2e.spec.mjs`
- Optional Modify: `tests/e2e/web_preview_real_backend.spec.mjs`

- [ ] **Step 1: Add UI E2E check for non-fake progress**

In `tests/e2e/web_preview_e2e.spec.mjs`, route task endpoints for one single and one compare flow. Assert:

```javascript
await expect(page.locator('[data-page="eval"] [data-scene="single"] .progress-label')).toContainText(/评测完成|处理完成/);
await expect(page.locator('[data-page="eval"] [data-scene="single"] .progress-label')).not.toHaveText("0%");
```

For compare:

```javascript
await expect(page.locator('[data-page="eval"] [data-scene="compare"] .progress-label')).toContainText(/文件完成|对比完成/);
```

- [ ] **Step 2: Add API log check**

Add or update a pytest test to capture logs with `caplog` around `/api/evaluate/upload-task`, then assert `progress_updated` appears with `task_id` and `percent=`.

- [ ] **Step 3: Run targeted E2E/UI/log tests**

Run:

```bash
npm run test:web-preview
npm run test:e2e
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_api.py tests/python/test_web_tasks.py tests/python/test_web_preview_app.py -q
```

Expected: PASS.

---

### Task 5: Full Verification

**Files:**
- No source changes unless verification exposes a real bug.

- [ ] **Step 1: Run project verification**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
npm run test:e2e
```

Expected: PASS.

- [ ] **Step 2: Optional real backend E2E**

If the local runtime dependencies are available, run:

```bash
npm run test:e2e:real
```

Expected: PASS or a dependency-specific skip/failure that is reported explicitly.

- [ ] **Step 3: Manual acceptance notes**

Record in final response:

- Which command verifies backend task progress.
- Which command verifies UI progress.
- Whether logs include `progress_updated`.
- That parallel compare processing is deferred to the next implementation phase.

---

## Future Phase: Compare Parallel Workers

Do not implement in this plan. Later work should:

- Add bounded compare concurrency with default `max_workers=2`.
- Avoid sharing a single model runner instance across workers.
- Preserve the same task progress contract so UI does not need another rewrite.
- Benchmark DNSMOS, NISQA, and AudioBox separately before raising defaults.

