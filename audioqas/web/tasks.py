from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any
from uuid import uuid4

from audioqas.logging import get_logger, get_request_id, log_context, set_event
from audioqas.core.preprocessor import configure_preprocessor
from audioqas.models.analysis import AudioAnalyzer
from audioqas.models.audiobox_aesthetics import AudioBoxAestheticsScorer
from audioqas.models.base import ScoreResult
from audioqas.models.dnsmos import DNSMOSScorer
from audioqas.models.nisqa import NISQAScorer
from audioqas.web.runtime import (
    BatchTaskResult,
    CompareGroupResult,
    CompareInputGroup,
    CompareTaskResult,
    ModelExecutionResult,
    ModelRunner,
    SignalExecutionResult,
    SignalRunner,
    SingleTaskResult,
)
from audioqas.web.schemas import EvalDomain

logger = get_logger(__name__)
ProgressCallback = Callable[[dict[str, Any]], None]
DEFAULT_COMPARE_WORKERS = 4
MAX_COMPARE_WORKERS = 4
COMPARE_PROGRESS_BASE = 20
COMPARE_PROGRESS_SPAN = 75


def _emit_progress(callback: ProgressCallback | None, **event: Any) -> None:
    if callback:
        callback(event)


@dataclass
class TaskRunners:
    speech_models: dict[str, ModelRunner]
    mixed_models: dict[str, ModelRunner]
    signal_runner: SignalRunner


def default_task_runners() -> TaskRunners:
    return TaskRunners(
        speech_models={
            "dnsmos": DNSMOSScorer(),
            "nisqa": NISQAScorer(),
        },
        mixed_models={
            "audiobox": AudioBoxAestheticsScorer(),
        },
        signal_runner=AudioAnalyzer(),
    )


