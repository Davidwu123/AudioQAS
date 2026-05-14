import json
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit, QFileDialog, QFrame, QScrollArea
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen

from audioqas.ui.theme import load_tokens, _color

SETTINGS_PATH = Path.home() / "Library" / "Preferences" / "AudioQAS" / "settings.json"

DEFAULT_SETTINGS = {
    "theme": "dark",
    "export_dir": "",
    "scoring_mode": "DNSMOS",
    "segment_window": 10,
    "min_duration_warning": 3.0,
    "plain_description": True,
    "resample_target": 16000,
    "auto_mono": True,
    "video_extract_audio": True,
    "onnx_runtime": "CPU",
    "concurrency": 4,
    "cache_model": False,
}


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, initial: bool = False, parent=None):
        super().__init__(parent)
        self._on = initial
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._anim_x = 24 if initial else 4

    def set_on(self, on: bool):
        self._on = on
        self._anim_x = 24 if on else 4
        self.update()

    def is_on(self) -> bool:
        return self._on

    def mousePressEvent(self, event):
        self._on = not self._on
        self.toggled.emit(self._on)
        self._anim_x = 24 if self._on else 4
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = QColor(0x1F, 0x6F, 0xEB) if self._on else QColor(0x30, 0x36, 0x3D)
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 44, 24, 12, 12)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(self._anim_x, 2, 20, 20)
        painter.end()


class SettingsSection(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)

        t = load_tokens()
        txt_ter = _color(t, "text", "tertiary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header = QLabel(title.upper())
        header.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {txt_ter}; letter-spacing: 1px")
        layout.addWidget(header)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(10)
        layout.addLayout(self._rows_layout)

    def add_row(self, label: str, widget):
        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")
        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 14px; color: {txt_sec}")
        lbl.setFixedWidth(140)
        row.addWidget(lbl)
        if isinstance(widget, QWidget):
            row.addWidget(widget, 1)
        else:
            row.addLayout(widget, 1)
        self._rows_layout.addLayout(row)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(22, 27, 34, int(0.65 * 255)))
        painter.setPen(QPen(QColor(48, 54, 61, int(0.6 * 255)), 1))
        painter.drawRoundedRect(r, 12, 12)
        highlight = QPen(QColor(139, 148, 158, int(0.15 * 255)), 1)
        painter.setPen(highlight)
        painter.drawLine(r.left() + 12, r.top(), r.right() - 12, r.top())
        painter.end()


def _load_settings() -> dict:
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, "r") as f:
            saved = json.load(f)
        return {**DEFAULT_SETTINGS, **saved}
    return dict(DEFAULT_SETTINGS)


def _save_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


