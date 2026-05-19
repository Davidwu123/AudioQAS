from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from audioqas.web.runtime import CompareInputGroup
from audioqas.web.history_store import default_history_store
from audioqas.web.settings_store import default_settings_store
from audioqas.web.services import WebPreviewService
from audioqas.web.schemas import EvalDomain
from audioqas.web.tasks import EvaluationService


class SingleEvaluateRequest(BaseModel):
    domain: EvalDomain
    model_key: str
    file_path: str
    include_signal: bool = True


class BatchEvaluateRequest(BaseModel):
    domain: EvalDomain
    model_key: str
    file_paths: list[str]
    include_signal: bool = True


class CompareGroupInput(BaseModel):
    key: str
    file_path: str


class CompareEvaluateRequest(BaseModel):
    domain: EvalDomain
    model_key: str
    groups: list[CompareGroupInput]
    base_key: str | None = None
    include_signal: bool = True


class SettingsUpdateRequest(BaseModel):
    default_eval_model: str | None = None
    default_analysis_model: str | None = None
    trace: bool | None = None
    compare_default: str | None = None


def _serialize_single_result(result) -> dict:
    return {
        "domain": result.domain.value,
        "file_path": result.file_path,
        "model": {
            "model_key": result.model.model_key,
            "domain": result.model.domain.value,
            "result": result.model.result,
        },
        "signal": result.signal.result if result.signal else None,
    }


def _serialize_batch_result(result) -> dict:
    return {
        "domain": result.domain.value,
        "model_key": result.model_key,
        "items": [_serialize_single_result(item) for item in result.items],
    }


def _serialize_compare_result(result) -> dict:
    return {
        "domain": result.domain.value,
        "model_key": result.model_key,
        "base_key": result.base_key,
        "items": [
            {
                "key": item.key,
                "file_path": item.file_path,
                "rank": item.rank,
                "delta_from_base": item.delta_from_base,
                "task": _serialize_single_result(item.task),
            }
            for item in result.items
        ],
    }


def _page_meta_for_domain(domain: EvalDomain) -> tuple[str, str]:
    if domain == EvalDomain.SPEECH:
        return "eval", "纯人声评测"
    return "analysis", "综合音频分析"


