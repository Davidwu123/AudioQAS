from threading import Barrier, Lock
import time

from audioqas.web.runtime import SingleTaskResult
from audioqas.web.runtime import CompareInputGroup
from audioqas.web.schemas import EvalDomain
from audioqas.web.tasks import EvaluationService, TaskRunners


class FakeModelRunner:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def score(self, audio_path: str):
        return {
            "eval_type": "mos",
            "model_name": self._model_name,
            "model_version": "test",
            "dimensions": {"OVRL": {"score": 4.0, "grade": "Good", "description": "ok"}},
            "grade": "Good",
            "descriptions": {"OVRL": "ok"},
            "timestamp": "2026-05-18T00:00:00",
            "file_path": audio_path,
            "original_sr": 16000,
            "original_channels": 1,
            "duration": 1.0,
            "preprocessed": False,
            "preprocessed_path": audio_path,
        }


class FakeSignalRunner:
    def analyze(self, audio_path: str):
        return {
            "eval_type": "analysis",
            "model_name": "AudioAnalyzer",
            "model_version": "test",
            "metrics": {
                "LUFS": {
                    "value": -16.0,
                    "unit": "LUFS",
                    "grade": "Good",
                    "description": "ok",
                    "threshold_good": -23.0,
                    "threshold_warn": -26.0,
                }
            },
            "grade": "Good",
            "timestamp": "2026-05-18T00:00:00",
            "file_path": audio_path,
            "original_sr": 16000,
            "original_channels": 1,
            "duration": 1.0,
            "preprocessed": False,
            "preprocessed_path": audio_path,
        }


class BlockingModelRunner(FakeModelRunner):
    def __init__(self, model_name: str, barrier: Barrier) -> None:
        super().__init__(model_name)
        self._barrier = barrier

    def score(self, audio_path: str):
        self._barrier.wait(timeout=2)
        return super().score(audio_path)


class CountingModelRunner(FakeModelRunner):
    def __init__(self, model_name: str, delay: float = 0.05) -> None:
        super().__init__(model_name)
        self._delay = delay
        self._lock = Lock()
        self.active = 0
        self.peak = 0

    def score(self, audio_path: str):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self._delay)
            return super().score(audio_path)
        finally:
            with self._lock:
                self.active -= 1


def make_service() -> EvaluationService:
    return EvaluationService(
        TaskRunners(
            speech_models={
                "dnsmos": FakeModelRunner("DNSMOS"),
                "nisqa": FakeModelRunner("NISQA"),
            },
            mixed_models={
                "audiobox": FakeModelRunner("AudioBox-Aesthetics"),
            },
            signal_runner=FakeSignalRunner(),
        )
    )


def test_evaluate_single_speech():
    service = make_service()
    result = service.evaluate_single(domain=EvalDomain.SPEECH, model_key="dnsmos", file_path="speech.wav")
    assert isinstance(result, SingleTaskResult)
    assert result.domain == EvalDomain.SPEECH
    assert result.model.model_key == "dnsmos"
    assert result.model.result["model_name"] == "DNSMOS"
    assert result.signal is not None


def test_evaluate_single_mixed():
    service = make_service()
    result = service.evaluate_single(domain=EvalDomain.MIXED, model_key="audiobox", file_path="mix.wav")
    assert result.domain == EvalDomain.MIXED
    assert result.model.result["model_name"] == "AudioBox-Aesthetics"


def test_evaluate_single_without_signal():
    service = make_service()
    result = service.evaluate_single(
        domain=EvalDomain.SPEECH,
        model_key="nisqa",
        file_path="speech.wav",
        include_signal=False,
    )
    assert result.signal is None


def test_evaluate_single_reports_observable_progress_stages():
    service = make_service()
    events = []

    result = service.evaluate_single(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        file_path="speech.wav",
        include_signal=True,
        progress_callback=lambda event: events.append(event),
    )

    assert result.model.model_key == "dnsmos"
    assert [event["stage"] for event in events] == [
        "preprocess_started",
        "model_started",
        "model_finished",
        "signal_started",
        "signal_finished",
        "finished",
    ]
    assert events[-1]["percent"] == 100


def test_unknown_model_raises():
    service = make_service()
    try:
        service.evaluate_single(domain=EvalDomain.SPEECH, model_key="missing", file_path="speech.wav")
    except KeyError as exc:
        assert "Unknown model" in str(exc)
    else:
        raise AssertionError("KeyError not raised")


