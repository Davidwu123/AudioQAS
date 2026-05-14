from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen

from audioqas.ui.theme import load_tokens, _val, _color


class CompareDropZoneWidget(QWidget):
    file_selected = Signal(str)

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self._side = side  # "A" or "B"
        self._hover = False
        self._file_path = None
        self.setAcceptDrops(True)

        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_primary = _color(t, "text", "primary")
        txt_ter = _color(t, "text", "tertiary")
        txt_sec = _color(t, "text", "secondary")
        hover_bg = _color(t, "interactive", "hover")
        border_def = _color(t, "border", "default")
        accent_secondary = _color(t, "accent", "secondary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignCenter)

        self._side_label = QLabel(f"{side}")
        self._side_label.setAlignment(Qt.AlignCenter)
        side_color = "#3fb950" if side == "A" else accent
        self._side_label.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {side_color}; letter-spacing: 2px")
        layout.addWidget(self._side_label)

        self._file_label = QLabel("拖拽或点击选择文件")
        self._file_label.setAlignment(Qt.AlignCenter)
        self._file_label.setStyleSheet(f"font-size: 14px; color: {txt_ter}")
        layout.addWidget(self._file_label)

        fmt_label = QLabel("WAV/FLAC/MP3/MP4/MOV...")
        fmt_label.setAlignment(Qt.AlignCenter)
        fmt_label.setStyleSheet(f"font-size: 12px; color: {txt_ter}")
        layout.addWidget(fmt_label)

        layout.addSpacing(12)

        file_btn = QPushButton("选择文件")
        file_btn.setStyleSheet(f"background: {hover_bg}; color: #fff; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 500")
        file_btn.setCursor(Qt.PointingHandCursor)
        file_btn.clicked.connect(self._open_file_dialog)
        layout.addWidget(file_btn)

    def set_file(self, path: str):
        import os
        self._file_path = path
        name = os.path.basename(path)
        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        self._file_label.setText(f'<span style="font-weight:600;color:{txt_primary}">{name}</span>')
        self._file_label.setAlignment(Qt.AlignCenter)
        self._hover = False
        self.update()

    def _open_file_dialog(self):
        file, _ = QFileDialog.getOpenFileName(
            self, f"选择文件 {self._side}",
            "",
            "Audio/Video (*.wav *.flac *.mp3 *.aac *.ogg *.m4a *.mp4 *.mkv *.avi *.mov);;All (*)"
        )
        if file:
            self.set_file(file)
            self.file_selected.emit(file)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hover = True
            self.update()

    def dragLeaveEvent(self, event):
        self._hover = False
        self.update()

    def dropEvent(self, event):
        self._hover = False
        self.update()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_file(path)
            self.file_selected.emit(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(4, 4, -4, -4)

        if self._file_path:
            bg = QColor(22, 27, 34, int(0.65 * 255))
            border = QColor(48, 54, 61, int(0.8 * 255))
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1))
        elif self._hover:
            bg = QColor(88, 166, 255, int(0.05 * 255))
            border = QColor(0x58, 0xA6, 0xFF)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 2))
        else:
            bg = QColor(22, 27, 34, int(0.3 * 255))
            border = QColor(0x30, 0x36, 0x3D)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 2, Qt.DashLine))

        painter.drawRoundedRect(r, 16, 16)
        painter.end()
