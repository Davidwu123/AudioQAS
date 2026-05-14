from __future__ import annotations


class DimensionRegistry:
    """Central registry for model dimension metadata.

    Each model registers its dimension labels (dim_id -> Chinese label)
    and descriptions (dim_id -> {grade -> Chinese description}) at import time.
    UI components query the registry dynamically instead of hardcoding.
    """
    _LABELS: dict[str, dict[str, str]] = {}
    _DESCS: dict[str, dict[str, dict[str, str]]] = {}
    _METAPHORS: dict[str, dict[str, dict[str, str]]] = {}

    @classmethod
    def register(cls, model_id: str, labels: dict[str, str],
                 descriptions: dict[str, dict[str, str]],
                 metaphors: dict[str, dict[str, str]] | None = None):
        cls._LABELS[model_id] = labels
        cls._DESCS[model_id] = descriptions
        if metaphors:
            cls._METAPHORS[model_id] = metaphors

    @classmethod
    def labels(cls, model_id: str) -> dict[str, str]:
        return cls._LABELS.get(model_id, {})

    @classmethod
    def descriptions(cls, model_id: str) -> dict[str, dict[str, str]]:
        return cls._DESCS.get(model_id, {})

    @classmethod
    def metaphors(cls, model_id: str) -> dict[str, dict[str, str]]:
        return cls._METAPHORS.get(model_id, {})

    @classmethod
    def dimension_label(cls, model_id: str, dim: str) -> str:
        return cls._LABELS.get(model_id, {}).get(dim, dim)

    @classmethod
    def dimension_description(cls, model_id: str, dim: str, grade: str) -> str:
        return cls._DESCS.get(model_id, {}).get(dim, {}).get(grade, "")

    @classmethod
    def dimension_metaphor(cls, model_id: str, dim: str, grade: str) -> str:
        return cls._METAPHORS.get(model_id, {}).get(dim, {}).get(grade, "")
