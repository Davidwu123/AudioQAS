# Logging Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified logging module that writes rotating log files under `.tmp/log/`, supports startup log-level configuration, propagates `request_id` across request chains, and instruments the first-stage web execution path for branch-aware runtime diagnosis.

**Architecture:** Add a single logging package under `audioqas/logging/` to own formatter, rotating handlers, context propagation, and logger creation. Wire startup initialization from `audioqas/web/run_local.py`, then instrument the first-stage web path (`api -> tasks -> preprocessor`) with structured events so a single `request_id` can reconstruct request flow and branch decisions.

**Tech Stack:** Python `logging`, `logging.handlers.RotatingFileHandler`, `contextvars`, `pytest`, FastAPI

---

### Task 1: Add failing tests for logging infrastructure

**Files:**
- Create: `tests/python/test_logging.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from audioqas.logging import runtime as logging_runtime


def test_setup_logging_creates_log_dir_and_files(tmp_path):
    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    logger = logging_runtime.get_logger("tests.logging")
    logger.info("hello logging")

    assert log_dir.exists()
    assert (log_dir / "audioqas.log").exists()
    assert (log_dir / "audioqas.error.log").exists()


def test_log_context_propagates_request_id_and_scene(tmp_path):
    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    with logging_runtime.log_context(request_id="req_test_001", scene="single"):
        logging_runtime.get_logger("tests.logging").info("context visible")

    text = (log_dir / "audioqas.log").read_text(encoding="utf-8")
    assert "[req_test_001]" in text
    assert "[single]" in text


def test_error_log_receives_error_entries(tmp_path):
    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    logging_runtime.get_logger("tests.logging").error("boom")

    app_text = (log_dir / "audioqas.log").read_text(encoding="utf-8")
    error_text = (log_dir / "audioqas.error.log").read_text(encoding="utf-8")
    assert "boom" in app_text
    assert "boom" in error_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_logging.py -q`
Expected: FAIL because `audioqas.logging` module does not exist yet

### Task 2: Implement unified logging runtime

**Files:**
- Create: `audioqas/logging/__init__.py`
- Create: `audioqas/logging/runtime.py`
- Modify: `audioqas/web/run_local.py`

- [ ] **Step 1: Write minimal logging runtime implementation**

```python
# audioqas/logging/__init__.py
from audioqas.logging.runtime import get_logger, log_context, setup_logging

__all__ = ["get_logger", "log_context", "setup_logging"]
```

```python
# audioqas/logging/runtime.py
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path


_request_id_var: ContextVar[str] = ContextVar("audioqas_request_id", default="-")
_scene_var: ContextVar[str] = ContextVar("audioqas_scene", default="-")
_event_var: ContextVar[str] = ContextVar("audioqas_event", default="-")
_configured = False


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        record.scene = _scene_var.get()
        record.event = _event_var.get()
        record.level_short = record.levelname[:1]
        return True


def _formatter() -> logging.Formatter:
    return logging.Formatter(
        "[%(asctime)s.%(msecs)03d][%(thread)d][%(level_short)s][%(request_id)s][%(scene)s][%(event)s]:(%(filename)s:%(lineno)d): [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _rotating_handler(path: Path, *, level: int, max_bytes: int, backup_count: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(_formatter())
    handler.addFilter(_ContextFilter())
    return handler


def setup_logging(
    *,
    log_dir: str | Path | None = None,
    level: str | None = None,
    max_mb: int | None = None,
    backup_count: int | None = None,
) -> None:
    global _configured

    resolved_dir = Path(log_dir or os.environ.get("AUDIOQAS_LOG_DIR") or Path(__file__).resolve().parents[2] / "log")
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_level = getattr(logging, (level or os.environ.get("AUDIOQAS_LOG_LEVEL", "DEBUG")).upper(), logging.DEBUG)
    resolved_max_bytes = int((max_mb or int(os.environ.get("AUDIOQAS_LOG_MAX_MB", "20"))) * 1024 * 1024)
    resolved_backup_count = backup_count or int(os.environ.get("AUDIOQAS_LOG_BACKUP_COUNT", "20"))

    root = logging.getLogger("audioqas")
    root.setLevel(resolved_level)
    root.handlers.clear()
    root.propagate = False

    app_handler = _rotating_handler(
        resolved_dir / "audioqas.log",
        level=resolved_level,
        max_bytes=resolved_max_bytes,
        backup_count=resolved_backup_count,
    )
    error_handler = _rotating_handler(
        resolved_dir / "audioqas.error.log",
        level=logging.ERROR,
        max_bytes=resolved_max_bytes,
        backup_count=resolved_backup_count,
    )

    root.addHandler(app_handler)
    root.addHandler(error_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    if not _configured:
        setup_logging()
    return logging.getLogger(f"audioqas.{name}" if not name.startswith("audioqas.") else name)


@contextmanager
def log_context(*, request_id: str | None = None, scene: str | None = None, event: str | None = None):
    tokens = []
    if request_id is not None:
        tokens.append((_request_id_var, _request_id_var.set(request_id)))
    if scene is not None:
        tokens.append((_scene_var, _scene_var.set(scene)))
    if event is not None:
        tokens.append((_event_var, _event_var.set(event)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
```

