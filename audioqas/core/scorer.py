from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from audioqas.models.base import BaseScorer, ScoreResult


class ScoringManager:
    def __init__(self) -> None:
        self._scorers: dict[str, BaseScorer] = {}
        self._active_model: str | None = None

    def register(self, scorer: BaseScorer) -> None:
        self._scorers[scorer.name] = scorer
        if self._active_model is None:
            self._active_model = scorer.name

    def set_active_model(self, model_name: str) -> None:
        if model_name not in self._scorers:
            raise ValueError(f"Model '{model_name}' not registered. Available: {list(self._scorers)}")
        self._active_model = model_name

    def available_models(self) -> list[str]:
        return list(self._scorers)

    def score_file(self, audio_path: str) -> ScoreResult:
        if self._active_model is None:
            raise RuntimeError("No active model set")
        return self._scorers[self._active_model].score(audio_path)

    def score_batch(
        self,
        file_paths: list[str],
        progress_callback: Callable[[int, int, ScoreResult], None] | None = None,
        max_workers: int = 4,
    ) -> list[ScoreResult]:
        if self._active_model is None:
            raise RuntimeError("No active model set")
        scorer = self._scorers[self._active_model]

        results: list[ScoreResult] = []
        total = len(file_paths)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(scorer.score, path): path
                for path in file_paths
            }

            for future in as_completed(future_map):
                path = future_map[future]
                result = future.result()
                results.append(result)
                if progress_callback:
                    progress_callback(len(results), total, result)

        return results