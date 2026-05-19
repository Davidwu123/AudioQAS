from audioqas.core.scorer import ScoringManager
from audioqas.models.base import BaseScorer


class FakeScorer(BaseScorer):
    def __init__(self, name: str, dims: list[str]) -> None:
        self._name = name
        self._dims = dims

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "test"

    @property
    def dimensions(self) -> list[str]:
        return self._dims

    def score(self, audio_path: str):
        dims = {
            dim: {
                "score": float(index + 1),
                "grade": "Good",
                "description": f"{dim} ok",
            }
            for index, dim in enumerate(self._dims)
        }
        return {
            "eval_type": "mos",
            "model_name": self._name,
            "model_version": self.version,
            "dimensions": dims,
            "grade": "Good",
            "descriptions": {dim: f"{dim} ok" for dim in self._dims},
            "timestamp": "2026-05-18T00:00:00",
            "file_path": audio_path,
            "original_sr": 16000,
            "original_channels": 1,
            "duration": 1.23,
            "preprocessed": False,
            "preprocessed_path": audio_path,
        }


class TestScoringManager:
    def test_register_first_model_becomes_active(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        assert "DNSMOS" in mgr.available_models()
        assert mgr._active_model == "DNSMOS"

    def test_register_multiple_models(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        mgr.register(FakeScorer("NISQA", ["OVRL", "NOI", "DIS", "COL", "LOUD"]))
        assert mgr.available_models() == ["DNSMOS", "NISQA"]

    def test_set_active_model(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        mgr.register(FakeScorer("NISQA", ["OVRL", "NOI", "DIS", "COL", "LOUD"]))
        mgr.set_active_model("NISQA")
        assert mgr._active_model == "NISQA"

    def test_set_invalid_model_raises(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        try:
            mgr.set_active_model("NISQA")
        except ValueError as exc:
            assert "not registered" in str(exc)
        else:
            raise AssertionError("ValueError not raised")

    def test_score_file_uses_active_model(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        result = mgr.score_file("sample.wav")
        assert result["model_name"] == "DNSMOS"
        assert result["file_path"] == "sample.wav"
        assert "OVRL" in result["dimensions"]

    def test_score_file_after_switch(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        mgr.register(FakeScorer("NISQA", ["OVRL", "NOI", "DIS", "COL", "LOUD"]))
        mgr.set_active_model("NISQA")
        result = mgr.score_file("sample.wav")
        assert result["model_name"] == "NISQA"
        assert "NOI" in result["dimensions"]

    def test_score_batch_preserves_count_and_model(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        files = ["a.wav", "b.wav", "c.wav"]
        results = mgr.score_batch(files, max_workers=2)
        assert len(results) == 3
        assert {result["file_path"] for result in results} == set(files)
        assert all(result["model_name"] == "DNSMOS" for result in results)

    def test_score_batch_invokes_progress_callback(self):
        mgr = ScoringManager()
        mgr.register(FakeScorer("DNSMOS", ["OVRL", "SIG", "BAK"]))
        files = ["a.wav", "b.wav"]
        calls = []

        def on_progress(done, total, result):
            calls.append((done, total, result["file_path"]))

        mgr.score_batch(files, progress_callback=on_progress, max_workers=2)
        assert len(calls) == 2
        assert all(total == 2 for _, total, _ in calls)
        assert {path for _, _, path in calls} == set(files)