```python
# audioqas/web/run_local.py
from audioqas.logging import setup_logging


def main() -> None:
    setup_logging()
    uvicorn.run(...)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_logging.py -q`
Expected: PASS

### Task 3: Add failing tests for API/task request_id flow

**Files:**
- Modify: `tests/python/test_web_api.py`
- Modify: `tests/python/test_web_tasks.py`

- [ ] **Step 1: Write failing tests**

```python
def test_health_request_writes_request_received_log(tmp_path, monkeypatch):
    from audioqas.logging import setup_logging
    from audioqas.web.api import create_app

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))

    response = client.get("/api/health")

    assert response.status_code == 200
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "request_received" in text
    assert "[health]" in text
```

```python
def test_evaluate_single_logs_task_events(tmp_path):
    from audioqas.logging import setup_logging
    from audioqas.web.tasks import EvaluationService, TaskRunners

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    ...
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "task_started" in text
    assert "task_finished" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_api.py tests/python/test_web_tasks.py -q`
Expected: FAIL because request/task logs are not emitted yet

### Task 4: Instrument API and task orchestration

**Files:**
- Modify: `audioqas/web/api.py`
- Modify: `audioqas/web/tasks.py`

- [ ] **Step 1: Add request-id generation and API lifecycle logs**

```python
from uuid import uuid4

from audioqas.logging import get_logger, log_context

logger = get_logger(__name__)


def _new_request_id(prefix: str) -> str:
    return f"req_{prefix}_{uuid4().hex[:8]}"
```

Add `request_received`, `request_finished`, and `request_failed` logs in:
- `/api/health`
- `/api/settings`
- `/api/evaluate/single`
- `/api/evaluate/batch`
- `/api/evaluate/compare`

- [ ] **Step 2: Add task lifecycle logs**

```python
logger = get_logger(__name__)

logger.info("task_started domain=%s model=%s include_signal=%s file=%s", ...)
logger.info("task_finished domain=%s model=%s file=%s", ...)
```

Instrument:
- `evaluate_single`
- `evaluate_batch`
- `evaluate_compare`

- [ ] **Step 3: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_api.py tests/python/test_web_tasks.py -q`
Expected: PASS

### Task 5: Add failing tests for preprocessing branch logs

**Files:**
- Modify: `tests/python/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
def test_dnsmos_preprocess_logs_passthrough_branch(tmp_path, monkeypatch):
    import numpy as np
    from audioqas.logging import setup_logging
    from audioqas.models import dnsmos

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    monkeypatch.setattr(dnsmos.sf, "read", lambda path: (np.zeros(16000), 16000))

    dnsmos._preprocess_audio("sample.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "branch=passthrough" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_models.py -q`
Expected: FAIL because preprocessing branch logs do not exist yet

### Task 6: Instrument preprocessing decisions

**Files:**
- Modify: `audioqas/core/preprocessor.py`
- Modify: `audioqas/models/dnsmos.py`
- Modify: `audioqas/models/nisqa.py`
- Modify: `audioqas/models/audiobox_aesthetics.py`
- Modify: `audioqas/models/analysis.py`

- [ ] **Step 1: Add branch-aware preprocessing logs**

Add logs for:
- `branch=video_extract`
- `branch=mono_convert`
- `branch=resample`
- `branch=passthrough`
- `preprocess_succeeded`

- [ ] **Step 2: Run targeted model tests**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_models.py -q`
Expected: PASS

### Task 7: Verify full first-stage integration

**Files:**
- Modify: `todo.md`

- [ ] **Step 1: Run repository verification**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q`
Expected: PASS

- [ ] **Step 2: Run preview tests**

Run: `npm run test:web-preview`
Expected: PASS

- [ ] **Step 3: Update todo tracking**

Mark first-stage logging items as completed or in-progress in `todo.md`.
