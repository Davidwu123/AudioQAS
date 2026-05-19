from audioqas.web import EvalDomain, WebPreviewService, default_registry
from audioqas.web.history_store import InMemoryHistoryStore


def test_navigation_contains_four_pages():
    service = WebPreviewService()
    payload = service.navigation()
    assert [item["page_key"] for item in payload] == ["eval", "analysis", "history", "settings"]


def test_model_catalog_is_domain_based():
    service = WebPreviewService()
    catalog = service.model_catalog()
    assert set(catalog) == {"speech", "mixed"}
    assert catalog["speech"]["primary_model"] == "dnsmos"
    assert catalog["mixed"]["primary_model"] == "audiobox"


def test_speech_domain_supports_multiple_models():
    descriptor = default_registry.model_descriptor(EvalDomain.SPEECH)
    keys = [option.key for option in descriptor.options]
    assert keys == ["dnsmos", "nisqa"]


def test_signal_catalog_keeps_expandable_detail_metrics():
    service = WebPreviewService()
    metrics = service.signal_catalog()
    keys = [metric["key"] for metric in metrics]
    assert "SNR" in keys
    assert "Stereo" in keys
    detail_only = {metric["key"]: metric["detail_only"] for metric in metrics}
    assert detail_only["SNR"] is True
    assert detail_only["Stereo"] is True


def test_bootstrap_payload_is_api_ready():
    service = WebPreviewService()
    payload = service.bootstrap_payload()
    assert "navigation" in payload
    assert "models" in payload
    assert "signal_metrics" in payload


class FakeHistoryStore:
    def list_items(self):
        return [
            {
                "id": "task-1",
                "timestamp": "2026-05-19T10:00:00",
                "page_key": "eval",
                "page_title": "纯人声评测",
                "scene": "single",
                "model_label": "DNSMOS",
                "file_summary": "meeting.wav",
                "summary_metrics": ["OVRL 3.8", "LUFS -14.8"],
                "trace_summary": "原始文件 → 重采样到 16kHz → 送入 DNSMOS",
            }
        ]

    def get_item(self, item_id: str):
        if item_id != "task-1":
            return None
        return {
            "id": "task-1",
            "timestamp": "2026-05-19T10:00:00",
            "page_key": "eval",
            "page_title": "纯人声评测",
            "scene": "single",
            "model_label": "DNSMOS",
            "file_summary": "meeting.wav",
            "summary_metrics": ["OVRL 3.8", "LUFS -14.8"],
            "trace_summary": "原始文件 → 重采样到 16kHz → 送入 DNSMOS",
            "detail": {"note": "ok"},
        }


def test_history_payload_is_available_when_store_is_provided():
    service = WebPreviewService(history_store=FakeHistoryStore())
    items = service.history_items()
    assert len(items) == 1
    assert items[0]["id"] == "task-1"
    assert items[0]["page_key"] == "eval"


def test_history_detail_uses_store_lookup():
    service = WebPreviewService(history_store=FakeHistoryStore())
    item = service.history_detail("task-1")
    assert item is not None
    assert item["detail"]["note"] == "ok"


def test_history_store_can_record_new_items():
    store = InMemoryHistoryStore()
    item = {
        "id": "task-2",
        "timestamp": "2026-05-19T11:00:00",
        "page_key": "analysis",
        "page_title": "综合音频分析",
        "scene": "single",
        "model_label": "AudioBox Aesthetics",
        "file_summary": "mix.wav",
        "summary_metrics": ["PQ 7.8", "LUFS -14.2"],
        "trace_summary": "原始文件 → 转单声道 → 送入 AudioBox Aesthetics",
    }

    store.add_item(item)

    items = store.list_items()
    assert len(items) == 1
    assert items[0]["id"] == "task-2"
    assert store.get_item("task-2") == item
