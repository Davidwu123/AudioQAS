from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile
from fastapi import HTTPException
from fastapi import Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from audioqas.logging import get_logger, log_context, set_event
from audioqas.web.runtime import CompareInputGroup
from audioqas.web.history_store import default_history_store
from audioqas.web.settings_store import default_settings_store
from audioqas.web.services import WebPreviewService
from audioqas.web.schemas import EvalDomain
from audioqas.web.tasks import EvaluationService

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
logger = get_logger(__name__)


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
    preprocess_resample: bool | None = None
    preprocess_to_mono: bool | None = None
    preprocess_extract_audio: bool | None = None
    export_format: str | None = None
    history_retention_days: int | None = None


PREPROCESS_ERROR_MESSAGES = {
    "mono_convert_disabled": "Automatic mono conversion is disabled for the current settings.",
    "resample_disabled": "Automatic resampling is disabled for the current settings.",
    "video_extract_disabled": "Automatic audio extraction from video is disabled for the current settings.",
}


def _new_request_id(scene: str, supplied: str | None = None) -> str:
    return supplied or f"req_{scene}_{uuid4().hex[:8]}"


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
    if "OVRL" in dimensions:
        primary_score, primary_label = dimensions["OVRL"]["score"], "OVRL"
    elif "PQ" in dimensions:
        primary_score, primary_label = dimensions["PQ"]["score"], "PQ"
    else:
        first_dim = next(iter(dimensions))
        primary_score, primary_label = dimensions[first_dim]["score"], first_dim
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
        "model_label": model_result["model_name"],
        "file_summary": Path(result.file_path).name,
        "summary_metrics": summary_metrics,
        "trace_summary": trace_summary,
        "detail": _serialize_single_result(result),
    }


