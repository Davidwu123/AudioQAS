from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


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
