import pytest
from audioqas.core.scorer import ScoringManager
from audioqas.models.dnsmos import DNSMOSScorer
from audioqas.models.nisqa import NISQAScorer


class TestScoringManager:
    def test_register_dnsmos(self):
        mgr = ScoringManager()
        scorer = DNSMOSScorer()
        mgr.register(scorer)
        assert "DNSMOS" in mgr.available_models()
        assert mgr._active_model == "DNSMOS"

    def test_register_multiple(self):
        mgr = ScoringManager()
        mgr.register(DNSMOSScorer())
        mgr.register(NISQAScorer())
        assert len(mgr.available_models()) == 2
        assert "DNSMOS" in mgr.available_models()
        assert "NISQA" in mgr.available_models()

    def test_set_active_model(self):
        mgr = ScoringManager()
        mgr.register(DNSMOSScorer())
        mgr.register(NISQAScorer())
        mgr.set_active_model("NISQA")
        assert mgr._active_model == "NISQA"

    def test_set_invalid_model(self):
        mgr = ScoringManager()
        mgr.register(DNSMOSScorer())
        with pytest.raises(ValueError, match="not registered"):
            mgr.set_active_model("NISQA")

    def test_score_file(self):
        mgr = ScoringManager()
        mgr.register(DNSMOSScorer())
        result = mgr.score_file("/Users/wuwei/Downloads/processed/00.wav")
        assert result["model_name"] == "DNSMOS"

    def test_score_file_nisqa(self):
        mgr = ScoringManager()
        mgr.register(NISQAScorer())
        mgr.set_active_model("NISQA")
        result = mgr.score_file("/Users/wuwei/Downloads/processed/00.wav")
        assert result["model_name"] == "NISQA"
        assert "NOI" in result["dimensions"]

    def test_score_batch(self):
        import glob, os
        mgr = ScoringManager()
        mgr.register(DNSMOSScorer())
        files = sorted(glob.glob("/Users/wuwei/Downloads/processed/*.wav"))[:3]
        results = mgr.score_batch(files, max_workers=2)
        assert len(results) == 3
        for r in results:
            assert "OVRL" in r["dimensions"]
