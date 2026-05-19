from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from audioqas.ui.theme import load_tokens, _color


class PageIntroWidget(QFrame):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("glassPanel")

        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_sec = _color(t, "text", "secondary")
        accent = _color(t, "accent", "primary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"font-size: 18px; font-weight: 600; color: {txt_primary}"
        )
        layout.addWidget(self._title)

        self._subtitle = QLabel(subtitle)
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet(
            f"font-size: 13px; color: {txt_sec}; line-height: 1.5"
        )
        layout.addWidget(self._subtitle)

        self._accent = QLabel("")
        self._accent.setStyleSheet(f"color: {accent}; font-size: 1px")
        self._accent.setFixedHeight(0)
        layout.addWidget(self._accent)

    def set_content(self, title: str, subtitle: str):
        self._title.setText(title)
        self._subtitle.setText(subtitle)
