from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from audioqas.web.api import create_app
from audioqas.web.history_store import InMemoryHistoryStore


ROOT = Path(__file__).resolve().parents[2]
FILES_DIR = ROOT / "tests" / "files"


def _client() -> TestClient:
    preprocess_dir = Path(tempfile.mkdtemp(prefix="audioqas-real-preprocess-"))
    state_dir = Path(tempfile.mkdtemp(prefix="audioqas-real-state-"))
    os.environ["AUDIOQAS_PREPROCESS_DIR"] = str(preprocess_dir)
    os.environ["AUDIOQAS_WEB_STATE_DIR"] = str(state_dir)
    return TestClient(create_app())


def _client_with_history() -> tuple[TestClient, InMemoryHistoryStore]:
    preprocess_dir = Path(tempfile.mkdtemp(prefix="audioqas-real-preprocess-"))
    state_dir = Path(tempfile.mkdtemp(prefix="audioqas-real-state-"))
    os.environ["AUDIOQAS_PREPROCESS_DIR"] = str(preprocess_dir)
    os.environ["AUDIOQAS_WEB_STATE_DIR"] = str(state_dir)
    store = InMemoryHistoryStore()
    return TestClient(create_app(history_store=store)), store


def _single_payload(domain: str, model_key: str, file_name: str) -> dict:
    client = _client()
    file_path = FILES_DIR / file_name
    with file_path.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": domain,
                "model_key": model_key,
                "include_signal": "true",
            },
            files={"file": (file_path.name, handle, "audio/wav")},
        )
    response.raise_for_status()
    return response.json()


def _compare_payload(domain: str, model_key: str, file_a: str, file_b: str) -> dict:
    client = _client()
    path_a = FILES_DIR / file_a
    path_b = FILES_DIR / file_b
    with path_a.open("rb") as handle_a, path_b.open("rb") as handle_b:
        response = client.post(
            "/api/evaluate/compare-upload",
            data={
                "domain": domain,
                "model_key": model_key,
                "base_key": "A",
                "include_signal": "true",
                "keys": ["A", "B"],
            },
            files=[
                ("files", (path_a.name, handle_a, "audio/wav")),
                ("files", (path_b.name, handle_b, "audio/wav")),
            ],
        )
    response.raise_for_status()
    return response.json()


def _history_after_single(domain: str, model_key: str, file_name: str) -> list[dict]:
    client, _store = _client_with_history()
    file_path = FILES_DIR / file_name
    with file_path.open("rb") as handle:
        response = client.post(
            "/api/evaluate/upload",
            data={
                "domain": domain,
                "model_key": model_key,
                "include_signal": "true",
            },
            files={"file": (file_path.name, handle, "audio/wav")},
        )
    response.raise_for_status()
    history = client.get("/api/history")
    history.raise_for_status()
    return history.json()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: web_real_backend_payload.py single|compare ...")

    mode = argv[1]
    if mode == "single":
        if len(argv) != 5:
            raise SystemExit("usage: web_real_backend_payload.py single <domain> <model_key> <file_name>")
        payload = _single_payload(argv[2], argv[3], argv[4])
    elif mode == "compare":
        if len(argv) != 6:
            raise SystemExit("usage: web_real_backend_payload.py compare <domain> <model_key> <file_a> <file_b>")
        payload = _compare_payload(argv[2], argv[3], argv[4], argv[5])
    elif mode == "history-single":
        if len(argv) != 5:
            raise SystemExit("usage: web_real_backend_payload.py history-single <domain> <model_key> <file_name>")
        payload = _history_after_single(argv[2], argv[3], argv[4])
    elif mode == "single-error":
        if len(argv) != 5:
            raise SystemExit("usage: web_real_backend_payload.py single-error <domain> <model_key> <file_name>")
        file_path = FILES_DIR / argv[4]
        client = _client()
        try:
            with file_path.open("rb") as handle:
                response = client.post(
                    "/api/evaluate/upload",
                    data={
                        "domain": argv[2],
                        "model_key": argv[3],
                        "include_signal": "true",
                    },
                    files={"file": (file_path.name, handle, "audio/wav")},
                )
            print(json.dumps({"status": response.status_code, "body": response.text}, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"status": 500, "body": str(exc)}, ensure_ascii=False))
        return 0
    else:
        raise SystemExit(f"unknown mode: {mode}")

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
