from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QToolTip
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen

from audioqas.ui.theme import load_tokens, _val, _color


MODELS = [
    {"id": "dnsmos", "name": "DNSMOS", "tag": "3维·16k", "version": "DNSMOS v8"},
    {"id": "nisqa",  "name": "NISQA",  "tag": "5维·48k", "version": "NISQA v2"},
]

ANALYSIS_MODELS = [
    {"id": "audiobox-aesthetics", "name": "AudioBox Aesthetics", "tag": "4维·1-10", "version": "AudioBox-Aesthetics v1"},
]

PAGE_DEFS = {
    "eval": {
        "label": "纯人声评测",
        "hint": "适用于通话、口播、会议、纯人声录音",
    },
    "analysis": {
        "label": "综合音频分析",
        "hint": "适用于人声+音乐、视频音轨、节目成品与混合内容",
    },
    "history": {
        "label": "历史",
        "hint": "查看历史评测与分析结果",
    },
    "settings": {
        "label": "设置",
        "hint": "调整模型、预处理和运行配置",
    },
}


class ModelDotWidget(QWidget):
    def __init__(self, selected: bool = False, parent=None):
        super().__init__(parent)
        self._selected = selected
        self.setFixedSize(10, 10)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._selected:
            painter.setBrush(QColor(0x58, 0xA6, 0xFF))
            painter.setPen(QPen(QColor(0x58, 0xA6, 0xFF), 2))
            painter.drawEllipse(1, 1, 8, 8)
        else:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(0x48, 0x4F, 0x58), 2))
            painter.drawEllipse(1, 1, 8, 8)
        painter.end()


class ModelItemWidget(QWidget):
    clicked = Signal(str)

    def __init__(self, model: dict, selected: bool = False, parent=None):
        super().__init__(parent)
        self._model = model
        self._selected = selected
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self._dot = ModelDotWidget(selected)
        layout.addWidget(self._dot)

        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")

        name_color = accent if selected else txt_sec
        self._name = QLabel(model["name"])
        self._name.setStyleSheet(f"font-size: 13px; color: {name_color}; font-weight: 500")
        layout.addWidget(self._name)

        tag_bg = "rgba(88,166,255,0.15)" if selected else "rgba(48,54,61,0.6)"
        tag_color = accent if selected else txt_ter
        self._tag = QLabel(model["tag"])
        self._tag.setStyleSheet(f"font-size: 10px; padding: 1px 4px; border-radius: 3px; background: {tag_bg}; color: {tag_color}")
        layout.addWidget(self._tag)
        layout.addStretch()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._dot.set_selected(selected)
        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        name_color = accent if selected else txt_sec
        self._name.setStyleSheet(f"font-size: 13px; color: {name_color}; font-weight: 500")
        tag_bg = "rgba(88,166,255,0.15)" if selected else "rgba(48,54,61,0.6)"
        tag_color = accent if selected else txt_ter
        self._tag.setStyleSheet(f"font-size: 10px; padding: 1px 4px; border-radius: 3px; background: {tag_bg}; color: {tag_color}")
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit(self._model["id"])
        super().mousePressEvent(event)

    def enterEvent(self, event):
        bg = "rgba(88,166,255,0.1)" if self._selected else "rgba(48,54,61,0.4)"
        self.setStyleSheet(f"background: {bg}; border-radius: 6px;")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("")
        super().leaveEvent(event)


