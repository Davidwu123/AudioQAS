from pathlib import Path
import os

from fastapi.testclient import TestClient

from audioqas.web.api import create_app
from audioqas.web.runtime import (
    BatchTaskResult,
    CompareGroupResult,
    CompareTaskResult,
    ModelExecutionResult,
    SignalExecutionResult,
    SingleTaskResult,
)
from audioqas.web.schemas import EvalDomain


ROOT = Path(__file__).resolve().parents[2]
REAL_FILE_1 = ROOT / "tests" / "fixtures" / "test1.wav"
REAL_FILE_2 = ROOT / "tests" / "fixtures" / "test2.wav"


def _with_real_preprocess_dir(tmp_path, monkeypatch) -> None:
    target = tmp_path / "preprocessed"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AUDIOQAS_PREPROCESS_DIR", str(target))
    state_dir = tmp_path / "web_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AUDIOQAS_WEB_STATE_DIR", str(state_dir))


class FakeEvaluationService:
    def evaluate_single(self, *, domain, model_key, file_path, include_signal=True):
        model_result = {
            "eval_type": "mos",
            "model_name": "DNSMOS" if model_key == "dnsmos" else "NISQA",
            "model_version": "test",
            "dimensions": {"OVRL": {"score": 4.0, "grade": "Good", "description": "ok"}},
            "grade": "Good",
            "descriptions": {"OVRL": "ok"},
            "timestamp": "2026-05-18T00:00:00",
            "file_path": file_path,
            "original_sr": 16000,
            "original_channels": 1,
            "duration": 1.0,
            "preprocessed": False,
            "preprocessed_path": file_path,
        }
        signal_result = None
        if include_signal:
            signal_result = {
                "eval_type": "analysis",
                "model_name": "AudioAnalyzer",
                "model_version": "test",
                "metrics": {},
                "grade": "Good",
                "timestamp": "2026-05-18T00:00:00",
                "file_path": file_path,
                "original_sr": 16000,
                "original_channels": 1,
                "duration": 1.0,
                "preprocessed": False,
                "preprocessed_path": file_path,
            }
        return SingleTaskResult(
            domain=domain,
            file_path=file_path,
            model=ModelExecutionResult(model_key=model_key, domain=domain, result=model_result),
            signal=SignalExecutionResult(signal_result) if signal_result else None,
        )

    def evaluate_batch(self, *, domain, model_key, file_paths, include_signal=True):
        items = tuple(
            self.evaluate_single(
                domain=domain,
                model_key=model_key,
                file_path=file_path,
                include_signal=include_signal,
            )
            for file_path in file_paths
        )
        return BatchTaskResult(domain=domain, model_key=model_key, items=items)

    def evaluate_compare(self, *, domain, model_key, groups, base_key=None, include_signal=True):
        items = []
        for index, group in enumerate(groups, start=1):
            task = self.evaluate_single(
                domain=domain,
                model_key=model_key,
                file_path=group.file_path,
                include_signal=include_signal,
            )
            items.append(
                CompareGroupResult(
                    key=group.key,
                    file_path=group.file_path,
                    task=task,
                    rank=index,
                    delta_from_base=0.0 if group.key == base_key else float(index),
                )
            )
        return CompareTaskResult(
            domain=domain,
            model_key=model_key,
            base_key=base_key,
            items=tuple(items),
        )


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
        if item_id == "task-1":
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
        return None


def make_client() -> TestClient:
    return TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))


