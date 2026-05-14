import os
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableView, QAbstractItemView, QHeaderView, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics

from audioqas.ui.theme import load_tokens, _color, _val, score_color, score_grade
from audioqas.ui.stats import StatsWidget

VIDEO_EXTS = {'.mp4', '.mkv', '.avi'}

GRADE_ORDER = ["Bad", "Poor", "Fair", "Good", "Excellent"]
GRADE_COLORS = {
    "Bad": "#F85149",
    "Poor": "#D29922",
    "Fair": "#E3B341",
    "Good": "#3FB950",
    "Excellent": "#2EA043",
}


class DistributionBarWidget(QWidget):
    """Colored bars showing grade distribution for one dimension."""

    def __init__(self, grade_counts: dict[str, int], total: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self._grade_counts = grade_counts
        self._total = total

    def paintEvent(self, event):
        if self._total == 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        t = load_tokens()
        overlay = _color(t, "base", "overlay")
        bar_w = self.width()
        bar_h = self.height()

        painter.setBrush(QColor(overlay))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, bar_w, bar_h, 4, 4)

        x = 0
        for grade in GRADE_ORDER:
            count = self._grade_counts.get(grade, 0)
            if count == 0:
                continue
            seg_w = int(bar_w * count / self._total)
            color = QColor(GRADE_COLORS[grade])
            painter.setBrush(color)
            painter.drawRoundedRect(x, 0, max(seg_w, 1), bar_h, 4, 4)
            x += seg_w

        painter.end()


class DistributionRowWidget(QWidget):
    """Row showing distribution bars + grade labels for all 3 dimensions."""

    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        total = len(results)

        for dim in ["OVRL", "SIG", "BAK"]:
            dim_layout = QHBoxLayout()
            dim_layout.setContentsMargins(0, 0, 0, 0)
            dim_layout.setSpacing(8)

            dim_label = QLabel(dim)
            dim_label.setFixedWidth(40)
            dim_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {txt_sec}")
            dim_layout.addWidget(dim_label)

            grade_counts = {}
            for r in results:
                g = r["dimensions"][dim]["grade"]
                grade_counts[g] = grade_counts.get(g, 0) + 1

            bar = DistributionBarWidget(grade_counts, total)
            dim_layout.addWidget(bar, 1)

            for grade in GRADE_ORDER:
                count = grade_counts.get(grade, 0)
                g_label = QLabel(f"{count}")
                g_label.setFixedWidth(20)
                g_label.setAlignment(Qt.AlignCenter)
                g_color = GRADE_COLORS[grade]
                g_label.setStyleSheet(
                    f"font-size: 11px; color: {g_color if count > 0 else txt_ter}; font-weight: 500"
                )
                dim_layout.addWidget(g_label)

            layout.addLayout(dim_layout)

        # Grade legend
        legend_layout = QHBoxLayout()
        legend_layout.setContentsMargins(40, 2, 0, 0)
        legend_layout.setSpacing(16)
        for grade in GRADE_ORDER:
            g_color = GRADE_COLORS[grade]
            lbl = QLabel(grade)
            lbl.setStyleSheet(f"font-size: 10px; color: {g_color}; font-weight: 500")
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        layout.addLayout(legend_layout)


