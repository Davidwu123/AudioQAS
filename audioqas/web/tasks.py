from __future__ import annotations

from dataclasses import dataclass
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
    def __init__(self, runners: TaskRunners | None = None) -> None:
        self._runners = runners or default_task_runners()
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
            model_result = model_runner.score(file_path)
            with set_event("model_result_ready"):
                logger.debug(
                    "model_result_ready model=%s grade=%s dimensions=%s",
                    model_key,
                    model_result["grade"],
                    sorted(model_result["dimensions"].keys()),
                )
            signal_result = self._runners.signal_runner.analyze(file_path) if include_signal else None
            if signal_result is not None:
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
    ) -> CompareTaskResult:
        single_results = [
            (group, self.evaluate_single(
                domain=domain,
                model_key=model_key,
                file_path=group.file_path,
                include_signal=include_signal,
            ))
            for group in groups
        ]

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
