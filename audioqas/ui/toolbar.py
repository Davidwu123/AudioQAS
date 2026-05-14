from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor

from audioqas.ui.theme import load_tokens, _color


class EvalToolbarWidget(QWidget):
    add_file = Signal()
    compare = Signal()
    export = Signal()
    reset = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)

        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")
        border_def = _color(t, "border", "default")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(12)

        btn_style = (
            f"background: transparent; color: {txt_sec}; "
            f"border: 1px solid {border_def}; border-radius: 8px; "
            f"padding: 8px 16px; font-size: 13px; font-weight: 500"
        )

        add_btn = QPushButton("+ 添加文件")
        add_btn.setStyleSheet(btn_style)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self.add_file.emit)
        layout.addWidget(add_btn)

        cmp_btn = QPushButton("对比评测")
        cmp_btn.setStyleSheet(btn_style)
        cmp_btn.setCursor(Qt.PointingHandCursor)
        cmp_btn.clicked.connect(self.compare.emit)
        layout.addWidget(cmp_btn)

        export_btn = QPushButton("导出结果")
        export_btn.setStyleSheet(btn_style)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self.export.emit)
        layout.addWidget(export_btn)

        reset_btn = QPushButton("重置")
        reset_btn.setStyleSheet(btn_style)
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.clicked.connect(self.reset.emit)
        layout.addWidget(reset_btn)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"font-size: 13px; color: {txt_sec}")
        layout.addStretch()
        layout.addWidget(self._progress_label)

    def progress_label(self):
        return self._progress_label

    def paintEvent(self, event):
        painter = QPainter(self)
        bg = QColor(22, 27, 34, int(0.75 * 255))
        painter.fillRect(self.rect(), bg)
        painter.setPen(QColor(0x21, 0x26, 0x2D))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        painter.end()