class SettingsPageWidget(QWidget):
    setting_changed = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = _load_settings()

        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        border_def = _color(t, "border", "default")
        elevated = _color(t, "base", "elevated")
        hover = _color(t, "interactive", "hover")

        combo_style = f"background: {elevated}; color: {txt_primary}; border: 1px solid {border_def}; border-radius: 8px; padding: 8px 12px; font-size: 13px"
        input_style = f"background: {elevated}; color: {txt_primary}; border: 1px solid {border_def}; border-radius: 8px; padding: 8px 12px; font-size: 13px"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("设置")
        header.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {txt_primary}")
        layout.addWidget(header)

        scroll_inner = QWidget()
        scroll_layout = QVBoxLayout(scroll_inner)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # General
        general = SettingsSection("通用")
        theme_combo = QComboBox()
        theme_combo.addItem("深色", "dark")
        theme_combo.setStyleSheet(combo_style)
        theme_combo.currentIndexChanged.connect(lambda i: self._update("theme", theme_combo.currentData()))
        general.add_row("主题选择", theme_combo)

        export_dir_layout = QHBoxLayout()
        self._export_dir_input = QLineEdit(self._settings.get("export_dir", ""))
        self._export_dir_input.setPlaceholderText("选择默认导出目录...")
        self._export_dir_input.setStyleSheet(input_style)
        self._export_dir_input.textChanged.connect(lambda v: self._update("export_dir", v))
        export_dir_layout.addWidget(self._export_dir_input, 1)
        dir_btn = QPushButton("选择")
        dir_btn.setStyleSheet(f"background: {hover}; color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-size: 13px")
        dir_btn.setCursor(Qt.PointingHandCursor)
        dir_btn.clicked.connect(self._pick_export_dir)
        export_dir_layout.addWidget(dir_btn)
        general.add_row("默认导出目录", export_dir_layout)
        scroll_layout.addWidget(general)

        # Scoring
        scoring = SettingsSection("评分")
        mode_combo = QComboBox()
        mode_combo.addItem("DNSMOS", "DNSMOS")
        mode_combo.addItem("NISQA", "NISQA")
        mode_combo.setStyleSheet(combo_style)
        idx = mode_combo.findData(self._settings["scoring_mode"])
        if idx >= 0:
            mode_combo.setCurrentIndex(idx)
        mode_combo.currentIndexChanged.connect(lambda i: self._update("scoring_mode", mode_combo.currentData()))
        scoring.add_row("评分模式", mode_combo)

        seg_combo = QComboBox()
        for v in [10, 5, 15]:
            seg_combo.addItem(f"{v}s", v)
        seg_combo.setStyleSheet(combo_style)
        idx = seg_combo.findData(self._settings["segment_window"])
        if idx >= 0:
            seg_combo.setCurrentIndex(idx)
        seg_combo.currentIndexChanged.connect(lambda i: self._update("segment_window", seg_combo.currentData()))
        scoring.add_row("分段窗口", seg_combo)

        min_dur = QLineEdit(str(self._settings["min_duration_warning"]))
        min_dur.setStyleSheet(f"{input_style}; max-width: 80px")
        min_dur.textChanged.connect(lambda v: self._update("min_duration_warning", float(v) if v else 3.0))
        scoring.add_row("最短时长警告(秒)", min_dur)

        plain_toggle = ToggleSwitch(self._settings["plain_description"])
        plain_toggle.toggled.connect(lambda v: self._update("plain_description", v))
        scoring.add_row("通俗描述", plain_toggle)
        scroll_layout.addWidget(scoring)

        # Preprocessing
        preprocess = SettingsSection("预处理")
        sr_combo = QComboBox()
        sr_combo.addItem("16000Hz", 16000)
        sr_combo.addItem("48000Hz", 48000)
        sr_combo.setStyleSheet(combo_style)
        idx = sr_combo.findData(self._settings["resample_target"])
        if idx >= 0:
            sr_combo.setCurrentIndex(idx)
        sr_combo.currentIndexChanged.connect(lambda i: self._update("resample_target", sr_combo.currentData()))
        preprocess.add_row("重采样目标", sr_combo)

        mono_toggle = ToggleSwitch(self._settings["auto_mono"])
        mono_toggle.toggled.connect(lambda v: self._update("auto_mono", v))
        preprocess.add_row("自动转单声道", mono_toggle)

        video_toggle = ToggleSwitch(self._settings["video_extract_audio"])
        video_toggle.toggled.connect(lambda v: self._update("video_extract_audio", v))
        preprocess.add_row("视频提取音轨", video_toggle)
        scroll_layout.addWidget(preprocess)

        # Advanced
        advanced = SettingsSection("高级")
        runtime_combo = QComboBox()
        runtime_combo.addItem("CPU", "CPU")
        runtime_combo.addItem("GPU Metal", "GPU_Metal")
        runtime_combo.setStyleSheet(combo_style)
        idx = runtime_combo.findData(self._settings["onnx_runtime"])
        if idx >= 0:
            runtime_combo.setCurrentIndex(idx)
        runtime_combo.currentIndexChanged.connect(lambda i: self._update("onnx_runtime", runtime_combo.currentData()))
        advanced.add_row("ONNX Runtime", runtime_combo)

        conc_input = QLineEdit(str(self._settings["concurrency"]))
        conc_input.setStyleSheet(f"{input_style}; max-width: 80px")
        conc_input.textChanged.connect(lambda v: self._update("concurrency", int(v) if v else 4))
        advanced.add_row("并发数", conc_input)

        cache_toggle = ToggleSwitch(self._settings["cache_model"])
        cache_toggle.toggled.connect(lambda v: self._update("cache_model", v))
        advanced.add_row("缓存模型", cache_toggle)
        scroll_layout.addWidget(advanced)

        # About
        about = SettingsSection("关于")
        about_label = QLabel("AudioQAS v1.0.0 · DNSMOS v1.0")
        about_label.setStyleSheet(f"font-size: 14px; color: {txt_sec}")
        about._rows_layout.addWidget(about_label)
        scroll_layout.addWidget(about)

        scroll_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setWidget(scroll_inner)
        layout.addWidget(scroll, 1)

    def _update(self, key: str, value):
        self._settings[key] = value
        _save_settings(self._settings)
        self.setting_changed.emit(key, value)

    def _pick_export_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if dir_path:
            self._export_dir_input.setText(dir_path)

    def get_settings(self) -> dict:
        return self._settings