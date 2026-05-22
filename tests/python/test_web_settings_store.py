from audioqas.web.settings_store import InMemorySettingsStore


def test_settings_store_reads_default_values():
    store = InMemorySettingsStore()
    payload = store.get_settings()

    assert payload["default_eval_model"] == "dnsmos"
    assert payload["default_analysis_model"] == "audiobox"
    assert payload["trace"] is True
    assert payload["compare_default"] == "free"
    assert payload["preprocess_resample"] is True
    assert payload["preprocess_to_mono"] is True
    assert payload["preprocess_extract_audio"] is True
    assert payload["export_format"] == "json_csv"
    assert payload["history_retention_days"] == 180


def test_settings_store_updates_values():
    store = InMemorySettingsStore()

    updated = store.update_settings({
        "default_eval_model": "nisqa",
        "trace": False,
        "compare_default": "base",
        "preprocess_resample": False,
        "preprocess_to_mono": False,
        "preprocess_extract_audio": False,
        "export_format": "csv",
        "history_retention_days": 30,
    })

    assert updated["default_eval_model"] == "nisqa"
    assert updated["default_analysis_model"] == "audiobox"
    assert updated["trace"] is False
    assert updated["compare_default"] == "base"
    assert updated["preprocess_resample"] is False
    assert updated["preprocess_to_mono"] is False
    assert updated["preprocess_extract_audio"] is False
    assert updated["export_format"] == "csv"
    assert updated["history_retention_days"] == 30


def test_corrupt_settings_json_returns_defaults(tmp_path):
    """FileSettingsStore should return defaults when the JSON file is corrupt."""
    from audioqas.web.settings_store import FileSettingsStore
    corrupt_file = tmp_path / "corrupt_settings.json"
    corrupt_file.write_text("{invalid json!!!", encoding="utf-8")
    store = FileSettingsStore(corrupt_file)
    settings = store.get_settings()
    assert settings["default_eval_model"] == "dnsmos"
    assert settings["trace"] is True


def test_default_settings_store_resolves_to_absolute_path():
    """default_settings_store() should resolve to an absolute path, not relative."""
    from audioqas.web.settings_store import default_settings_store
    store = default_settings_store()
    assert store._path.is_absolute()


def test_file_settings_store_logs_corrupt_json_fallback(tmp_path):
    from audioqas.logging import setup_logging
    from audioqas.web.settings_store import FileSettingsStore

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    corrupt_file = tmp_path / "corrupt_settings.json"
    corrupt_file.write_text("{invalid json!!!", encoding="utf-8")

    store = FileSettingsStore(corrupt_file)
    store.get_settings()

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "settings_read_fallback" in text
