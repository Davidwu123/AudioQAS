from __future__ import annotations

from audioqas.web.history_store import HistoryStore
from audioqas.web.registry import ModelRegistry, default_registry
from audioqas.web.schemas import EvalDomain
from audioqas.web.settings_store import SettingsStore


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
        return {
            "navigation": self.navigation(),
            "models": self.model_catalog(),
            "signal_metrics": self.signal_catalog(),
            "settings": self.settings(),
        }

    def history_items(self) -> list[dict]:
        if not self._history_store:
            return []
        return self._history_store.list_items()

    def history_detail(self, item_id: str) -> dict | None:
        if not self._history_store:
            return None
        return self._history_store.get_item(item_id)

    def settings(self) -> dict:
        if not self._settings_store:
            return {
                "default_eval_model": "dnsmos",
                "default_analysis_model": "audiobox",
                "trace": True,
                "compare_default": "free",
            }
        return self._settings_store.get_settings()

    def update_settings(self, patch: dict) -> dict:
        if not self._settings_store:
            return self.settings()
        return self._settings_store.update_settings(patch)
