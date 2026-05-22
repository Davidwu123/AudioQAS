from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from audioqas.models.analysis import AnalysisResult
from audioqas.models.base import ScoreResult
from audioqas.web.schemas import EvalDomain


class ModelRunner(Protocol):
    def score(self, audio_path: str) -> ScoreResult:
        ...


class SignalRunner(Protocol):
    def analyze(self, audio_path: str) -> AnalysisResult:
        ...


@dataclass(frozen=True)
class ModelExecutionResult:
    model_key: str
    domain: EvalDomain
    result: ScoreResult


@dataclass(frozen=True)
class SignalExecutionResult:
    result: AnalysisResult


@dataclass(frozen=True)
class SingleTaskResult:
    domain: EvalDomain
    file_path: str
    model: ModelExecutionResult
    signal: SignalExecutionResult | None


@dataclass(frozen=True)
class BatchTaskResult:
    domain: EvalDomain
    model_key: str
    items: tuple[SingleTaskResult, ...]


@dataclass(frozen=True)
class CompareInputGroup:
    key: str
    file_path: str


@dataclass(frozen=True)
class CompareGroupResult:
    key: str
    file_path: str
    task: SingleTaskResult
    rank: int
    delta_from_base: float | None


@dataclass(frozen=True)
class CompareTaskResult:
    domain: EvalDomain
    model_key: str
    base_key: str | None
    items: tuple[CompareGroupResult, ...]
