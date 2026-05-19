from __future__ import annotations

import json
import os
from typing import Protocol
from pathlib import Path


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
            return []
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, items: list[dict]) -> None:
        self._path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_items(self) -> list[dict]:
        return self._read()

    def get_item(self, item_id: str) -> dict | None:
        return next((item for item in self._read() if item.get("id") == item_id), None)

    def add_item(self, item: dict) -> None:
        items = self._read()
        items.insert(0, dict(item))
        self._write(items)


def default_history_store() -> FileHistoryStore:
    root = Path(os.environ.get("AUDIOQAS_WEB_STATE_DIR", ".tmp/web_state"))
    return FileHistoryStore(root / "history.json")
