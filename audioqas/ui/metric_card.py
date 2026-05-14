from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from audioqas.ui.theme import load_tokens, _color, _val


GRADE_COLORS = {
    "Good": "#3FB950",
    "Warning": "#D29922",
    "Poor": "#F85149",
}


class MetricCardWidget(QFrame):
    def __init__(self, metric_name: str, parent=None):
        super().__init__(parent)
        self._metric_name = metric_name
        self._value = 0.0
        self._unit = ""
        self._grade = ""
        self._description = ""
        self._pulse_active = False
        self._pulse_phase = 0.0

        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName("metricCard")
        self.setFixedWidth(160)
        self.setMinimumHeight(140)
        self.setCursor(Qt.ArrowCursor)

        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        overlay = _color(t, "base", "overlay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        self._label = QLabel(metric_name)
        self._label.setStyleSheet(f"font-size: 11px; font-weight: 500; letter-spacing: 0.5px; color: {txt_sec}")
        layout.addWidget(self._label)

        self._number = QLabel("--")
        self._number.setStyleSheet(f"font-family: {mono}; font-size: 28px; font-weight: 700; color: {txt_sec}; line-height: 1.1;")
        layout.addWidget(self._number)

        self._grade_label = QLabel("")
        self._grade_label.setStyleSheet(f"font-size: 12px; font-weight: 600;")
        layout.addWidget(self._grade_label)

        self._desc_label = QLabel("")
        self._desc_label.setStyleSheet(f"font-size: 11px; color: {txt_ter}")
        layout.addWidget(self._desc_label)

        self._grade_color_hex = "#484F58"
        self._grade_color = QColor("#484F58")

    def set_metric(self, value: float, unit: str, grade: str, description: str):
        self._value = value
        self._unit = unit
        self._grade = grade
        self._description = description

        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")

        color = GRADE_COLORS.get(grade, "#484F58")

        # Format value display
        if unit == "次":
            value_text = f"{int(value)} {unit}"
        elif unit == "%":
            value_text = f"{value:.1f}{unit}"
        elif unit in ("LUFS", "LU", "dBTP", "Hz"):
            value_text = f"{value:.1f}"
        else:
            value_text = f"{value:.2f}"

        self._number.setText(value_text)
        self._number.setStyleSheet(f"font-family: {mono}; font-size: 28px; font-weight: 700; color: {color}; line-height: 1.1;")

        self._grade_label.setText(grade)
        self._grade_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {color}")

        self._desc_label.setText(description)
        self._desc_label.setStyleSheet(f"font-size: 11px; color: {txt_ter}")

        self._grade_color_hex = color
        self._grade_color = QColor(color)
        self.start_pulse()

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
        painter.drawRoundedRect(r, 12, 12)

        highlight_pen = QPen(QColor(139, 148, 158, int(0.15 * 255)), 1)
        painter.setPen(highlight_pen)
        painter.drawLine(r.left() + 12, r.top(), r.right() - 12, r.top())

        if self._pulse_active:
            phase = self._pulse_phase
            if phase <= 0.5:
                glow_alpha = int(phase * 2 * 60)
            else:
                glow_alpha = int((1.0 - phase) * 2 * 60)
            glow_color = QColor(self._grade_color)
            glow_color.setAlpha(glow_alpha)
            painter.setPen(QPen(glow_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(r, 12, 12)

        painter.end()
