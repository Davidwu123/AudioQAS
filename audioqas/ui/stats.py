import numpy as np
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

from audioqas.ui.theme import load_tokens, _color, _val


class StatItemWidget(QFrame):
    """Single stat block showing one dimension's mean/median/std."""

    def __init__(self, dimension: str, scores: list[float], parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)

        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        txt_primary = _color(t, "text", "primary")
        txt_sec = _color(t, "text", "secondary")
        accent = _color(t, "accent", "primary")
        surface = _color(t, "base", "surface")
        overlay = _color(t, "base", "overlay")

        arr = np.array(scores)
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        std_val = float(np.std(arr))

        DIMENSION_LABELS = {
            "OVRL": "OVRL · 整体听感",
            "SIG": "SIG · 语音清晰度",
            "BAK": "BAK · 背景干净度",
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        dim_label = QLabel(DIMENSION_LABELS.get(dimension, dimension))
        dim_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {accent}; letter-spacing: 0.5px")
        layout.addWidget(dim_label)

        mean_text = QLabel(f"均值 {mean_val:.2f}")
        mean_text.setStyleSheet(f"font-family: {mono}; font-size: 13px; color: {txt_primary}")
        layout.addWidget(mean_text)

        median_text = QLabel(f"中位 {median_val:.2f}")
        median_text.setStyleSheet(f"font-family: {mono}; font-size: 13px; color: {txt_primary}")
        layout.addWidget(median_text)

        std_text = QLabel(f"标准差 {std_val:.2f}")
        std_text.setStyleSheet(f"font-family: {mono}; font-size: 13px; color: {txt_sec}")
        layout.addWidget(std_text)

        self.setStyleSheet(f"background: {surface}; border: 1px solid {overlay}; border-radius: 10px")


class StatsWidget(QWidget):
    """Horizontal row of 3 stat items for OVRL/SIG/BAK."""

    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        for dim in ["OVRL", "SIG", "BAK"]:
            scores = [r["dimensions"][dim]["score"] for r in results]
            item = StatItemWidget(dim, scores)
            layout.addWidget(item)

        layout.addStretch()

    def update_stats(self, results: list[dict]):
        """Rebuild stat items when results change."""
        while self.layout().count() > 0:
            child = self.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for dim in ["OVRL", "SIG", "BAK"]:
            scores = [r["dimensions"][dim]["score"] for r in results]
            item = StatItemWidget(dim, scores)
            self.layout().addWidget(item)

        self.layout().addStretch()