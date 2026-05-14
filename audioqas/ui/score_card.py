from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from audioqas.ui.theme import score_color, score_grade, score_description, load_tokens, _val, _color
from audioqas.core.dimensions import DimensionRegistry


class ScoreCardWidget(QFrame):
    def __init__(self, dimension: str, score: float = 0.0,
                 model_id: str = "DNSMOS", parent=None):
        super().__init__(parent)
        self.dimension = dimension
        self._model_id = model_id
        self._score = score
        self._pulse_active = False
        self._pulse_phase = 0.0

        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("scoreCard")
        self.setFixedWidth(200)
        self.setMinimumHeight(260)
        self.setCursor(Qt.ArrowCursor)

        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        overlay = _color(t, "base", "overlay")

        dim_label = DimensionRegistry.dimension_label(model_id, dimension)
        info_label = f"{dimension} · {dim_label}"
        grade = score_grade(score)
        color = score_color(score)
        desc = score_description(score)
        metaphor = DimensionRegistry.dimension_metaphor(model_id, dimension, grade)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(4)

        self._label = QLabel(info_label)
        self._label.setStyleSheet(f"font-size: 13px; font-weight: 500; letter-spacing: 0.5px; color: {txt_sec}")
        layout.addWidget(self._label)

        self._number = QLabel(f"{score:.2f}" if score > 0 else "--")
        self._number.setStyleSheet(f"font-family: {mono}; font-size: 48px; font-weight: 700; color: {color}; line-height: 1.1;")
        layout.addWidget(self._number)

        self._progress = QProgressBar()
        self._progress.setRange(0, 500)
        self._progress.setValue(int(score * 100) if score > 0 else 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: {overlay};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self._progress)
        layout.addSpacing(12)

        self._grade = QLabel(grade)
        self._grade.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {color}")
        layout.addWidget(self._grade)

        self._desc = QLabel(desc)
        self._desc.setStyleSheet(f"font-size: 13px; color: {txt_sec}; font-weight: 500")
        layout.addWidget(self._desc)

        self._metaphor = QLabel(metaphor)
        self._metaphor.setStyleSheet(f"font-size: 11px; color: {txt_ter}; line-height: 1.4")
        self._metaphor.setWordWrap(True)
        layout.addWidget(self._metaphor)

        self._score_color_hex = color
        self._score_color = QColor(color)

    def set_score(self, score: float, label: str = None, desc_override: str = None):
        self._score = score
        model_id = self._model_id
        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        overlay = _color(t, "base", "overlay")

        grade = score_grade(score)
        color = score_color(score)
        desc = desc_override if desc_override else score_description(score)
        metaphor = DimensionRegistry.dimension_metaphor(model_id, self.dimension, grade)

        if label:
            self._label.setText(label)
            self._label.setStyleSheet(f"font-size: 13px; font-weight: 500; letter-spacing: 0.5px; color: {txt_sec}")

        self._number.setText(f"{score:.2f}")
        self._number.setStyleSheet(f"font-family: {mono}; font-size: 48px; font-weight: 700; color: {color}")
        self._progress.setValue(int(score * 100))
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: {overlay};
                border-radius: 2px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 2px;
            }}
        """)
        self._grade.setText(grade)
        self._grade.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {color}")
        self._desc.setText(desc)
        self._desc.setStyleSheet(f"font-size: 13px; color: {txt_sec}; font-weight: 500")
        self._metaphor.setText(metaphor)
        self._metaphor.setStyleSheet(f"font-size: 11px; color: {txt_ter}; line-height: 1.4")
        self._score_color_hex = color
        self._score_color = QColor(color)
        self.start_pulse()

    def set_model_id(self, model_id: str):
        self._model_id = model_id

    def start_pulse(self):
        self._pulse_active = True
        self._pulse_phase = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_timer.start(16)
        QTimer.singleShot(400, self._stop_pulse)

    def _pulse_tick(self):
        self._pulse_phase += 16 / 400.0
        self.update()

    def _stop_pulse(self):
        self._pulse_active = False
        self._pulse_phase = 0.0
        if hasattr(self, "_pulse_timer"):
            self._pulse_timer.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.rect().adjusted(1, 1, -1, -1)

        painter.setBrush(QBrush(QColor(22, 27, 34, int(0.65 * 255))))
        painter.setPen(QPen(QColor(48, 54, 61, int(0.6 * 255)), 1))
        painter.drawRoundedRect(r, 14, 14)

        highlight_pen = QPen(QColor(139, 148, 158, int(0.15 * 255)), 1)
        painter.setPen(highlight_pen)
        painter.drawLine(r.left() + 14, r.top(), r.right() - 14, r.top())

        if self._pulse_active:
            phase = self._pulse_phase
            if phase <= 0.5:
                glow_alpha = int(phase * 2 * 60)
            else:
                glow_alpha = int((1.0 - phase) * 2 * 60)
            glow_color = QColor(self._score_color)
            glow_color.setAlpha(glow_alpha)
            painter.setPen(QPen(glow_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(r, 14, 14)

        painter.end()
