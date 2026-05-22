from abc import ABC, abstractmethod
from typing import TypedDict


class DimensionScore(TypedDict):
    score: float
    grade: str
    description: str


DimensionsDict = dict[str, DimensionScore]


class ScoreResult(TypedDict):
    eval_type: str  # "mos" or "analysis"
    model_name: str
    model_version: str
    dimensions: DimensionsDict
    grade: str
    descriptions: dict[str, str]
    timestamp: str
    file_path: str
    original_sr: int
    original_channels: int
    duration: float
    preprocessed: bool
    preprocessed_path: str  # path to the intermediate file for manual verification
    pipeline_steps: list[str]
    preprocess_settings: dict[str, bool]


GRADE_MAP = [
    (4.5, "Excellent"),
    (4.0, "Good"),
    (3.0, "Fair"),
    (2.0, "Poor"),
    (0.0, "Bad"),
]


def score_to_grade(score: float) -> str:
    for threshold, grade in GRADE_MAP:
        if score >= threshold:
            return grade
    return "Bad"


class BaseScorer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        ...

    @property
    @abstractmethod
    def dimensions(self) -> list[str]:
        ...

    @abstractmethod
    def score(self, audio_path: str) -> ScoreResult:
        ...