class BatchTableModel(QAbstractTableModel):
    """Model for the batch result table."""

    COLUMNS = ["文件名", "时长", "OVRL", "SIG", "BAK", "等级", "状态"]

    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        self._results = results

    def rowCount(self, parent=QModelIndex()):
        return len(self._results)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._results):
            return None

        r = self._results[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                name = os.path.basename(r["file_path"])
                ext = os.path.splitext(r["file_path"])[1].lower()
                if ext in VIDEO_EXTS:
                    name = f"\U0001F3B9 {name}"
                return name
            elif col == 1:
                return f"{r['duration']:.1f}s"
            elif col == 2:
                return f"{r['dimensions']['OVRL']['score']:.2f}"
            elif col == 3:
                return f"{r['dimensions']['SIG']['score']:.2f}"
            elif col == 4:
                return f"{r['dimensions']['BAK']['score']:.2f}"
            elif col == 5:
                return r["grade"]
            elif col == 6:
                return "完成"
            return None

        if role == Qt.UserRole:
            return r

        if role == Qt.ToolTipRole:
            if col in (2, 3, 4):
                dim = ["OVRL", "SIG", "BAK"][col - 2]
                d = r["dimensions"][dim]
                return f"{dim}: {d['score']:.2f} ({d['grade']} - {d['description']})"
            return None

        if role == Qt.ForegroundRole:
            if col in (2, 3, 4):
                dim = ["OVRL", "SIG", "BAK"][col - 2]
                score = r["dimensions"][dim]["score"]
                color = score_color(score)
                return QColor(color)
            if col == 5:
                grade = r["grade"]
                return QColor(GRADE_COLORS.get(grade, "#8B949E"))
            return None

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignLeft | Qt.AlignVCenter
            return Qt.AlignCenter | Qt.AlignVCenter

        return None


class ScoreDescriptionDelegate(QStyledItemDelegate):
    """Custom delegate: score value in color + small description below."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        col = index.column()
        if col not in (2, 3, 4):
            super().paint(painter, option, index)
            return

        painter.save()

        result = index.data(Qt.UserRole)
        dim = ["OVRL", "SIG", "BAK"][col - 2]
        d = result["dimensions"][dim]
        score_val = d["score"]
        desc = d["description"]

        score_color_hex = score_color(score_val)
        score_qcolor = QColor(score_color_hex)

        # Background
        bg = option.rect
        if option.state & QStyle.State_Selected:
            painter.fillRect(bg, QColor(88, 166, 255, int(0.08 * 255)))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(bg, QColor(88, 166, 255, int(0.08 * 255)))

        # Score number
        t = load_tokens()
        mono = _val(t["typography"]["fontFamily"]["monospace"])
        score_font = QFont(mono.replace("'", "").split(",")[0].strip(), 13, QFont.Bold)
        painter.setFont(score_font)
        painter.setPen(score_qcolor)
        score_text = f"{score_val:.2f}"
        fm = QFontMetrics(score_font)
        score_rect = fm.boundingRect(score_text)
        x = bg.x() + (bg.width() - score_rect.width()) // 2
        y = bg.y() + bg.height() // 2 - 8
        painter.drawText(x, y + score_rect.height(), score_text)

        # Description
        desc_font = QFont(mono.replace("'", "").split(",")[0].strip(), 9)
        painter.setFont(desc_font)
        txt_sec = _color(t, "text", "secondary")
        painter.setPen(QColor(txt_sec))
        desc_fm = QFontMetrics(desc_font)
        desc_rect = desc_fm.boundingRect(desc)
        dx = bg.x() + (bg.width() - desc_rect.width()) // 2
        dy = y + score_rect.height() + 2
        painter.drawText(dx, dy + desc_rect.height(), desc)

        painter.restore()

    def sizeHint(self, option, index):
        col = index.column()
        if col not in (2, 3, 4):
            return super().sizeHint(option, index)
        base = super().sizeHint(option, index)
        return base.grownBy(QMargins(0, 8, 0, 8))


class BatchResultWidget(QWidget):
    """Full batch view: stats + distribution bars + table."""

    row_clicked = Signal(dict)

    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        self._results = results
        self._setup_ui()

    def _setup_ui(self):
        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")
        surface = _color(t, "base", "surface")
        elevated = _color(t, "base", "elevated")
        overlay = _color(t, "base", "overlay")
        border_muted = _color(t, "border", "muted")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Stats row
        self._stats_widget = StatsWidget(self._results)
        layout.addWidget(self._stats_widget)

        # Distribution bars
        self._dist_widget = DistributionRowWidget(self._results)
        layout.addWidget(self._dist_widget)

        # Table
        self._model = BatchTableModel(self._results)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setMouseTracking(True)

        # Delegate for score columns
        delegate = ScoreDescriptionDelegate(self._table)
        for col in (2, 3, 4):
            self._table.setItemDelegateForColumn(col, delegate)

        # Header styling
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"""
            QHeaderView::section {{
                background: {surface};
                color: {txt_sec};
                font-size: 13px;
                font-weight: 600;
                letter-spacing: 0.5px;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid {border_muted};
            }}
        """)

        # Column widths
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 60)
        for col in (2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.Fixed)
            header.resizeSection(col, 90)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.resizeSection(5, 80)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.resizeSection(6, 60)

        # Row height
        self._table.verticalHeader().setDefaultSectionSize(52)

        # Table styling
        self._table.setStyleSheet(f"""
            QTableView {{
                background: {surface};
                alternate-background-color: {elevated};
                color: {txt_sec};
                border: 1px solid {overlay};
                border-radius: 10px;
                font-size: 13px;
                selection-background-color: rgba(88,166,255,0.08);
                outline: none;
            }}
            QTableView::item {{
                padding: 4px 8px;
                border: none;
            }}
            QTableView::item:hover {{
                background: rgba(88,166,255,0.08);
            }}
        """)

        self._table.clicked.connect(self._on_table_click)
        layout.addWidget(self._table)

    def _on_table_click(self, index: QModelIndex):
        result = self._model.data(index, Qt.UserRole)
        if result:
            self.row_clicked.emit(result)

    def update_results(self, results: list[dict]):
        """Refresh all sub-widgets with new results."""
        self._results = results
        self._model = BatchTableModel(results)
        self._table.setModel(self._model)

        # Re-apply delegate
        delegate = ScoreDescriptionDelegate(self._table)
        for col in (2, 3, 4):
            self._table.setItemDelegateForColumn(col, delegate)

        self._stats_widget.update_stats(results)

        # Refresh distribution
        old_dist = self._dist_widget
        self.layout().removeWidget(old_dist)
        old_dist.deleteLater()
        self._dist_widget = DistributionRowWidget(results)
        self.layout().insertWidget(1, self._dist_widget)