class SidebarWidget(QWidget):
    model_changed = Signal(str)
    page_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self._active_page = "analysis"  # default to audio analysis

        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        txt_inv = _color(t, "text", "inverse")
        accent_ter = _color(t, "accent", "tertiary")
        border_muted = _color(t, "border", "muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(16, 24, 16, 16)
        logo_layout.setSpacing(8)

        logo_icon = QLabel("M")
        logo_icon.setFixedSize(28, 28)
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setStyleSheet(f"background: {accent}; border-radius: 8px; font-size: 14px; font-weight: 700; color: {txt_inv}")
        logo_layout.addWidget(logo_icon)

        logo_text = QLabel("AudioQAS")
        logo_text.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {accent}")
        logo_layout.addWidget(logo_text)
        layout.addLayout(logo_layout)

        # Navigation
        self._nav_items = []
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(0)
        pages = ["eval", "analysis", "history", "settings"]
        for page_id in pages:
            item = QLabel(PAGE_DEFS[page_id]["label"])
            item.setFixedHeight(44)
            item.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            item.setContentsMargins(16, 0, 16, 0)
            item.setCursor(Qt.PointingHandCursor)
            item.setStyleSheet(f"font-size: 15px; font-weight: 500; color: {txt_sec}; border-radius: 6px;")
            item.setProperty("page_id", page_id)
            item.mousePressEvent = lambda e, pid=page_id: self.page_changed.emit(pid)
            item.enterEvent = lambda e, w=item, pid=page_id: self._show_nav_hint(w, pid, e)
            item.leaveEvent = lambda e, w=item, pid=page_id: self._hide_nav_hint(w, pid, e)
            nav_layout.addWidget(item)
            self._nav_items.append(item)
        layout.addLayout(nav_layout)

        # Default to analysis page (index 1)
        self._set_nav_active(1)

        # ---- Voice models section (shown only on eval page) ----
        self._voice_section = QWidget()
        voice_layout = QVBoxLayout(self._voice_section)
        voice_layout.setContentsMargins(0, 0, 0, 0)
        voice_layout.setSpacing(0)

        models_sep = QLabel()
        models_sep.setFixedHeight(1)
        models_sep.setStyleSheet(f"background: {border_muted}")
        voice_layout.addWidget(models_sep)

        models_inner = QVBoxLayout()
        models_inner.setContentsMargins(16, 8, 16, 8)
        models_inner.setSpacing(0)

        models_title = QLabel("人声模型")
        models_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {txt_ter}; letter-spacing: 1px")
        models_inner.addWidget(models_title)
        models_inner.addSpacing(8)

        self._model_items = []
        for i, model in enumerate(MODELS):
            selected = (i == 0)
            item = ModelItemWidget(model, selected)
            item.clicked.connect(self._on_model_click)
            models_inner.addWidget(item)
            self._model_items.append(item)

        voice_layout.addLayout(models_inner)
        layout.addWidget(self._voice_section)

        # ---- Audio analysis models section (shown only on analysis page) ----
        self._analysis_section = QWidget()
        analysis_layout = QVBoxLayout(self._analysis_section)
        analysis_layout.setContentsMargins(0, 0, 0, 0)
        analysis_layout.setSpacing(0)

        analysis_sep = QLabel()
        analysis_sep.setFixedHeight(1)
        analysis_sep.setStyleSheet(f"background: {border_muted}")
        analysis_layout.addWidget(analysis_sep)

        analysis_inner = QVBoxLayout()
        analysis_inner.setContentsMargins(16, 8, 16, 8)
        analysis_inner.setSpacing(0)

        analysis_title = QLabel("综合音频模型")
        analysis_title.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {txt_ter}; letter-spacing: 1px")
        analysis_inner.addWidget(analysis_title)
        analysis_inner.addSpacing(8)

        self._analysis_model_items = []
        for i, model in enumerate(ANALYSIS_MODELS):
            selected = (i == 0)
            item = ModelItemWidget(model, selected)
            item.clicked.connect(self._on_analysis_model_click)
            analysis_inner.addWidget(item)
            self._analysis_model_items.append(item)

        analysis_layout.addLayout(analysis_inner)
        layout.addWidget(self._analysis_section)

        layout.addStretch()

        # Status bar
        status_sep = QLabel()
        status_sep.setFixedHeight(1)
        status_sep.setStyleSheet(f"background: {border_muted}")
        layout.addWidget(status_sep)

        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(16, 12, 16, 12)

        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"color: {accent_ter}; font-size: 11px")
        status_layout.addWidget(status_dot)

        self._status_label = QLabel(f"就绪 · {ANALYSIS_MODELS[0]['version']}")
        self._status_label.setStyleSheet(f"font-size: 11px; color: {txt_ter}")
        status_layout.addWidget(self._status_label)
        layout.addLayout(status_layout)

        self._current_model_id = "dnsmos"
        self._current_analysis_model_id = "audiobox-aesthetics"

        # Initial visibility: show analysis models, hide voice models
        self._update_model_visibility()

    def _update_model_visibility(self):
        if self._active_page == "eval":
            self._voice_section.setVisible(True)
            self._analysis_section.setVisible(False)
            version = next(m["version"] for m in MODELS if m["id"] == self._current_model_id)
            self._status_label.setText(f"就绪 · {version}")
        elif self._active_page == "analysis":
            self._voice_section.setVisible(False)
            self._analysis_section.setVisible(True)
            version = next(m["version"] for m in ANALYSIS_MODELS if m["id"] == self._current_analysis_model_id)
            self._status_label.setText(f"就绪 · {version}")
        else:
            # History/Settings: show nothing
            self._voice_section.setVisible(False)
            self._analysis_section.setVisible(False)

    def _set_nav_active(self, index):
        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_sec = _color(t, "text", "secondary")
        for i, item in enumerate(self._nav_items):
            page_id = item.property("page_id")
            active = i == index
            hovered = page_id != self._active_page and item.underMouse()
            self._apply_nav_item_style(item, active, hovered, accent, txt_sec)

    def _on_model_click(self, model_id):
        if model_id == self._current_model_id:
            return
        self._current_model_id = model_id
        for item in self._model_items:
            item.set_selected(item._model["id"] == model_id)
        version = next(m["version"] for m in MODELS if m["id"] == model_id)
        self._status_label.setText(f"就绪 · {version}")
        self.model_changed.emit(model_id)

    def _on_analysis_model_click(self, model_id):
        if model_id == self._current_analysis_model_id:
            return
        self._current_analysis_model_id = model_id
        for item in self._analysis_model_items:
            item.set_selected(item._model["id"] == model_id)
        version = next(m["version"] for m in ANALYSIS_MODELS if m["id"] == model_id)
        self._status_label.setText(f"就绪 · {version}")
        self.model_changed.emit(model_id)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg = QColor(13, 17, 23, int(0.85 * 255))
        painter.fillRect(self.rect(), bg)
        painter.setPen(QPen(QColor(0x21, 0x26, 0x2D), 1))
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        painter.end()

    def set_active_page(self, page_id):
        self._active_page = page_id
        pages = ["eval", "analysis", "history", "settings"]
        idx = pages.index(page_id) if page_id in pages else 1
        self._set_nav_active(idx)
        self._update_model_visibility()

    def current_model(self):
        return self._current_model_id

    def _show_nav_hint(self, widget, page_id, event):
        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_sec = _color(t, "text", "secondary")
        self._apply_nav_item_style(widget, page_id == self._active_page, True, accent, txt_sec)
        hint = PAGE_DEFS.get(page_id, {}).get("hint", "")
        if hint:
            pos = widget.mapToGlobal(widget.rect().topRight())
            QToolTip.showText(pos, hint, widget)

    def _hide_nav_hint(self, widget, page_id, event):
        QToolTip.hideText()
        t = load_tokens()
        accent = _color(t, "accent", "primary")
        txt_sec = _color(t, "text", "secondary")
        self._apply_nav_item_style(widget, page_id == self._active_page, False, accent, txt_sec)

    def _apply_nav_item_style(self, item, active: bool, hovered: bool, accent: str, txt_sec: str):
        if active:
            item.setStyleSheet(
                f"font-size: 15px; font-weight: 500; color: {accent}; "
                "background: rgba(88,166,255,0.15); border-radius: 6px; padding-left: 16px;"
            )
            return
        bg = "rgba(48,54,61,0.4)" if hovered else "transparent"
        item.setStyleSheet(
            f"font-size: 15px; font-weight: 500; color: {txt_sec}; "
            f"background: {bg}; border-radius: 6px; padding-left: 16px;"
        )
