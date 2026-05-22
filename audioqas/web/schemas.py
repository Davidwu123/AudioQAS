from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EvalDomain(StrEnum):
    SPEECH = "speech"
    MIXED = "mixed"


@dataclass(frozen=True)
class ModelOption:
    key: str
    label: str
    short_tag: str
    dimensions: tuple[str, ...]


@dataclass(frozen=True)
class ModelDescriptor:
    domain: EvalDomain
    primary_model: str
    options: tuple[ModelOption, ...]
    supports_signal_analysis: bool = True


@dataclass(frozen=True)
class SignalMetricDefinition:
    key: str
    label: str
    unit: str
    detail_only: bool = False


@dataclass(frozen=True)
class TaskDescriptor:
    page_key: str
    title: str
    subtitle: str
    domain: EvalDomain | None = None
    accepts_audio: bool = True
    accepts_video: bool = False
    capabilities: tuple[str, ...] = field(default_factory=tuple)