class EvaluationService:
    def __init__(self, runners: TaskRunners | None = None, compare_workers: int = DEFAULT_COMPARE_WORKERS) -> None:
        self._runners = runners or default_task_runners()
        self._owns_default_runners = runners is None
        self._compare_workers = max(1, min(MAX_COMPARE_WORKERS, int(compare_workers)))
        self._preprocess_settings = {
            "resample": True,
            "to_mono": True,
            "extract_audio": True,
        }

    def configure_settings(self, settings: dict | None) -> None:
        if not settings:
            return
        self._preprocess_settings = {
            "resample": settings.get("preprocess_resample", True),
            "to_mono": settings.get("preprocess_to_mono", True),
            "extract_audio": settings.get("preprocess_extract_audio", True),
        }

    @staticmethod
    def _request_id() -> str | None:
        current = get_request_id()
        if current and current != "-":
            return current
        return f"req_task_{uuid4().hex[:8]}"

    def _model_runner(self, domain: EvalDomain, model_key: str) -> ModelRunner:
        catalog = self._runners.speech_models if domain == EvalDomain.SPEECH else self._runners.mixed_models
        if model_key not in catalog:
            raise KeyError(f"Unknown model '{model_key}' for domain '{domain.value}'")
        return catalog[model_key]

    def _worker_service(self) -> "EvaluationService":
        service = EvaluationService(
            None if self._owns_default_runners else self._runners,
            compare_workers=1,
        )
        service._preprocess_settings = dict(self._preprocess_settings)
        return service

    @staticmethod
    def _primary_dimension_score(result: ScoreResult) -> float:
        dimensions = result["dimensions"]
        if "OVRL" in dimensions:
            return dimensions["OVRL"]["score"]
        if "PQ" in dimensions:
            return dimensions["PQ"]["score"]
        return next(iter(dimensions.values()))["score"]

    def evaluate_single(
        self,
        *,
        domain: EvalDomain,
        model_key: str,
        file_path: str,
        include_signal: bool = True,
        progress_callback: ProgressCallback | None = None,
        progress_prefix: str | None = None,
        progress_base: int = 0,
        progress_span: int = 100,
    ) -> SingleTaskResult:
        with log_context(request_id=self._request_id()):
            configure_preprocessor(
                resample=self._preprocess_settings["resample"],
                to_mono=self._preprocess_settings["to_mono"],
                extract_audio=self._preprocess_settings["extract_audio"],
            )
            with set_event("task_started"):
                logger.info(
                    "task_started model=%s file=%s include_signal=%s",
                    model_key,
                    file_path,
                    include_signal,
                )
            model_runner = self._model_runner(domain, model_key)
            prefix = f"{progress_prefix} " if progress_prefix else ""
            signal_steps = 3 if include_signal else 2

            def percent(step_index: int) -> int:
                return min(100, round(progress_base + (progress_span * step_index / signal_steps)))

            _emit_progress(
                progress_callback,
                stage="preprocess_started",
                percent=percent(0),
                label=f"{prefix}预处理中",
            )
            _emit_progress(
                progress_callback,
                stage="model_started",
                percent=percent(0),
                label=f"{prefix}模型评测中",
            )
            model_result = model_runner.score(file_path)
            _emit_progress(
                progress_callback,
                stage="model_finished",
                percent=percent(1),
                label=f"{prefix}模型评测完成",
            )
            with set_event("model_result_ready"):
                logger.debug(
                    "model_result_ready model=%s grade=%s dimensions=%s",
                    model_key,
                    model_result["grade"],
                    sorted(model_result["dimensions"].keys()),
                )
            if include_signal:
                _emit_progress(
                    progress_callback,
                    stage="signal_started",
                    percent=percent(1),
                    label=f"{prefix}信号分析中",
                )
            signal_result = self._runners.signal_runner.analyze(file_path) if include_signal else None
            if signal_result is not None:
                _emit_progress(
                    progress_callback,
                    stage="signal_finished",
                    percent=percent(2),
                    label=f"{prefix}信号分析完成",
                )
                with set_event("signal_result_ready"):
                    logger.debug(
                        "signal_result_ready grade=%s metrics=%s",
                        signal_result["grade"],
                        sorted(signal_result["metrics"].keys()),
                    )
            result = SingleTaskResult(
                domain=domain,
                file_path=file_path,
                model=ModelExecutionResult(model_key=model_key, domain=domain, result=model_result),
                signal=SignalExecutionResult(signal_result) if signal_result else None,
            )
            with set_event("task_finished"):
                logger.info("task_finished model=%s file=%s", model_key, file_path)
            _emit_progress(
                progress_callback,
                stage="finished",
                percent=percent(signal_steps),
                label=f"{prefix}处理完成",
            )
            return result

    def evaluate_batch(
        self,
        *,
        domain: EvalDomain,
        model_key: str,
        file_paths: list[str],
        include_signal: bool = True,
    ) -> BatchTaskResult:
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

    def evaluate_compare(
        self,
        *,
        domain: EvalDomain,
        model_key: str,
        groups: list[CompareInputGroup],
        base_key: str | None = None,
        include_signal: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> CompareTaskResult:
        total_groups = len(groups)
        if total_groups == 0:
            single_results = []
        else:
            aggregator = _CompareProgressAggregator(
                groups=[group.key for group in groups],
                callback=progress_callback,
                base=COMPARE_PROGRESS_BASE,
                span=COMPARE_PROGRESS_SPAN,
            )
            workers = min(self._compare_workers, total_groups, MAX_COMPARE_WORKERS)
            indexed_results: list[tuple[CompareInputGroup, SingleTaskResult] | None] = [None] * total_groups
            with set_event("compare_parallel_started"):
                logger.info(
                    "compare_parallel_started model=%s groups=%s workers=%s max_workers=%s",
                    model_key,
                    total_groups,
                    workers,
                    MAX_COMPARE_WORKERS,
                )

            def evaluate_group(index: int, group: CompareInputGroup) -> tuple[int, CompareInputGroup, SingleTaskResult]:
                service = self._worker_service()
                result = service.evaluate_single(
                    domain=domain,
                    model_key=model_key,
                    file_path=group.file_path,
                    include_signal=include_signal,
                    progress_callback=aggregator.callback_for(group.key),
                    progress_prefix=f"{group.key} 文件",
                    progress_base=0,
                    progress_span=100,
                )
                return index, group, result

            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="audioqas-compare") as executor:
                futures = [
                    executor.submit(evaluate_group, index, group)
                    for index, group in enumerate(groups)
                ]
                for future in as_completed(futures):
                    index, group, result = future.result()
                    indexed_results[index] = (group, result)

            single_results = [item for item in indexed_results if item is not None]
            with set_event("compare_parallel_finished"):
                logger.info("compare_parallel_finished model=%s groups=%s workers=%s", model_key, total_groups, workers)

        sorted_results = sorted(
            single_results,
            key=lambda item: self._primary_dimension_score(item[1].model.result),
            reverse=True,
        )

        score_by_key = {
            group.key: self._primary_dimension_score(task.model.result)
            for group, task in single_results
        }
        resolved_base = base_key if base_key in score_by_key else None
        base_score = score_by_key.get(resolved_base) if resolved_base else None

        rank_by_key = {group.key: index + 1 for index, (group, _) in enumerate(sorted_results)}

        items = tuple(
            CompareGroupResult(
                key=group.key,
                file_path=group.file_path,
                task=task,
                rank=rank_by_key[group.key],
                delta_from_base=(score_by_key[group.key] - base_score) if base_score is not None else None,
            )
            for group, task in single_results
        )
        return CompareTaskResult(
            domain=domain,
            model_key=model_key,
            base_key=resolved_base,
            items=items,
        )


class _CompareProgressAggregator:
    _STAGE_WEIGHTS = {
        "preprocess_started": 0,
        "model_started": 0,
        "model_finished": 1,
        "signal_started": 1,
        "signal_finished": 2,
        "finished": 3,
    }

    def __init__(self, *, groups: list[str], callback: ProgressCallback | None, base: int, span: int) -> None:
        self._groups = groups
        self._callback = callback
        self._base = base
        self._span = span
        self._lock = Lock()
        self._weights = {group: 0 for group in groups}
        self._last_percent = base

    def callback_for(self, group_key: str) -> ProgressCallback | None:
        if self._callback is None:
            return None

        def callback(event: dict[str, Any]) -> None:
            with self._lock:
                current = self._weights[group_key]
                incoming = self._STAGE_WEIGHTS.get(str(event.get("stage")), current)
                self._weights[group_key] = max(current, incoming)
                total = max(len(self._groups), 1) * 3
                percent = self._base + round(self._span * sum(self._weights.values()) / total)
                percent = max(self._last_percent, min(self._base + self._span, percent))
                self._last_percent = percent
                finished = sum(1 for value in self._weights.values() if value >= 3)
                forwarded = {
                    **event,
                    "percent": percent,
                    "label": f"{event.get('label', group_key)} · {finished}/{len(self._groups)} 文件完成",
                }
            self._callback(forwarded)

        return callback
