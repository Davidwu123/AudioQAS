from __future__ import annotations

import json
import os
from typing import Protocol
from pathlib import Path


DEFAULT_SETTINGS = {
    "default_eval_model": "dnsmos",
    "default_analysis_model": "audiobox",
    "trace": True,
    "compare_default": "free",
}


class SettingsStore(Protocol):
    def get_settings(self) -> dict:
        ...

    def update_settings(self, patch: dict) -> dict:
        ...


class InMemorySettingsStore:
    def __init__(self, initial: dict | None = None) -> None:
        self._settings = {**DEFAULT_SETTINGS, **(initial or {})}

    def get_settings(self) -> dict:
        return dict(self._settings)

    def update_settings(self, patch: dict) -> dict:
        self._settings.update({key: value for key, value in patch.items() if value is not None})
        return self.get_settings()


class FileSettingsStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def get_settings(self) -> dict:
        if not self._path.exists():
            return dict(DEFAULT_SETTINGS)
        return {**DEFAULT_SETTINGS, **json.loads(self._path.read_text(encoding="utf-8"))}

    def update_settings(self, patch: dict) -> dict:
        settings = self.get_settings()
        settings.update({key: value for key, value in patch.items() if value is not None})
        self._path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        return dict(settings)


def default_settings_store() -> FileSettingsStore:
    root = Path(os.environ.get("AUDIOQAS_WEB_STATE_DIR", ".tmp/web_state"))
    return FileSettingsStore(root / "settings.json")
