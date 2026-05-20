from __future__ import annotations

import json
import os
from typing import Protocol
from pathlib import Path

from audioqas.logging import get_logger, set_event

logger = get_logger(__name__)


class HistoryStore(Protocol):
    def list_items(self) -> list[dict]:
        ...

    def get_item(self, item_id: str) -> dict | None:
        ...

    def add_item(self, item: dict) -> None:
        ...


class InMemoryHistoryStore:
    def __init__(self, items: list[dict] | None = None) -> None:
        self._items = items or []

    def list_items(self) -> list[dict]:
        return list(self._items)

    def get_item(self, item_id: str) -> dict | None:
        return next((item for item in self._items if item.get("id") == item_id), None)

    def add_item(self, item: dict) -> None:
        self._items.insert(0, dict(item))


class FileHistoryStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict]:
        if not self._path.exists():
            with set_event("history_read_empty"):
                logger.info("history_read_empty path=%s", self._path)
            return []
        try:
            items = json.loads(self._path.read_text(encoding="utf-8"))
            with set_event("history_read_succeeded"):
                logger.info("history_read_succeeded path=%s count=%s", self._path, len(items))
            return items
        except json.JSONDecodeError:
            with set_event("history_read_fallback"):
                logger.warning("history_read_fallback path=%s reason=invalid_json", self._path)
            return []

    def _write(self, items: list[dict]) -> None:
        self._path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        with set_event("history_write_succeeded"):
            logger.info("history_write_succeeded path=%s count=%s", self._path, len(items))

    def list_items(self) -> list[dict]:
        return self._read()

    def get_item(self, item_id: str) -> dict | None:
        return next((item for item in self._read() if item.get("id") == item_id), None)

    def add_item(self, item: dict) -> None:
        items = self._read()
        items.insert(0, dict(item))
        self._write(items)


def default_history_store() -> FileHistoryStore:
    default_root = str(Path(__file__).resolve().parents[2] / ".tmp" / "web_state")
    root = Path(os.environ.get("AUDIOQAS_WEB_STATE_DIR", default_root))
    return FileHistoryStore(root / "history.json")
