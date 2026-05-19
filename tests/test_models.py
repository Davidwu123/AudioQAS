from audioqas.models import BaseScorer, ScoreResult, score_to_grade
from audioqas.models.base import GRADE_MAP


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


class TestModelExports:
    def test_base_exports_available(self):
        assert BaseScorer is not None
        assert ScoreResult is not None

    def test_grade_map_descending_thresholds(self):
        thresholds = [threshold for threshold, _ in GRADE_MAP]
        assert thresholds == sorted(thresholds, reverse=True)

    def test_grade_labels_complete(self):
        labels = [label for _, label in GRADE_MAP]
        assert labels == ["Excellent", "Good", "Fair", "Poor", "Bad"]

