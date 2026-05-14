import csv
import os
from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QLineEdit, QComboBox, QMessageBox, QFileDialog, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen

from audioqas.ui.theme import load_tokens, _color, score_color
from audioqas.core.history import HistoryManager


class EvalCard(QFrame):
    detail_requested = Signal(str)
    export_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, eval_data: dict, parent=None):
        super().__init__(parent)
        self._eval_id = eval_data["id"]
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(80)
        self.setCursor(Qt.ArrowCursor)

        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        hover_bg = _color(t, "interactive", "hover")
        border_def = _color(t, "border", "default")

        stats = eval_data["statistics"]
        ovrl_mean = stats.get("ovrl_mean", 0)
        ovrl_color = score_color(ovrl_mean)

        ts = eval_data["timestamp"]
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            time_str = ts

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {txt_primary}")
        top_row.addWidget(time_label)

        type_label = QLabel(eval_data["type"])
        type_label.setStyleSheet(f"font-size: 11px; padding: 1px 6px; border-radius: 4px; background: rgba(88,166,255,0.15); color: {_color(t, 'accent', 'primary')}")
        top_row.addWidget(type_label)

        model_label = QLabel(f"{eval_data['model']} {eval_data['model_version']}")
        model_label.setStyleSheet(f"font-size: 11px; padding: 1px 6px; border-radius: 4px; background: rgba(48,54,61,0.6); color: {txt_ter}")
        top_row.addWidget(model_label)
        top_row.addStretch()
        info_layout.addLayout(top_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        files_label = QLabel(f"{eval_data['files_count']} 文件")
        files_label.setStyleSheet(f"font-size: 13px; color: {txt_sec}")
        bottom_row.addWidget(files_label)

        ovrl_label = QLabel(f"OVRL {ovrl_mean:.2f}")
        ovrl_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {ovrl_color}")
        bottom_row.addWidget(ovrl_label)

        pt = eval_data["processing_time"]
        if pt >= 1000:
            time_text = f"{pt / 1000:.1f}s"
        else:
            time_text = f"{pt}ms"
        pt_label = QLabel(time_text)
        pt_label.setStyleSheet(f"font-size: 13px; color: {txt_ter}")
        bottom_row.addWidget(pt_label)
        bottom_row.addStretch()
        info_layout.addLayout(bottom_row)
        layout.addLayout(info_layout, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        detail_btn = QPushButton("查看详情")
        detail_btn.setStyleSheet(f"background: transparent; color: {_color(t, 'accent', 'primary')}; border: none; font-size: 12px; font-weight: 500")
        detail_btn.setCursor(Qt.PointingHandCursor)
        detail_btn.clicked.connect(lambda: self.detail_requested.emit(self._eval_id))
        btn_layout.addWidget(detail_btn)

        export_btn = QPushButton("导出CSV")
        export_btn.setStyleSheet(f"background: transparent; color: {txt_sec}; border: 1px solid {border_def}; border-radius: 6px; padding: 4px 10px; font-size: 12px")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(lambda: self.export_requested.emit(self._eval_id))
        btn_layout.addWidget(export_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet(f"background: transparent; color: #F85149; border: none; font-size: 12px")
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._eval_id))
        btn_layout.addWidget(delete_btn)

        layout.addLayout(btn_layout)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(22, 27, 34, int(0.65 * 255)))
        painter.setPen(QPen(QColor(48, 54, 61, int(0.6 * 255)), 1))
        painter.drawRoundedRect(r, 10, 10)
        highlight = QPen(QColor(139, 148, 158, int(0.15 * 255)), 1)
        painter.setPen(highlight)
        painter.drawLine(r.left() + 10, r.top(), r.right() - 10, r.top())
        painter.end()


class HistoryPageWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mgr = HistoryManager()

        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")
        border_def = _color(t, "border", "default")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("历史记录")
        header.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {txt_primary}")
        layout.addWidget(header)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索文件名...")
        self._search.setStyleSheet(f"background: {_color(t, 'base', 'elevated')}; color: {txt_primary}; border: 1px solid {border_def}; border-radius: 8px; padding: 8px 12px; font-size: 13px")
        self._search.textChanged.connect(self._refresh)
        filter_row.addWidget(self._search)

        self._grade_filter = QComboBox()
        self._grade_filter.addItem("全部等级", "")
        for grade in ["Excellent", "Good", "Fair", "Poor", "Bad"]:
            self._grade_filter.addItem(grade, grade)
        self._grade_filter.setStyleSheet(f"background: {_color(t, 'base', 'elevated')}; color: {txt_primary}; border: 1px solid {border_def}; border-radius: 8px; padding: 8px 12px; font-size: 13px; min-width: 120px")
        self._grade_filter.currentIndexChanged.connect(self._refresh)
        filter_row.addWidget(self._grade_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()
        self._scroll.setWidget(self._cards_container)
        layout.addWidget(self._scroll, 1)

        self._empty_label = QLabel("暂无历史记录")
        self._empty_label.setStyleSheet(f"font-size: 16px; color: {txt_ter}; background: transparent")
        self._empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._empty_label, 1)
        self._empty_label.setVisible(True)
        self._scroll.setVisible(False)

        delete_all_btn = QPushButton("删除全部")
        delete_all_btn.setStyleSheet("background: transparent; color: #F85149; border: 1px solid #F85149; border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 500")
        delete_all_btn.setCursor(Qt.PointingHandCursor)
        delete_all_btn.clicked.connect(self._delete_all)
        layout.addWidget(delete_all_btn, 0, Qt.AlignRight)

        self._refresh()

    def _refresh(self):
        evals = self._mgr.get_all_evaluations()
        search_text = self._search.text().strip().lower()
        grade_filter = self._grade_filter.currentData()

        filtered = []
        for e in evals:
            if search_text:
                detail = self._mgr.get_evaluation_detail(e["id"])
                names = [f["filename"].lower() for f in detail]
                if not any(search_text in n for n in names):
                    continue
            if grade_filter:
                ovrl_mean = e["statistics"].get("ovrl_mean", 0)
                from audioqas.ui.theme import score_grade as _sg
                if _sg(ovrl_mean) != grade_filter:
                    continue
            filtered.append(e)

        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        has_data = len(filtered) > 0
        self._empty_label.setVisible(not has_data)
        self._scroll.setVisible(has_data)

        for e in filtered:
            card = EvalCard(e)
            card.detail_requested.connect(self._show_detail)
            card.export_requested.connect(self._export_csv)
            card.delete_requested.connect(self._delete_eval)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _show_detail(self, eval_id):
        detail = self._mgr.get_evaluation_detail(eval_id)
        if not detail:
            return
        lines = []
        for f in detail:
            ovrl_color = score_color(f["ovrl_score"])
            lines.append(
                f'<span style="font-weight:600">{f["filename"]}</span> '
                f'&nbsp; <span style="color:{ovrl_color};font-weight:600">OVRL {f["ovrl_score"]:.2f}</span> '
                f'&nbsp; <span style="color:#8B949E">SIG {f["sig_score"]:.2f}</span> '
                f'&nbsp; <span style="color:#8B949E">BAK {f["bak_score"]:.2f}</span>'
            )
        QMessageBox.information(self, "评测详情", "\n".join(lines))

    def _export_csv(self, eval_id):
        detail = self._mgr.get_evaluation_detail(eval_id)
        if not detail:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出CSV", f"eval_{eval_id}.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["文件名", "时长(s)", "OVRL分数", "OVRL等级", "SIG分数", "SIG等级", "BAK分数", "BAK等级"])
            for d in detail:
                writer.writerow([
                    d["filename"], f"{d['duration']:.1f}",
                    f"{d['ovrl_score']:.2f}", d["ovrl_grade"],
                    f"{d['sig_score']:.2f}", d["sig_grade"],
                    f"{d['bak_score']:.2f}", d["bak_grade"],
                ])
        QMessageBox.information(self, "导出成功", f"已导出 {len(detail)} 条到 {path}")

    def _delete_eval(self, eval_id):
        self._mgr.delete_evaluation(eval_id)
        self._refresh()

    def _delete_all(self):
        reply = QMessageBox.question(self, "删除全部", "确定删除所有历史记录？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mgr.delete_all()
            self._refresh()