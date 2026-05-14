import pytest
from audioqas.models.base import BaseScorer, ScoreResult, score_to_grade


class TestScoreToGrade:
    def test_excellent(self):
        assert score_to_grade(4.8) == "Excellent"
        assert score_to_grade(4.5) == "Excellent"

    def test_good(self):
        assert score_to_grade(4.0) == "Good"
        assert score_to_grade(4.49) == "Good"

    def test_fair(self):
        assert score_to_grade(3.0) == "Fair"
        assert score_to_grade(3.99) == "Fair"

    def test_poor(self):
        assert score_to_grade(2.0) == "Poor"
        assert score_to_grade(2.99) == "Poor"

    def test_bad(self):
        assert score_to_grade(0.0) == "Bad"
        assert score_to_grade(1.99) == "Bad"


class TestDNSMOSScorer:
    @pytest.fixture
    def scorer(self):
        from audioqas.models.dnsmos import DNSMOSScorer
        return DNSMOSScorer()

    def test_properties(self, scorer):
        assert scorer.name == "DNSMOS"
        assert scorer.version == "v8"
        assert scorer.dimensions == ["OVRL", "SIG", "BAK"]

    def test_score_real_file(self, scorer):
        result = scorer.score("/Users/wuwei/Downloads/processed/00.wav")
        assert result["model_name"] == "DNSMOS"
        assert result["model_version"] == "v8"
        assert "OVRL" in result["dimensions"]
        assert "SIG" in result["dimensions"]
        assert "BAK" in result["dimensions"]
        for dim in ["OVRL", "SIG", "BAK"]:
            info = result["dimensions"][dim]
            assert 0 <= info["score"] <= 5
            assert info["grade"] in ["Bad", "Poor", "Fair", "Good", "Excellent"]
            assert info["description"]
        assert result["original_sr"] == 48000
        assert result["original_channels"] == 2
        assert result["duration"] > 0
        assert result["preprocessed"] in [True, False]


class TestNISQAScorer:
    @pytest.fixture
    def scorer(self):
        from audioqas.models.nisqa import NISQAScorer
        return NISQAScorer()

    def test_properties(self, scorer):
        assert scorer.name == "NISQA"
        assert scorer.version == "v2"
        assert scorer.dimensions == ["OVRL", "NOI", "DIS", "COL", "LOUD"]

    def test_score_real_file(self, scorer):
        result = scorer.score("/Users/wuwei/Downloads/processed/00.wav")
        assert result["model_name"] == "NISQA"
        assert result["model_version"] == "v2"
        for dim in ["OVRL", "NOI", "DIS", "COL", "LOUD"]:
            info = result["dimensions"][dim]
            assert 0 <= info["score"] <= 5
            assert info["grade"] in ["Bad", "Poor", "Fair", "Good", "Excellent"]
            assert info["description"]
        assert result["original_sr"] == 48000
        assert result["original_channels"] == 2
        assert result["preprocessed"] in [True, False]


class TestVideoExtraction:
    @pytest.fixture
    def scorer(self):
        from audioqas.models.dnsmos import DNSMOSScorer
        return DNSMOSScorer()

    def test_mov_file(self, scorer):
        mov_path = "/Users/wuwei/Downloads/破碎_主播测试_202605/20260512测试录屏/tata_pc_慢歌.mov"
        import os
        if not os.path.exists(mov_path):
            pytest.skip("MOV test file not available")
        result = scorer.score(mov_path)
        assert result["model_name"] == "DNSMOS"
        assert "OVRL" in result["dimensions"]
        assert result["preprocessed"] in [True, False]
