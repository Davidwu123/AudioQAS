from __future__ import annotations

from datetime import datetime, timedelta

from audioqas.logging import get_logger, set_event
from audioqas.web.history_store import HistoryStore
from audioqas.web.registry import ModelRegistry, default_registry
from audioqas.web.schemas import EvalDomain
from audioqas.web.settings_store import SettingsStore

logger = get_logger(__name__)


def _parse_history_timestamp(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


class WebPreviewService:
    def __init__(
        self,
        registry: ModelRegistry | None = None,
        history_store: HistoryStore | None = None,
        settings_store: SettingsStore | None = None,
    ) -> None:
        self._registry = registry or default_registry
        self._history_store = history_store
        self._settings_store = settings_store

    def navigation(self) -> list[dict]:
        return [
            {
                "page_key": task.page_key,
                "title": task.title,
                "subtitle": task.subtitle,
                "domain": task.domain.value if task.domain else None,
                "capabilities": list(task.capabilities),
            }
            for task in self._registry.tasks()
        ]

    def model_catalog(self) -> dict[str, dict]:
        catalog: dict[str, dict] = {}
        for domain in (EvalDomain.SPEECH, EvalDomain.MIXED):
            descriptor = self._registry.model_descriptor(domain)
            catalog[domain.value] = {
                "primary_model": descriptor.primary_model,
                "supports_signal_analysis": descriptor.supports_signal_analysis,
                "options": [
                    {
                        "key": option.key,
                        "label": option.label,
                        "short_tag": option.short_tag,
                        "dimensions": list(option.dimensions),
                    }
                    for option in descriptor.options
                ],
            }
        return catalog

    def signal_catalog(self) -> list[dict]:
        return [
            {
                "key": metric.key,
                "label": metric.label,
                "unit": metric.unit,
                "detail_only": metric.detail_only,
            }
            for metric in self._registry.signal_metrics()
        ]

    def bootstrap_payload(self) -> dict:
        payload = {
            "navigation": self.navigation(),
            "models": self.model_catalog(),
            "signal_metrics": self.signal_catalog(),
            "settings": self.settings(),
        }
        with set_event("bootstrap_payload_built"):
            logger.info("bootstrap_payload_built navigation=%s", len(payload["navigation"]))
        return payload

    def history_items(self) -> list[dict]:
        if not self._history_store:
            return []
        items = self._history_store.list_items()
        retention_days = self.settings().get("history_retention_days", 180)
        if retention_days < 99999:
            cutoff = datetime.now() - timedelta(days=retention_days)
            items = [
                item for item in items
                if (_parse_history_timestamp(item["timestamp"]) or datetime.min) >= cutoff
            ]
        with set_event("history_items_loaded"):
            logger.info("history_items_loaded count=%s", len(items))
        return items

    def history_detail(self, item_id: str) -> dict | None:
        if not self._history_store:
            return None
        item = self._history_store.get_item(item_id)
        with set_event("history_detail_loaded"):
            logger.info("history_detail_loaded item_id=%s found=%s", item_id, item is not None)
        return item

    def settings(self) -> dict:
        if not self._settings_store:
            return {
                "default_eval_model": "dnsmos",
                "default_analysis_model": "audiobox",
                "trace": True,
                "compare_default": "free",
            }
        settings = self._settings_store.get_settings()
        with set_event("settings_loaded"):
            logger.info("settings_loaded compare_default=%s", settings["compare_default"])
        return settings

    def update_settings(self, patch: dict) -> dict:
        if not self._settings_store:
            return self.settings()
        settings = self._settings_store.update_settings(patch)
        with set_event("settings_updated"):
            logger.info("settings_updated keys=%s", sorted(patch.keys()))
        return settings
