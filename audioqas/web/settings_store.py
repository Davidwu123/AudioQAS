from __future__ import annotations

import json
import os
from typing import Protocol
from pathlib import Path

from audioqas.logging import get_logger, set_event

logger = get_logger(__name__)


DEFAULT_SETTINGS = {
    "default_eval_model": "dnsmos",
    "default_analysis_model": "audiobox",
    "trace": True,
    "compare_default": "free",
    "preprocess_resample": True,
    "preprocess_to_mono": True,
    "preprocess_extract_audio": True,
    "export_format": "json_csv",
    "history_retention_days": 180,
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
            with set_event("settings_read_default"):
                logger.info("settings_read_default path=%s reason=missing_file", self._path)
            return dict(DEFAULT_SETTINGS)
        try:
            stored = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            with set_event("settings_read_fallback"):
                logger.warning("settings_read_fallback path=%s reason=invalid_json", self._path)
            return dict(DEFAULT_SETTINGS)
        merged = {**DEFAULT_SETTINGS, **stored}
        with set_event("settings_read_succeeded"):
            logger.info("settings_read_succeeded path=%s", self._path)
        return merged

    def update_settings(self, patch: dict) -> dict:
        settings = self.get_settings()
        settings.update({key: value for key, value in patch.items() if value is not None})
        self._path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        with set_event("settings_write_succeeded"):
            logger.info("settings_write_succeeded path=%s keys=%s", self._path, sorted(patch.keys()))
        return dict(settings)


def default_settings_store() -> FileSettingsStore:
    default_root = str(Path(__file__).resolve().parents[2] / ".tmp" / "web_state")
    root = Path(os.environ.get("AUDIOQAS_WEB_STATE_DIR", default_root))
    return FileSettingsStore(root / "settings.json")
