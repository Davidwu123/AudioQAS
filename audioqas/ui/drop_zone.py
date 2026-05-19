from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFileDialog
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen

from audioqas.ui.theme import load_tokens, _val, _color


class DropZoneWidget(QWidget):
    files_dropped = Signal(list)
    dir_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self._title_text = "拖拽音频/视频文件到此处"
        self._subtitle_text = "或点击选择文件/目录"
        self._audio_formats_text = "WAV / FLAC / MP3 / AAC / OGG / M4A"
        self._video_formats_text = "MP4 / MKV / AVI / MOV (自动提取音轨)"
        self._dir_enabled = True
        self.setAcceptDrops(True)
        self.setMinimumHeight(300)

        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_primary = _color(t, "text", "primary")
        txt_tertiary = _color(t, "text", "tertiary")
        accent_secondary = _color(t, "accent", "secondary")
        hover_bg = _color(t, "interactive", "hover")
        txt_sec = _color(t, "text", "secondary")
        border_def = _color(t, "border", "default")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setAlignment(Qt.AlignCenter)

        inner = QWidget()
        inner.setObjectName("dropZoneInner")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(48, 48, 48, 48)
        inner_layout.setAlignment(Qt.AlignCenter)
        inner_layout.setSpacing(8)

        self._title = QLabel(self._title_text)
        self._title.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {txt_primary}")
        self._title.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self._title)

        self._subtitle = QLabel(self._subtitle_text)
        self._subtitle.setStyleSheet(f"font-size: 15px; color: {txt_tertiary}")
        self._subtitle.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self._subtitle)

        inner_layout.addSpacing(8)

        self._fmt_audio = QLabel(self._audio_formats_text)
        self._fmt_audio.setStyleSheet(f"font-size: 13px; color: {txt_tertiary}")
        self._fmt_audio.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self._fmt_audio)

        self._fmt_video = QLabel(self._video_formats_text)
        self._fmt_video.setStyleSheet(f"font-size: 13px; color: {accent_secondary}")
        self._fmt_video.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self._fmt_video)

        inner_layout.addSpacing(24)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(12)

        file_btn = QPushButton("选择文件")
        file_btn.setStyleSheet(f"background: {hover_bg}; color: #fff; border: none; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 500")
        file_btn.setCursor(Qt.PointingHandCursor)
        file_btn.clicked.connect(self._open_file_dialog)
        btn_layout.addWidget(file_btn)

        self._dir_btn = QPushButton("选择目录")
        self._dir_btn.setStyleSheet(f"background: transparent; color: {txt_sec}; border: 1px solid {border_def}; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 500")
        self._dir_btn.setCursor(Qt.PointingHandCursor)
        self._dir_btn.clicked.connect(self._open_dir_dialog)
        btn_layout.addWidget(self._dir_btn)

        inner_layout.addLayout(btn_layout)
        layout.addWidget(inner)

    def set_texts(
        self,
        title: str,
        subtitle: str,
        audio_formats: str | None = None,
        video_formats: str | None = None,
    ):
        self._title_text = title
        self._subtitle_text = subtitle
        self._title.setText(title)
        self._subtitle.setText(subtitle)
        if audio_formats is not None:
            self._audio_formats_text = audio_formats
            self._fmt_audio.setText(audio_formats)
        if video_formats is not None:
            self._video_formats_text = video_formats
            self._fmt_video.setText(video_formats)

    def set_directory_enabled(self, enabled: bool):
        self._dir_enabled = enabled
        self._dir_btn.setVisible(enabled)

    def _open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频/视频文件",
            "",
            "Audio/Video Files (*.wav *.flac *.mp3 *.aac *.ogg *.m4a *.mp4 *.mkv *.avi *.mov);;All Files (*)"
        )
        if files:
            self.files_dropped.emit(files)

    def _open_dir_dialog(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择目录")
        if dir_path:
            self.dir_selected.emit(dir_path)

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
        paths = [u.toLocalFile() for u in urls]
        if paths:
            self.files_dropped.emit(paths)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.rect().adjusted(8, 8, -8, -8)

        if self._hover:
            bg_color = QColor(88, 166, 255, int(0.05 * 255))
            border_color = QColor(0x58, 0xA6, 0xFF)
            painter.setBrush(bg_color)
            painter.setPen(QPen(border_color, 2))
        else:
            bg_color = QColor(22, 27, 34, int(0.3 * 255))
            border_color = QColor(0x30, 0x36, 0x3D)
            painter.setBrush(bg_color)
            painter.setPen(QPen(border_color, 2, Qt.DashLine))
        painter.drawRoundedRect(r, 20, 20)

        inner = self.findChild(QWidget, "dropZoneInner")
        if inner:
            ir = inner.geometry().adjusted(-1, -1, 1, 1)
            painter.setBrush(QColor(22, 27, 34, int(0.5 * 255)))
            painter.setPen(QPen(QColor(48, 54, 61, int(0.5 * 255)), 1))
            painter.drawRoundedRect(ir, 14, 14)

        painter.end()