def test_health_endpoint():
    client = make_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_request_writes_request_received_log(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    client = make_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "request_received" in text
    assert "[health]" in text


def test_root_serves_web_preview_html():
    client = make_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AudioQAS" in response.text


def test_design_static_assets_are_mounted():
    client = make_client()
    response = client.get("/static-preview/web-preview-data.js")
    assert response.status_code == 200
    assert "AudioQASWebPreview" in response.text


def test_bootstrap_endpoint():
    client = make_client()
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert "navigation" in payload
    assert "models" in payload
    assert "signal_metrics" in payload


def test_navigation_endpoint():
    client = make_client()
    response = client.get("/api/navigation")
    assert response.status_code == 200
    payload = response.json()
    assert [item["page_key"] for item in payload] == ["eval", "analysis", "history", "settings"]


def test_models_endpoint():
    client = make_client()
    response = client.get("/api/models")
    assert response.status_code == 200
    payload = response.json()
    assert payload["speech"]["primary_model"] == "dnsmos"
    assert payload["mixed"]["primary_model"] == "audiobox"


def test_signal_metrics_endpoint():
    client = make_client()
    response = client.get("/api/signal-metrics")
    assert response.status_code == 200
    payload = response.json()
    keys = [metric["key"] for metric in payload]
    assert "LUFS" in keys
    assert "TruePeak" in keys
    assert "THD" in keys
    assert "SNR" not in keys
    assert "Stereo" not in keys


def test_history_list_endpoint():
    client = make_client()
    response = client.get("/api/history")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "task-1"
    assert payload[0]["page_key"] == "eval"


def test_history_detail_endpoint():
    client = make_client()
    response = client.get("/api/history/task-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "task-1"
    assert payload["detail"]["note"] == "ok"


def test_evaluate_single_endpoint():
    client = make_client()
    response = client.post(
        "/api/evaluate/single",
        json={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "file_path": "sample.wav",
            "include_signal": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model"]["model_key"] == "dnsmos"
    assert payload["model"]["result"]["file_path"] == "sample.wav"
    assert payload["signal"] is not None


def test_evaluate_single_without_signal():
    client = make_client()
    response = client.post(
        "/api/evaluate/single",
        json={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "nisqa",
            "file_path": "sample.wav",
            "include_signal": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"]["model_key"] == "nisqa"
    assert payload["signal"] is None


def test_evaluate_batch_endpoint():
    client = make_client()
    response = client.post(
        "/api/evaluate/batch",
        json={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "file_paths": ["a.wav", "b.wav"],
            "include_signal": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model_key"] == "dnsmos"
    assert len(payload["items"]) == 2


def test_evaluate_compare_endpoint():
    client = make_client()
    response = client.post(
        "/api/evaluate/compare",
        json={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "base_key": "A",
            "groups": [
                {"key": "A", "file_path": "a.wav"},
                {"key": "B", "file_path": "b.wav"},
            ],
            "include_signal": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["base_key"] == "A"
    assert len(payload["items"]) == 2
    assert payload["items"][0]["key"] == "A"
    assert "rank" in payload["items"][0]
    assert "delta_from_base" in payload["items"][1]


def test_evaluate_upload_endpoint():
    client = make_client()
    response = client.post(
        "/api/evaluate/upload",
        data={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "include_signal": "true",
        },
        files={"file": ("sample.wav", b"fake wav bytes", "audio/wav")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model"]["model_key"] == "dnsmos"
    assert payload["signal"] is not None


def test_evaluate_upload_batch_endpoint():
    client = make_client()
    response = client.post(
        "/api/evaluate/upload-batch",
        data={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "include_signal": "true",
        },
        files=[
            ("files", ("a.wav", b"a bytes", "audio/wav")),
            ("files", ("b.wav", b"b bytes", "audio/wav")),
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model_key"] == "dnsmos"
    assert len(payload["items"]) == 2


def test_evaluate_compare_upload_endpoint():
    client = make_client()
    response = client.post(
        "/api/evaluate/compare-upload",
        data={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "base_key": "A",
            "include_signal": "false",
            "keys": ["A", "B"],
        },
        files=[
            ("files", ("a.wav", b"a bytes", "audio/wav")),
            ("files", ("b.wav", b"b bytes", "audio/wav")),
        ],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["base_key"] == "A"
    assert len(payload["items"]) == 2


def test_real_upload_dnsmos_endpoint_contract(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())
    with REAL_FILE_1.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": EvalDomain.SPEECH.value,
                "model_key": "dnsmos",
                "include_signal": "true",
            },
            files={"file": (REAL_FILE_1.name, handle, "audio/wav")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model"]["model_key"] == "dnsmos"
    assert payload["model"]["result"]["original_sr"] == 48000
    assert payload["model"]["result"]["original_channels"] == 2
    assert set(payload["model"]["result"]["dimensions"]) == {"OVRL", "SIG", "BAK"}
    assert payload["signal"] is not None
    assert {"LUFS", "LRA", "TruePeak", "Clipping", "THD"}.issubset(payload["signal"]["metrics"])


def test_real_upload_nisqa_endpoint_contract(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())
    with REAL_FILE_1.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": EvalDomain.SPEECH.value,
                "model_key": "nisqa",
                "include_signal": "true",
            },
            files={"file": (REAL_FILE_1.name, handle, "audio/wav")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model"]["model_key"] == "nisqa"
    assert payload["model"]["result"]["original_sr"] == 48000
    assert payload["model"]["result"]["original_channels"] == 2
    assert set(payload["model"]["result"]["dimensions"]) == {"OVRL", "NOI", "DIS", "COL", "LOUD"}
    assert payload["signal"] is not None


def test_real_upload_audiobox_endpoint_contract(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())
    with REAL_FILE_1.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": EvalDomain.MIXED.value,
                "model_key": "audiobox",
                "include_signal": "true",
            },
            files={"file": (REAL_FILE_1.name, handle, "audio/wav")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "mixed"
    assert payload["model"]["model_key"] == "audiobox"
    assert payload["model"]["result"]["original_sr"] == 48000
    assert payload["model"]["result"]["original_channels"] == 2
    assert set(payload["model"]["result"]["dimensions"]) == {"PQ", "CE", "CU", "PC"}
    assert payload["signal"] is not None


def test_real_compare_upload_dnsmos_endpoint_contract(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())
    with REAL_FILE_1.open("rb") as file_a, REAL_FILE_2.open("rb") as file_b:
        response = client.post(
            "/api/evaluate/compare-upload",
            data={
                "domain": EvalDomain.SPEECH.value,
                "model_key": "dnsmos",
                "base_key": "A",
                "include_signal": "true",
                "keys": ["A", "B"],
            },
            files=[
                ("files", (REAL_FILE_1.name, file_a, "audio/wav")),
                ("files", (REAL_FILE_2.name, file_b, "audio/wav")),
            ],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "speech"
    assert payload["model_key"] == "dnsmos"
    assert payload["base_key"] == "A"
    assert len(payload["items"]) == 2
    assert {item["key"] for item in payload["items"]} == {"A", "B"}
    assert all(item["rank"] in (1, 2) for item in payload["items"])
    assert all(item["task"]["signal"] is not None for item in payload["items"])


def test_real_compare_upload_audiobox_endpoint_contract(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())
    with REAL_FILE_1.open("rb") as file_a, REAL_FILE_2.open("rb") as file_b:
        response = client.post(
            "/api/evaluate/compare-upload",
            data={
                "domain": EvalDomain.MIXED.value,
                "model_key": "audiobox",
                "base_key": "A",
                "include_signal": "true",
                "keys": ["A", "B"],
            },
            files=[
                ("files", (REAL_FILE_1.name, file_a, "audio/wav")),
                ("files", (REAL_FILE_2.name, file_b, "audio/wav")),
            ],
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "mixed"
    assert payload["model_key"] == "audiobox"
    assert payload["base_key"] == "A"
    assert len(payload["items"]) == 2
    assert {item["key"] for item in payload["items"]} == {"A", "B"}
    assert all(item["rank"] in (1, 2) for item in payload["items"])
    assert all(item["task"]["signal"] is not None for item in payload["items"])


def test_real_upload_writes_history_item(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    from audioqas.web.history_store import InMemoryHistoryStore

    store = InMemoryHistoryStore()
    client = TestClient(create_app(history_store=store))
    with REAL_FILE_1.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": EvalDomain.SPEECH.value,
                "model_key": "dnsmos",
                "include_signal": "true",
            },
            files={"file": (REAL_FILE_1.name, handle, "audio/wav")},
        )

    assert response.status_code == 200
    history = client.get("/api/history")
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["page_key"] == "eval"
    assert items[0]["scene"] == "single"
    assert items[0]["model_label"] == "DNSMOS"
    assert REAL_FILE_1.name in items[0]["file_summary"]
    assert items[0]["summary_metrics"]
    assert items[0]["trace_summary"]


def test_settings_endpoints_roundtrip_state():
    from audioqas.web.settings_store import InMemorySettingsStore

    store = InMemorySettingsStore()
    client = TestClient(create_app(settings_store=store))

    response = client.get("/api/settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["default_eval_model"] == "dnsmos"
    assert payload["trace"] is True
    assert payload["compare_default"] == "free"
    assert payload["preprocess_resample"] is True
    assert payload["preprocess_to_mono"] is True
    assert payload["preprocess_extract_audio"] is True
    assert payload["export_format"] == "json_csv"
    assert payload["history_retention_days"] == 180

    response = client.post(
        "/api/settings",
        json={
            "default_eval_model": "nisqa",
            "trace": False,
            "compare_default": "base",
            "preprocess_resample": False,
            "preprocess_to_mono": False,
            "preprocess_extract_audio": False,
            "export_format": "csv",
            "history_retention_days": 30,
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["default_eval_model"] == "nisqa"
    assert updated["trace"] is False
    assert updated["compare_default"] == "base"
    assert updated["preprocess_resample"] is False
    assert updated["preprocess_to_mono"] is False
    assert updated["preprocess_extract_audio"] is False
    assert updated["export_format"] == "csv"
    assert updated["history_retention_days"] == 30

    response = client.get("/api/settings")
    assert response.status_code == 200
    persisted = response.json()
    assert persisted["default_eval_model"] == "nisqa"
    assert persisted["trace"] is False
    assert persisted["compare_default"] == "base"
    assert persisted["preprocess_resample"] is False
    assert persisted["preprocess_to_mono"] is False
    assert persisted["preprocess_extract_audio"] is False
    assert persisted["export_format"] == "csv"
    assert persisted["history_retention_days"] == 30


def test_default_app_persists_history_and_settings(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("AUDIOQAS_WEB_STATE_DIR", str(tmp_path / "web_state"))
    client = TestClient(create_app())

    response = client.get("/api/history")
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/api/settings")
    assert response.status_code == 200
    assert response.json()["compare_default"] == "free"
    assert response.json()["export_format"] == "json_csv"

    response = client.post(
        "/api/settings",
        json={
            "compare_default": "base",
            "trace": False,
            "export_format": "csv",
            "history_retention_days": 30,
        },
    )
    assert response.status_code == 200

    with REAL_FILE_1.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": EvalDomain.SPEECH.value,
                "model_key": "dnsmos",
                "include_signal": "true",
            },
            files={"file": (REAL_FILE_1.name, handle, "audio/wav")},
        )
    assert response.status_code == 200

    reloaded = TestClient(create_app())
    settings = reloaded.get("/api/settings")
    history = reloaded.get("/api/history")
    assert settings.status_code == 200
    assert history.status_code == 200
    assert settings.json()["compare_default"] == "base"
    assert settings.json()["trace"] is False
    assert settings.json()["export_format"] == "csv"
    assert settings.json()["history_retention_days"] == 30
    assert len(history.json()) == 1


def test_upload_filename_collision(tmp_path, monkeypatch):
    """Two uploads with the same filename should get different stored paths (UUID prefix)."""
    from audioqas.web.history_store import InMemoryHistoryStore
    store = InMemoryHistoryStore()
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=store))
    response1 = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "true"},
        files={"file": ("same.wav", b"fake1", "audio/wav")},
    )
    response2 = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "true"},
        files={"file": ("same.wav", b"fake2", "audio/wav")},
    )
    assert response1.status_code == 200
    assert response2.status_code == 200
    path1 = response1.json()["model"]["result"]["file_path"]
    path2 = response2.json()["model"]["result"]["file_path"]
    assert path1 != path2


def test_upload_file_size_limit(tmp_path, monkeypatch):
    """Upload exceeding MAX_UPLOAD_SIZE should be rejected with 413."""
    import audioqas.web.api as api_module
    original_limit = api_module.MAX_UPLOAD_SIZE
    monkeypatch.setattr(api_module, "MAX_UPLOAD_SIZE", 100)  # 100 bytes
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))
    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "true"},
        files={"file": ("big.wav", b"x" * 200, "audio/wav")},
    )
    assert response.status_code == 413


def test_compare_upload_keys_files_mismatch():
    """Mismatched keys and files lengths should return 400."""
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))
    response = client.post(
        "/api/evaluate/compare-upload",
        data={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "base_key": "A",
            "include_signal": "false",
            "keys": ["A", "B", "C"],
        },
        files=[
            ("files", ("a.wav", b"a", "audio/wav")),
            ("files", ("b.wav", b"b", "audio/wav")),
        ],
    )
    assert response.status_code == 400


def test_upload_batch_writes_history():
    """upload-batch endpoint should write a history item."""
    from audioqas.web.history_store import InMemoryHistoryStore
    store = InMemoryHistoryStore()
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=store))
    response = client.post(
        "/api/evaluate/upload-batch",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "true"},
        files=[
            ("files", ("a.wav", b"a", "audio/wav")),
            ("files", ("b.wav", b"b", "audio/wav")),
        ],
    )
    assert response.status_code == 200
    items = store.list_items()
    assert len(items) == 1
    assert items[0]["scene"] == "batch"


def test_compare_upload_writes_history():
    """compare-upload endpoint should write a history item."""
    from audioqas.web.history_store import InMemoryHistoryStore
    store = InMemoryHistoryStore()
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=store))
    response = client.post(
        "/api/evaluate/compare-upload",
        data={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "base_key": "A",
            "include_signal": "false",
            "keys": ["A", "B"],
        },
        files=[
            ("files", ("a.wav", b"a", "audio/wav")),
            ("files", ("b.wav", b"b", "audio/wav")),
        ],
    )
    assert response.status_code == 200
    items = store.list_items()
    assert len(items) == 1
    assert items[0]["scene"] == "compare"
    assert items[0]["compare_mode"] == "base"


def test_upload_endpoint_logs_request_chain(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "true"},
        files={"file": ("same.wav", b"fake1", "audio/wav")},
    )

    assert response.status_code == 200
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "request_received" in text
    assert "upload_saved" in text
    assert "request_finished" in text


