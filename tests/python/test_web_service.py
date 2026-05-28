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


def test_signal_catalog_only_includes_computed_metrics():
    service = WebPreviewService()
    metrics = service.signal_catalog()
    keys = [metric["key"] for metric in metrics]
    assert "LUFS" in keys
    assert "TruePeak" in keys
    assert "THD" in keys
    assert "SNR" not in keys
    assert "Stereo" not in keys


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


def test_registry_dimensions_match_model_output():
    """Each ModelOption.dimensions should match the actual scorer's dimensions property."""
    from audioqas.models.dnsmos import DNSMOSScorer
    from audioqas.models.nisqa import NISQAScorer
    from audioqas.models.audiobox_aesthetics import AudioBoxAestheticsScorer

    speech_descriptor = default_registry.model_descriptor(EvalDomain.SPEECH)
    for option in speech_descriptor.options:
        if option.key == "dnsmos":
            assert tuple(option.dimensions) == tuple(DNSMOSScorer().dimensions)
        elif option.key == "nisqa":
            assert tuple(option.dimensions) == tuple(NISQAScorer().dimensions)

    mixed_descriptor = default_registry.model_descriptor(EvalDomain.MIXED)
    for option in mixed_descriptor.options:
        if option.key == "audiobox":
            assert tuple(option.dimensions) == tuple(AudioBoxAestheticsScorer().dimensions)


def test_bootstrap_logs_service_event(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    service = WebPreviewService()

    service.bootstrap_payload()

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "bootstrap_payload_built" in text


def test_audioqas_bootstrap_script_exists_and_is_executable():
    import os
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "audioqas-bootstrap"
    assert script.exists()
    assert os.access(script, os.X_OK)
