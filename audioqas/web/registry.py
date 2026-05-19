from __future__ import annotations

from audioqas.web.schemas import EvalDomain, ModelDescriptor, ModelOption, SignalMetricDefinition, TaskDescriptor


class ModelRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskDescriptor] = {}
        self._models: dict[EvalDomain, ModelDescriptor] = {}
        self._signal_metrics: tuple[SignalMetricDefinition, ...] = ()

    def register_task(self, task: TaskDescriptor) -> None:
        self._tasks[task.page_key] = task

    def register_models(self, descriptor: ModelDescriptor) -> None:
        self._models[descriptor.domain] = descriptor

    def register_signal_metrics(self, metrics: tuple[SignalMetricDefinition, ...]) -> None:
        self._signal_metrics = metrics

    def tasks(self) -> list[TaskDescriptor]:
        return list(self._tasks.values())

    def task(self, page_key: str) -> TaskDescriptor:
        return self._tasks[page_key]

    def model_descriptor(self, domain: EvalDomain) -> ModelDescriptor:
        return self._models[domain]

    def signal_metrics(self) -> tuple[SignalMetricDefinition, ...]:
        return self._signal_metrics


default_registry = ModelRegistry()

default_registry.register_task(
    TaskDescriptor(
        page_key="eval",
        title="纯人声评测",
        subtitle="适用于通话、口播、会议、纯人声录音。评测结果同时包含当前模型结果、信号分析和预处理追溯。",
        domain=EvalDomain.SPEECH,
        accepts_audio=True,
        accepts_video=True,
        capabilities=("single", "compare", "history", "trace"),
    )
)
default_registry.register_task(
    TaskDescriptor(
        page_key="analysis",
        title="综合音频分析",
        subtitle="适用于人声+音乐、视频音轨、节目成品与混合内容。结果同时包含当前模型结果、信号分析和预处理追溯。",
        domain=EvalDomain.MIXED,
        accepts_audio=True,
        accepts_video=True,
        capabilities=("single", "compare", "history", "trace"),
    )
)
default_registry.register_task(
    TaskDescriptor(
        page_key="history",
        title="历史",
        subtitle="查看历史任务、结果摘要、预处理追溯和导出记录。",
        capabilities=("history",),
    )
)
default_registry.register_task(
    TaskDescriptor(
        page_key="settings",
        title="设置",
        subtitle="管理默认模型、结果显示、预处理、导出和历史设置。",
        capabilities=("settings",),
    )
)

default_registry.register_models(
    ModelDescriptor(
        domain=EvalDomain.SPEECH,
        primary_model="dnsmos",
        options=(
            ModelOption("dnsmos", "DNSMOS", "3维", ("OVRL", "SIG", "BAK")),
            ModelOption("nisqa", "NISQA", "4维", ("MOS", "Noisiness", "Discontinuity", "Coloration")),
        ),
    )
)
default_registry.register_models(
    ModelDescriptor(
        domain=EvalDomain.MIXED,
        primary_model="audiobox",
        options=(
            ModelOption("audiobox", "AudioBox Aesthetics", "4维", ("PQ", "CE", "CU", "PC")),
        ),
    )
)

default_registry.register_signal_metrics(
    (
        SignalMetricDefinition("LUFS", "综合响度", "LUFS"),
        SignalMetricDefinition("LRA", "响度范围", "LU"),
        SignalMetricDefinition("TruePeak", "真实峰值", "dBTP"),
        SignalMetricDefinition("Clipping", "削波次数", "count"),
        SignalMetricDefinition("THD", "谐波失真", "%"),
        SignalMetricDefinition("SNR", "信噪比", "dB", detail_only=True),
        SignalMetricDefinition("Stereo", "声像宽度", "band", detail_only=True),
    )
)