def test_evaluate_batch_returns_all_items():
    service = make_service()
    result = service.evaluate_batch(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        file_paths=["a.wav", "b.wav"],
    )
    assert result.domain == EvalDomain.SPEECH
    assert result.model_key == "dnsmos"
    assert len(result.items) == 2


def test_evaluate_compare_returns_rank_and_delta():
    service = make_service()
    result = service.evaluate_compare(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        groups=[
            CompareInputGroup(key="A", file_path="a.wav"),
            CompareInputGroup(key="B", file_path="b.wav"),
        ],
        base_key="A",
        include_signal=False,
    )
    assert result.base_key == "A"
    assert len(result.items) == 2
    item_b = next(item for item in result.items if item.key == "B")
    assert item_b.rank >= 1
    assert item_b.delta_from_base is not None


def test_evaluate_compare_runs_files_concurrently_by_default():
    runner = BlockingModelRunner("DNSMOS", Barrier(3))
    service = EvaluationService(
        TaskRunners(
            speech_models={"dnsmos": runner},
            mixed_models={},
            signal_runner=FakeSignalRunner(),
        )
    )

    result = service.evaluate_compare(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        groups=[
            CompareInputGroup(key="A", file_path="a.wav"),
            CompareInputGroup(key="B", file_path="b.wav"),
            CompareInputGroup(key="C", file_path="c.wav"),
        ],
        include_signal=False,
    )

    assert [item.key for item in result.items] == ["A", "B", "C"]


def test_evaluate_compare_caps_parallel_workers_at_four():
    runner = CountingModelRunner("DNSMOS")
    service = EvaluationService(
        TaskRunners(
            speech_models={"dnsmos": runner},
            mixed_models={},
            signal_runner=FakeSignalRunner(),
        )
    )

    result = service.evaluate_compare(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        groups=[
            CompareInputGroup(key="A", file_path="a.wav"),
            CompareInputGroup(key="B", file_path="b.wav"),
            CompareInputGroup(key="C", file_path="c.wav"),
            CompareInputGroup(key="D", file_path="d.wav"),
            CompareInputGroup(key="E", file_path="e.wav"),
            CompareInputGroup(key="F", file_path="f.wav"),
        ],
        include_signal=False,
    )

    assert len(result.items) == 6
    assert runner.peak == 4


def test_evaluate_compare_progress_percent_is_monotonic_when_events_are_out_of_order():
    service = make_service()
    events = []

    service.evaluate_compare(
        domain=EvalDomain.SPEECH,
        model_key="dnsmos",
        groups=[
            CompareInputGroup(key="A", file_path="a.wav"),
            CompareInputGroup(key="B", file_path="b.wav"),
            CompareInputGroup(key="C", file_path="c.wav"),
        ],
        include_signal=True,
        progress_callback=lambda event: events.append(event),
    )

    percents = [event["percent"] for event in events]
    assert percents == sorted(percents)
    assert percents[-1] <= 95


def test_evaluate_single_logs_task_events(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    service = make_service()

    service.evaluate_single(domain=EvalDomain.SPEECH, model_key="dnsmos", file_path="speech.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "task_started" in text
    assert "task_finished" in text


def test_evaluate_single_debug_logs_include_model_result_summary(tmp_path):
    from audioqas.logging import setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    service = make_service()

    service.evaluate_single(domain=EvalDomain.SPEECH, model_key="dnsmos", file_path="speech.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "model_result_ready" in text
    assert "signal_result_ready" in text


def test_evaluate_single_reuses_existing_request_id(tmp_path):
    from audioqas.logging import log_context, setup_logging

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    service = make_service()

    with log_context(request_id="req_ui_test_001", scene="single"):
        service.evaluate_single(domain=EvalDomain.SPEECH, model_key="dnsmos", file_path="speech.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "[req_ui_test_001][single][task_started]" in text
    assert "req_task_" not in text


def test_evaluate_single_supports_default_model_switch_from_settings():
    service = make_service()

    result = service.evaluate_single(domain=EvalDomain.SPEECH, model_key="nisqa", file_path="speech.wav")

    assert result.model.model_key == "nisqa"
    assert result.model.result["model_name"] == "NISQA"