def test_upload_size_limit_logs_request_failed(tmp_path, monkeypatch):
    from audioqas.logging import setup_logging
    import audioqas.web.api as api_module

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    monkeypatch.setattr(api_module, "MAX_UPLOAD_SIZE", 100)
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "true"},
        files={"file": ("big.wav", b"x" * 200, "audio/wav")},
    )

    assert response.status_code == 413
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "request_failed" in text
    assert "file_too_large" in text


def test_compare_upload_mismatch_logs_request_failed(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))

    response = client.post(
        "/api/evaluate/compare-upload",
        data={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "base_key": "A",
            "include_signal": "false",
            "keys": ["A", "B", "C"],
        },
        files=[
            ("files", ("a.wav", b"a", "audio/wav")),
            ("files", ("b.wav", b"b", "audio/wav")),
        ],
    )

    assert response.status_code == 400
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "request_failed" in text
    assert "mismatched_keys_files" in text


def test_upload_preprocess_disabled_returns_400(tmp_path, monkeypatch):
    from audioqas.web.settings_store import InMemorySettingsStore
    import audioqas.models.nisqa as nisqa
    import numpy as np

    monkeypatch.setattr(nisqa.sf, "read", lambda path: (np.zeros((48000, 2)), 48000))
    settings_store = InMemorySettingsStore({"preprocess_to_mono": False})
    client = TestClient(create_app(settings_store=settings_store))

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "nisqa", "include_signal": "false"},
        files={"file": ("sample.wav", b"fake", "audio/wav")},
    )

    assert response.status_code == 400
    payload = response.json()["detail"]
    assert payload["code"] == "mono_convert_disabled"
    assert payload["stage"] == "preprocess"
    assert "disabled" in payload["message"]