def _build_history_item_for_batch(result) -> dict:
    page_key, page_title = _page_meta_for_domain(result.domain)
    file_names = [Path(item.file_path).name for item in result.items]
    return {
        "id": str(uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "page_key": page_key,
        "page_title": page_title,
        "scene": "batch",
        "model_label": result.model_key,
        "file_summary": f"{len(result.items)} files",
        "summary_metrics": [f"batch {len(result.items)} files"],
        "trace_summary": file_names[0] if file_names else "",
        "detail": _serialize_batch_result(result),
    }


def _build_history_item_for_compare(result) -> dict:
    page_key, page_title = _page_meta_for_domain(result.domain)
    group_labels = [f"{item.key}: {Path(item.file_path).name}" for item in result.items]
    primary_item = result.items[0]
    dimensions = primary_item.task.model.result["dimensions"]
    first_dim = next(iter(dimensions))
    primary_score = dimensions[first_dim]["score"]
    compare_mode = "base" if result.base_key else "free"
    return {
        "id": str(uuid4()),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "page_key": page_key,
        "page_title": page_title,
        "scene": "compare",
        "compare_mode": compare_mode,
        "model_label": result.model_key,
        "file_summary": f"{len(result.items)} groups",
        "summary_metrics": [f"{first_dim} {primary_score:.1f}"],
        "trace_summary": "; ".join(group_labels),
        "detail": _serialize_compare_result(result),
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

    def _configure_task_service() -> None:
        if hasattr(task_service, "configure_settings"):
            task_service.configure_settings(preview_service.settings())

    def _raise_preprocess_http_error(exc: ValueError) -> None:
        reason = str(exc)
        detail = PREPROCESS_ERROR_MESSAGES.get(reason)
        if detail is None:
            raise exc
        with set_event("request_failed"):
            logger.warning("request_failed reason=%s", reason)
        raise HTTPException(
            status_code=400,
            detail={
                "code": reason,
                "message": detail,
                "stage": "preprocess",
            },
        )

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(design_dir / "web-preview.html")

    @app.get("/api/health")
    def health(x_request_id: str | None = Header(None)) -> dict:
        with log_context(request_id=_new_request_id("health", x_request_id), scene="health"):
            with set_event("request_received"):
                logger.info("request_received path=/api/health")
            result = {"ok": True}
            with set_event("request_finished"):
                logger.info("request_finished path=/api/health status=200")
            return result

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
    def settings(x_request_id: str | None = Header(None)) -> dict:
        with log_context(request_id=_new_request_id("settings_get", x_request_id), scene="settings"):
            with set_event("request_received"):
                logger.info("request_received path=/api/settings method=GET")
            result = preview_service.settings()
            with set_event("request_finished"):
                logger.info("request_finished path=/api/settings status=200")
            return result

    @app.post("/api/settings")
    def update_settings(payload: SettingsUpdateRequest, x_request_id: str | None = Header(None)) -> dict:
        with log_context(request_id=_new_request_id("settings_post", x_request_id), scene="settings"):
            with set_event("request_received"):
                logger.info("request_received path=/api/settings method=POST keys=%s", sorted(payload.model_dump(exclude_unset=True).keys()))
            result = preview_service.update_settings(payload.model_dump(exclude_unset=True))
            with set_event("request_finished"):
                logger.info("request_finished path=/api/settings status=200")
            return result

    @app.post("/api/evaluate/single")
    def evaluate_single(payload: SingleEvaluateRequest, x_request_id: str | None = Header(None)) -> dict:
        with log_context(request_id=_new_request_id("single", x_request_id), scene="single"):
            _configure_task_service()
            with set_event("request_received"):
                logger.info(
                    "request_received path=/api/evaluate/single domain=%s model=%s file=%s include_signal=%s",
                    payload.domain.value,
                    payload.model_key,
                    payload.file_path,
                    payload.include_signal,
                )
            result = task_service.evaluate_single(
                domain=payload.domain,
                model_key=payload.model_key,
                file_path=payload.file_path,
                include_signal=payload.include_signal,
            )
            with set_event("request_finished"):
                logger.info("request_finished path=/api/evaluate/single status=200")
            return _serialize_single_result(result)

    @app.post("/api/evaluate/batch")
    def evaluate_batch(payload: BatchEvaluateRequest, x_request_id: str | None = Header(None)) -> dict:
        with log_context(request_id=_new_request_id("batch", x_request_id), scene="batch"):
            _configure_task_service()
            with set_event("request_received"):
                logger.info(
                    "request_received path=/api/evaluate/batch domain=%s model=%s files=%s include_signal=%s",
                    payload.domain.value,
                    payload.model_key,
                    len(payload.file_paths),
                    payload.include_signal,
                )
            result = task_service.evaluate_batch(
                domain=payload.domain,
                model_key=payload.model_key,
                file_paths=payload.file_paths,
                include_signal=payload.include_signal,
            )
            with set_event("request_finished"):
                logger.info("request_finished path=/api/evaluate/batch status=200")
            return _serialize_batch_result(result)

    @app.post("/api/evaluate/compare")
    def evaluate_compare(payload: CompareEvaluateRequest, x_request_id: str | None = Header(None)) -> dict:
        with log_context(request_id=_new_request_id("compare", x_request_id), scene="compare"):
            _configure_task_service()
            with set_event("request_received"):
                logger.info(
                    "request_received path=/api/evaluate/compare domain=%s model=%s groups=%s include_signal=%s base_key=%s",
                    payload.domain.value,
                    payload.model_key,
                    len(payload.groups),
                    payload.include_signal,
                    payload.base_key,
                )
            result = task_service.evaluate_compare(
                domain=payload.domain,
                model_key=payload.model_key,
                groups=[CompareInputGroup(key=group.key, file_path=group.file_path) for group in payload.groups],
                base_key=payload.base_key,
                include_signal=payload.include_signal,
            )
            with set_event("request_finished"):
                logger.info("request_finished path=/api/evaluate/compare status=200")
            return _serialize_compare_result(result)

    @app.post("/api/evaluate/upload")
    async def evaluate_upload(
        domain: EvalDomain = Form(...),
        model_key: str = Form(...),
        include_signal: bool = Form(True),
        file: UploadFile = File(...),
        x_request_id: str | None = Header(None),
    ) -> dict:
        with log_context(request_id=_new_request_id("upload_single", x_request_id), scene="single"):
            try:
                _configure_task_service()
                with set_event("request_received"):
                    logger.info(
                        "request_received path=/api/evaluate/upload domain=%s model=%s include_signal=%s filename=%s",
                        domain.value,
                        model_key,
                        include_signal,
                        file.filename,
                    )
                filename = f"{uuid4().hex[:8]}_{Path(file.filename or 'upload.bin').name}"
                target = upload_dir / filename
                content = await file.read()
                logger.debug("upload_read_complete filename=%s size=%s", file.filename, len(content))
                if len(content) > MAX_UPLOAD_SIZE:
                    with set_event("request_failed"):
                        logger.warning(
                            "request_failed reason=file_too_large size=%s limit=%s filename=%s",
                            len(content),
                            MAX_UPLOAD_SIZE,
                            file.filename,
                        )
                    raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_SIZE // (1024*1024)}MB)")
                target.write_bytes(content)
                with set_event("upload_saved"):
                    logger.info("upload_saved file=%s size=%s", target, len(content))
                result = task_service.evaluate_single(
                    domain=domain,
                    model_key=model_key,
                    file_path=str(target),
                    include_signal=include_signal,
                )
                if history_store and hasattr(history_store, "add_item"):
                    history_store.add_item(_build_history_item_for_single(result))
                with set_event("request_finished"):
                    logger.info("request_finished path=/api/evaluate/upload status=200")
                return _serialize_single_result(result)
            except HTTPException:
                raise
            except ValueError as exc:
                _raise_preprocess_http_error(exc)
            except Exception:
                with set_event("request_failed"):
                    logger.exception("request_failed path=/api/evaluate/upload reason=unexpected_error")
                raise

    @app.post("/api/evaluate/upload-batch")
    async def evaluate_upload_batch(
        domain: EvalDomain = Form(...),
        model_key: str = Form(...),
        include_signal: bool = Form(True),
        files: list[UploadFile] = File(...),
        x_request_id: str | None = Header(None),
    ) -> dict:
        with log_context(request_id=_new_request_id("upload_batch", x_request_id), scene="batch"):
            try:
                _configure_task_service()
                with set_event("request_received"):
                    logger.info(
                        "request_received path=/api/evaluate/upload-batch domain=%s model=%s files=%s include_signal=%s",
                        domain.value,
                        model_key,
                        len(files),
                        include_signal,
                    )
                stored_paths: list[str] = []
                for upload in files:
                    filename = f"{uuid4().hex[:8]}_{Path(upload.filename or 'upload.bin').name}"
                    target = upload_dir / filename
                    content = await upload.read()
                    if len(content) > MAX_UPLOAD_SIZE:
                        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_SIZE // (1024*1024)}MB)")
                    target.write_bytes(content)
                    stored_paths.append(str(target))
                    with set_event("upload_saved"):
                        logger.info("upload_saved file=%s size=%s", target, len(content))
                result = task_service.evaluate_batch(
                    domain=domain,
                    model_key=model_key,
                    file_paths=stored_paths,
                    include_signal=include_signal,
                )
                if history_store and hasattr(history_store, "add_item"):
                    history_store.add_item(_build_history_item_for_batch(result))
                with set_event("request_finished"):
                    logger.info("request_finished path=/api/evaluate/upload-batch status=200")
                return _serialize_batch_result(result)
            except HTTPException:
                raise
            except ValueError as exc:
                _raise_preprocess_http_error(exc)
            except Exception:
                with set_event("request_failed"):
                    logger.exception("request_failed path=/api/evaluate/upload-batch reason=unexpected_error")
                raise

    @app.post("/api/evaluate/compare-upload")
    async def evaluate_compare_upload(
        domain: EvalDomain = Form(...),
        model_key: str = Form(...),
        base_key: str | None = Form(None),
        include_signal: bool = Form(True),
        keys: list[str] = Form(...),
        files: list[UploadFile] = File(...),
        x_request_id: str | None = Header(None),
    ) -> dict:
        with log_context(request_id=_new_request_id("upload_compare", x_request_id), scene="compare"):
            try:
                _configure_task_service()
                with set_event("request_received"):
                    logger.info(
                        "request_received path=/api/evaluate/compare-upload domain=%s model=%s files=%s include_signal=%s base_key=%s",
                        domain.value,
                        model_key,
                        len(files),
                        include_signal,
                        base_key,
                    )
                if len(keys) != len(files):
                    with set_event("request_failed"):
                        logger.warning(
                            "request_failed reason=mismatched_keys_files keys=%s files=%s",
                            len(keys),
                            len(files),
                        )
                    raise HTTPException(status_code=400, detail=f"Mismatched keys ({len(keys)}) and files ({len(files)})")
                groups: list[CompareInputGroup] = []
                for key, upload in zip(keys, files, strict=False):
                    filename = f"{uuid4().hex[:8]}_{Path(upload.filename or 'upload.bin').name}"
                    target = upload_dir / filename
                    content = await upload.read()
                    if len(content) > MAX_UPLOAD_SIZE:
                        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_SIZE // (1024*1024)}MB)")
                    target.write_bytes(content)
                    groups.append(CompareInputGroup(key=key, file_path=str(target)))
                    with set_event("upload_saved"):
                        logger.info("upload_saved group=%s file=%s size=%s", key, target, len(content))
                result = task_service.evaluate_compare(
                    domain=domain,
                    model_key=model_key,
                    groups=groups,
                    base_key=base_key,
                    include_signal=include_signal,
                )
                if history_store and hasattr(history_store, "add_item"):
                    history_store.add_item(_build_history_item_for_compare(result))
                with set_event("request_finished"):
                    logger.info("request_finished path=/api/evaluate/compare-upload status=200")
                return _serialize_compare_result(result)
            except HTTPException:
                raise
            except ValueError as exc:
                _raise_preprocess_http_error(exc)
            except Exception:
                with set_event("request_failed"):
                    logger.exception("request_failed path=/api/evaluate/compare-upload reason=unexpected_error")
                raise

    return app


app = create_app()
