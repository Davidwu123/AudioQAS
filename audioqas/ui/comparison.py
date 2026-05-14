from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from audioqas.ui.theme import load_tokens, _val, _color, score_color, score_grade
from audioqas.core.dimensions import DimensionRegistry


class DeltaWidget(QFrame):
    def __init__(self, dim: str, score_a: float, score_b: float, parent=None):
        super().__init__(parent)
        self._dim = dim
        self._score_a = score_a
        self._score_b = score_b
        self._delta = score_b - score_a

        self.setFrameShape(QFrame.NoFrame)
        self.setFixedWidth(100)
        self.setMinimumHeight(120)

        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        txt_ter = _color(t, "text", "tertiary")
        txt_sec = _color(t, "text", "secondary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        dim_label = QLabel(dim)
        dim_label.setAlignment(Qt.AlignCenter)
        dim_label.setStyleSheet(f"font-size: 11px; color: {txt_ter}; letter-spacing: 0.5px")
        layout.addWidget(dim_label)

        delta = self._delta
        if abs(delta) < 0.01:
            delta_text = "0.00"
            delta_color = txt_sec
            arrow = "—"
        elif delta > 0:
            delta_text = f"+{delta:.2f}"
            delta_color = "#3fb950"
            arrow = "↑"
        else:
            delta_text = f"{delta:.2f}"
            delta_color = "#f85149"
            arrow = "↓"

        self._delta_label = QLabel(f"{delta_text} {arrow}")
        self._delta_label.setAlignment(Qt.AlignCenter)
        self._delta_label.setStyleSheet(f"font-family: {mono}; font-size: 22px; font-weight: 700; color: {delta_color}")
        layout.addWidget(self._delta_label)

        grade_a = score_grade(score_a)
        grade_b = score_grade(score_b)
        flow = f"{grade_a} → {grade_b}"
        self._flow_label = QLabel(flow)
        self._flow_label.setAlignment(Qt.AlignCenter)
        self._flow_label.setStyleSheet(f"font-size: 11px; color: {txt_ter}")
        layout.addWidget(self._flow_label)

        self._delta_color_hex = delta_color
        self._is_better = delta > 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        bg = QColor(22, 27, 34, int(0.4 * 255))
        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(QColor(48, 54, 61, int(0.4 * 255)), 1))
        painter.drawRoundedRect(r, 10, 10)

        if abs(self._delta) >= 0.01:
            accent = QColor(self._delta_color_hex)
            accent.setAlpha(int(0.15 * 255))
            painter.setBrush(QBrush(accent))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(r, 10, 10)

        painter.end()


class ComparisonWidget(QWidget):
    def __init__(self, result_a: dict, result_b: dict, parent=None):
        super().__init__(parent)
        self._result_a = result_a
        self._result_b = result_b

        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Header: file A info | VS | file B info
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        name_a = self._short_name(result_a['file_path'])
        name_b = self._short_name(result_b['file_path'])
        model = f"{result_a['model_name']} {result_a['model_version']}"

        tag_style = "font-size:12px;background:rgba(48,54,61,0.5);padding:3px 8px;border-radius:5px"

        left_info = QLabel(
            f'<span style="font-weight:600;color:{txt_primary}">A: {name_a}</span>'
            f'&nbsp;&nbsp;<span style="{tag_style};color:{txt_ter}">{result_a["original_sr"]}Hz · {result_a["duration"]:.1f}s</span>'
        )
        left_info.setStyleSheet("font-size: 14px")
        header_layout.addWidget(left_info)

        vs_label = QLabel("VS")
        vs_label.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {txt_ter}; letter-spacing: 2px")
        vs_label.setAlignment(Qt.AlignCenter)
        vs_label.setFixedWidth(40)
        header_layout.addWidget(vs_label)

        right_info = QLabel(
            f'<span style="font-weight:600;color:{txt_primary}">B: {name_b}</span>'
            f'&nbsp;&nbsp;<span style="{tag_style};color:{txt_ter}">{result_b["original_sr"]}Hz · {result_b["duration"]:.1f}s</span>'
        )
        right_info.setStyleSheet("font-size: 14px")
        header_layout.addWidget(right_info)

        header_layout.addStretch()
        model_label = QLabel(model)
        model_label.setStyleSheet(f"font-size: 12px; color: {txt_ter}; background: rgba(88,166,255,0.1); padding: 3px 8px; border-radius: 5px")
        header_layout.addWidget(model_label)

        layout.addWidget(header)

        # Summary verdict
        ovrl_a = result_a['dimensions'].get('OVRL', list(result_a['dimensions'].values())[0])['score']
        ovrl_b = result_b['dimensions'].get('OVRL', list(result_b['dimensions'].values())[0])['score']
        delta_ovrl = ovrl_b - ovrl_a

        if abs(delta_ovrl) < 0.01:
            verdict = "两者相当"
            verdict_color = txt_sec
        elif delta_ovrl > 0:
            verdict = f"B 领先 Δ={delta_ovrl:+.2f}"
            verdict_color = "#3fb950"
        else:
            verdict = f"A 领先 Δ={abs(delta_ovrl):.2f}"
            verdict_color = "#3fb950"

        verdict_label = QLabel(verdict)
        verdict_label.setAlignment(Qt.AlignCenter)
        verdict_label.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {verdict_color}; padding: 6px 0")
        layout.addWidget(verdict_label)

        # Dimension rows: card A | delta | card B
        from audioqas.ui.score_card import ScoreCardWidget

        model_id = result_a['model_name']
        dims = list(result_a['dimensions'].keys())
        for dim in dims:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            info_a = result_a['dimensions'][dim]
            info_b = result_b['dimensions'][dim]

            card_a = ScoreCardWidget(dim, model_id=model_id)
            dim_label = DimensionRegistry.dimension_label(model_id, dim)
            label_a = f"{dim} · {dim_label}"
            desc_a = DimensionRegistry.dimension_description(model_id, dim, info_a['grade'])
            if not desc_a:
                desc_a = info_a['description']
            card_a.set_score(info_a['score'], label_a, desc_a)
            row_layout.addWidget(card_a)

            delta_w = DeltaWidget(dim, info_a['score'], info_b['score'])
            row_layout.addWidget(delta_w)

            card_b = ScoreCardWidget(dim, model_id=model_id)
            label_b = f"{dim} · {dim_label}"
            desc_b = DimensionRegistry.dimension_description(model_id, dim, info_b['grade'])
            if not desc_b:
                desc_b = info_b['description']
            card_b.set_score(info_b['score'], label_b, desc_b)
            row_layout.addWidget(card_b)

            row_layout.addStretch()
            layout.addWidget(row)

        layout.addStretch()

    def _short_name(self, path: str) -> str:
        import os
        name = os.path.basename(path)
        if len(name) > 25:
            name = name[:22] + "..."
        return name