def _build_history_item_for_single(result) -> dict:
    page_key, page_title = _page_meta_for_domain(result.domain)
    model_result = result.model.result
    dimensions = model_result["dimensions"]
    primary_score = dimensions["OVRL"]["score"] if "OVRL" in dimensions else dimensions["PQ"]["score"]
    primary_label = "OVRL" if "OVRL" in dimensions else "PQ"
    signal_metrics = result.signal.result["metrics"] if result.signal else {}
    summary_metrics = [f"{primary_label} {primary_score:.1f}"]
    if "LUFS" in signal_metrics:
        summary_metrics.append(f"LUFS {signal_metrics['LUFS']['value']:.1f}")
    trace_summary = model_result["preprocessed_path"] or model_result["file_path"]
    return {
        "id": str(uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "page_key": page_key,
        "page_title": page_title,
        "scene": "single",
        "model_label": model_result["model_name"].replace("AudioBox-Aesthetics", "AudioBox Aesthetics"),
        "file_summary": Path(result.file_path).name,
        "summary_metrics": summary_metrics,
        "trace_summary": trace_summary,
        "detail": _serialize_single_result(result),
    }


def create_app(
    service: WebPreviewService | None = None,
    evaluation_service: EvaluationService | None = None,
    history_store=None,
    settings_store=None,
) -> FastAPI:
    app = FastAPI(title="AudioQAS Web API", version="0.1.0")
    history_store = history_store or default_history_store()
    settings_store = settings_store or default_settings_store()
    preview_service = service or WebPreviewService(history_store=history_store, settings_store=settings_store)
    task_service = evaluation_service or EvaluationService()
    design_dir = Path(__file__).resolve().parents[2] / "design"
    upload_dir = Path(__file__).resolve().parents[2] / ".tmp" / "web_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    app.mount("/design", StaticFiles(directory=design_dir), name="design")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(design_dir / "web-preview.html")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/bootstrap")
    def bootstrap() -> dict:
        return preview_service.bootstrap_payload()

    @app.get("/api/navigation")
    def navigation() -> list[dict]:
        return preview_service.navigation()

    @app.get("/api/models")
    def models() -> dict[str, dict]:
        return preview_service.model_catalog()

    @app.get("/api/signal-metrics")
    def signal_metrics() -> list[dict]:
        return preview_service.signal_catalog()

    @app.get("/api/history")
    def history_items() -> list[dict]:
        return preview_service.history_items()

    @app.get("/api/history/{item_id}")
    def history_detail(item_id: str) -> dict:
        item = preview_service.history_detail(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="history item not found")
        return item

    @app.get("/api/settings")
    def settings() -> dict:
        return preview_service.settings()

    @app.post("/api/settings")
    def update_settings(payload: SettingsUpdateRequest) -> dict:
        return preview_service.update_settings(payload.model_dump(exclude_unset=True))

    @app.post("/api/evaluate/single")
    def evaluate_single(payload: SingleEvaluateRequest) -> dict:
        result = task_service.evaluate_single(
            domain=payload.domain,
            model_key=payload.model_key,
            file_path=payload.file_path,
            include_signal=payload.include_signal,
        )
        return _serialize_single_result(result)

    @app.post("/api/evaluate/batch")
    def evaluate_batch(payload: BatchEvaluateRequest) -> dict:
        result = task_service.evaluate_batch(
            domain=payload.domain,
            model_key=payload.model_key,
            file_paths=payload.file_paths,
            include_signal=payload.include_signal,
        )
        return _serialize_batch_result(result)

    @app.post("/api/evaluate/compare")
    def evaluate_compare(payload: CompareEvaluateRequest) -> dict:
        result = task_service.evaluate_compare(
            domain=payload.domain,
            model_key=payload.model_key,
            groups=[CompareInputGroup(key=group.key, file_path=group.file_path) for group in payload.groups],
            base_key=payload.base_key,
            include_signal=payload.include_signal,
        )
        return _serialize_compare_result(result)

    @app.post("/api/evaluate/upload")
    async def evaluate_upload(
        domain: EvalDomain = Form(...),
        model_key: str = Form(...),
        include_signal: bool = Form(True),
        file: UploadFile = File(...),
    ) -> dict:
        filename = Path(file.filename or "upload.bin").name
        target = upload_dir / filename
        content = await file.read()
        target.write_bytes(content)
        result = task_service.evaluate_single(
            domain=domain,
            model_key=model_key,
            file_path=str(target),
            include_signal=include_signal,
        )
        if history_store and hasattr(history_store, "add_item"):
            history_store.add_item(_build_history_item_for_single(result))
        return _serialize_single_result(result)

    @app.post("/api/evaluate/upload-batch")
    async def evaluate_upload_batch(
        domain: EvalDomain = Form(...),
        model_key: str = Form(...),
        include_signal: bool = Form(True),
        files: list[UploadFile] = File(...),
    ) -> dict:
        stored_paths: list[str] = []
        for upload in files:
            filename = Path(upload.filename or "upload.bin").name
            target = upload_dir / filename
            target.write_bytes(await upload.read())
            stored_paths.append(str(target))
        result = task_service.evaluate_batch(
            domain=domain,
            model_key=model_key,
            file_paths=stored_paths,
            include_signal=include_signal,
        )
        return _serialize_batch_result(result)

    @app.post("/api/evaluate/compare-upload")
    async def evaluate_compare_upload(
        domain: EvalDomain = Form(...),
        model_key: str = Form(...),
        base_key: str | None = Form(None),
        include_signal: bool = Form(True),
        keys: list[str] = Form(...),
        files: list[UploadFile] = File(...),
    ) -> dict:
        groups: list[CompareInputGroup] = []
        for key, upload in zip(keys, files, strict=False):
            filename = Path(upload.filename or "upload.bin").name
            target = upload_dir / filename
            target.write_bytes(await upload.read())
            groups.append(CompareInputGroup(key=key, file_path=str(target)))
        result = task_service.evaluate_compare(
            domain=domain,
            model_key=model_key,
            groups=groups,
            base_key=base_key,
            include_signal=include_signal,
        )
        return _serialize_compare_result(result)

    return app


app = create_app()
