# Parallel Compare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable compare evaluation to process up to four files concurrently by default while preserving stable results and truthful UI progress.

**Architecture:** Keep the existing API background task executor for request-level async execution, and add compare-internal bounded parallelism inside `EvaluationService.evaluate_compare()`. Each compare file runs in its own worker with an isolated `EvaluationService(default_task_runners())` when the service uses default runners, so model instances are not shared across worker threads. Progress events are merged through a monotonic aggregator so concurrent updates never make the UI percentage move backward.

**Tech Stack:** Python `ThreadPoolExecutor`, FastAPI background task API, existing `EvaluationService`, pytest, Node/jsdom progress tests, Playwright E2E.

---

## Product Boundary

- Compare internal parallelism is on by default.
- Maximum compare file workers is `4`.
- If the compare contains fewer than four files, workers are capped by file count.
- Single-file evaluation remains unchanged.
- Existing result ordering remains grouped by input order in `CompareTaskResult.items`; ranking still derives from model scores.
- Progress remains real stage progress, not smooth fake animation.

## File Structure

- Modify `audioqas/web/tasks.py`: add default compare worker limit, isolated worker service factory, monotonic compare progress aggregator, and parallel `evaluate_compare()`.
- Modify `tests/python/test_web_tasks.py`: add TDD tests for concurrent compare execution, worker cap, progress monotonicity, and result stability.
- Optionally modify `tests/python/test_web_api.py`: assert compare task progress labels still include all groups after parallel execution.
- Optionally modify `tests/web/web_preview_user_flow.test.mjs`: keep existing progress test compatible with out-of-order worker events.

## Tasks

### Task 1: RED Tests For Parallel Compare

**Files:**
- Modify: `tests/python/test_web_tasks.py`

- [ ] Add a fake runner that blocks in `score()` until three files enter concurrently.
- [ ] Add `test_evaluate_compare_runs_files_concurrently_by_default`.
- [ ] Add `test_evaluate_compare_caps_parallel_workers_at_four`.
- [ ] Add `test_evaluate_compare_progress_percent_is_monotonic_when_events_are_out_of_order`.
- [ ] Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/python/test_web_tasks.py::test_evaluate_compare_runs_files_concurrently_by_default \
  tests/python/test_web_tasks.py::test_evaluate_compare_caps_parallel_workers_at_four \
  tests/python/test_web_tasks.py::test_evaluate_compare_progress_percent_is_monotonic_when_events_are_out_of_order -q
```

Expected before implementation: at least the concurrency test fails because compare is still serial.

### Task 2: Implement Bounded Parallel Compare

**Files:**
- Modify: `audioqas/web/tasks.py`

- [ ] Add constants:

```python
DEFAULT_COMPARE_WORKERS = 4
COMPARE_PROGRESS_BASE = 20
COMPARE_PROGRESS_SPAN = 75
```

- [ ] Add `_CompareProgressAggregator` with thread-safe per-group stage state and monotonic percent output.
- [ ] Add `compare_workers: int = DEFAULT_COMPARE_WORKERS` to `EvaluationService.__init__`.
- [ ] Add `_make_worker_service()` that creates isolated default runners when the service owns default runners.
- [ ] Replace serial list comprehension in `evaluate_compare()` with `ThreadPoolExecutor(max_workers=min(compare_workers, len(groups), 4))`.
- [ ] Preserve result order by storing each future result under its input index and building `single_results` in input order.

### Task 3: Verify API/UI Compatibility

**Files:**
- Modify tests only if needed:
  - `tests/python/test_web_api.py`
  - `tests/web/web_preview_user_flow.test.mjs`

- [ ] Ensure compare task events still include all file labels.
- [ ] Ensure UI progress tests do not assume strict A then B then C event order.

### Task 4: Full Verification

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
npm run test:e2e
npm run test:e2e:real
```

Expected: all pass, with `test:e2e:real` retaining its intentionally skipped damaged WAV case.