def test_upload_video_without_ffmpeg_returns_400(tmp_path, monkeypatch):
    from audioqas.web.settings_store import InMemorySettingsStore
    import audioqas.core.preprocessor as preprocessor
    import shutil

    _with_real_preprocess_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "ffmpeg" else shutil.which(name))
    settings_store = InMemorySettingsStore({"preprocess_extract_audio": True})
    client = TestClient(create_app(settings_store=settings_store))

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "false"},
        files={"file": ("sample.mp4", b"fake-video", "video/mp4")},
    )

    assert response.status_code == 400
    payload = response.json()["detail"]
    assert payload["code"] == "ffmpeg_missing"
    assert payload["stage"] == "preprocess"
    assert "ffmpeg" in payload["message"].lower()


def test_upload_empty_file_returns_400(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "false"},
        files={"file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    payload = response.json()["detail"]
    assert payload["code"] == "empty_upload"
    assert payload["stage"] == "upload"


def test_upload_invalid_audio_returns_400(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "false"},
        files={"file": ("broken.wav", b"not-a-real-wave-file", "audio/wav")},
    )

    assert response.status_code == 400
    payload = response.json()["detail"]
    assert payload["code"] == "invalid_audio_file"
    assert payload["stage"] == "preprocess"


def test_upload_header_only_wav_returns_400(tmp_path, monkeypatch):
    _with_real_preprocess_dir(tmp_path, monkeypatch)
    client = TestClient(create_app())
    header_only_wav = (
        b"RIFF"
        + (36).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (2).to_bytes(2, "little")
        + (48000).to_bytes(4, "little")
        + (48000 * 2 * 2).to_bytes(4, "little")
        + (4).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + (0).to_bytes(4, "little")
    )

    response = client.post(
        "/api/evaluate/upload",
        data={"domain": EvalDomain.SPEECH.value, "model_key": "dnsmos", "include_signal": "false"},
        files={"file": ("header_only.wav", header_only_wav, "audio/wav")},
    )

    assert response.status_code == 400
    payload = response.json()["detail"]
    assert payload["code"] == "empty_audio"
    assert payload["stage"] == "preprocess"


