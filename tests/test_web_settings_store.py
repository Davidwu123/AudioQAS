from audioqas.web.settings_store import InMemorySettingsStore


def test_settings_store_reads_default_values():
    store = InMemorySettingsStore()
    payload = store.get_settings()

    assert payload["default_eval_model"] == "dnsmos"
    assert payload["default_analysis_model"] == "audiobox"
    assert payload["trace"] is True
    assert payload["compare_default"] == "free"


def test_settings_store_updates_values():
    store = InMemorySettingsStore()

    updated = store.update_settings({
        "default_eval_model": "nisqa",
        "trace": False,
        "compare_default": "base",
    })

    assert updated["default_eval_model"] == "nisqa"
    assert updated["default_analysis_model"] == "audiobox"
    assert updated["trace"] is False
    assert updated["compare_default"] == "base"
