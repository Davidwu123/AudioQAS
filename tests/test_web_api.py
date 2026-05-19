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


ROOT = Path(__file__).resolve().parents[1]
REAL_FILE_1 = ROOT / "tests" / "files" / "test1.wav"
REAL_FILE_2 = ROOT / "tests" / "files" / "test2.wav"


def _with_real_preprocess_dir(tmp_path, monkeypatch) -> None:
    target = tmp_path / "preprocessed"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AUDIOQAS_PREPROCESS_DIR", str(target))


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


def test_root_serves_web_preview_html():
    client = make_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AudioQAS" in response.text


def test_design_static_assets_are_mounted():
    client = make_client()
    response = client.get("/design/web-preview-data.js")
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
    assert "SNR" in keys
    assert "Stereo" in keys


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

    response = client.post(
        "/api/settings",
        json={
            "default_eval_model": "nisqa",
            "trace": False,
            "compare_default": "base",
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["default_eval_model"] == "nisqa"
    assert updated["trace"] is False
    assert updated["compare_default"] == "base"

    response = client.get("/api/settings")
    assert response.status_code == 200
    persisted = response.json()
    assert persisted["default_eval_model"] == "nisqa"
    assert persisted["trace"] is False
    assert persisted["compare_default"] == "base"


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

    response = client.post(
        "/api/settings",
        json={"compare_default": "base", "trace": False},
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
    assert len(history.json()) == 1
