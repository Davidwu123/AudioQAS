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