def test_supplied_request_id_is_used_in_logs(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    client = TestClient(create_app(evaluation_service=FakeEvaluationService(), history_store=FakeHistoryStore()))

    response = client.post(
        "/api/evaluate/single",
        json={
            "domain": EvalDomain.SPEECH.value,
            "model_key": "dnsmos",
            "file_path": "sample.wav",
            "include_signal": True,
        },
        headers={"X-Request-Id": "req_ui_test_001"},
    )

    assert response.status_code == 200
    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "[req_ui_test_001]" in text


def test_build_history_item_unknown_dimension():
    """_build_history_item_for_single should fallback to first dimension when no OVRL/PQ."""
    from audioqas.web.api import _build_history_item_for_single
    result = SingleTaskResult(
        domain=EvalDomain.SPEECH,
        file_path="test.wav",
        model=ModelExecutionResult(
            model_key="future",
            domain=EvalDomain.SPEECH,
            result={
                "eval_type": "mos",
                "model_name": "FutureModel",
                "model_version": "1",
                "dimensions": {"CE": {"score": 7.0, "grade": "Good", "description": "content"}},
                "grade": "Good",
                "descriptions": {},
                "timestamp": "2026-05-19T00:00",
                "file_path": "test.wav",
                "original_sr": 48000,
                "original_channels": 1,
                "duration": 10.0,
                "preprocessed": False,
                "preprocessed_path": "test.wav",
            },
        ),
        signal=None,
    )
    item = _build_history_item_for_single(result)
    assert item["summary_metrics"] == ["CE 7.0"]
    assert item["model_label"] == "FutureModel"


def test_history_items_respect_retention_window():
    from audioqas.web.history_store import InMemoryHistoryStore
    from audioqas.web.settings_store import InMemorySettingsStore

    history_store = InMemoryHistoryStore([
        {
            "id": "old-task",
            "timestamp": "2026-01-01 10:00",
            "page_key": "eval",
            "page_title": "纯人声评测",
            "scene": "single",
            "model_label": "DNSMOS",
            "file_summary": "old.wav",
            "summary_metrics": ["OVRL 3.0"],
            "trace_summary": "old",
        },
        {
            "id": "new-task",
            "timestamp": "2026-05-20 10:00",
            "page_key": "eval",
            "page_title": "纯人声评测",
            "scene": "single",
            "model_label": "DNSMOS",
            "file_summary": "new.wav",
            "summary_metrics": ["OVRL 4.0"],
            "trace_summary": "new",
        },
    ])
    settings_store = InMemorySettingsStore({"history_retention_days": 30})
    client = TestClient(create_app(history_store=history_store, settings_store=settings_store))

    response = client.get("/api/history")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == ["new-task"]
