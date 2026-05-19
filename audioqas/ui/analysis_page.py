import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Signal

from audioqas.ui.theme import load_tokens, _color
from audioqas.ui.toolbar import EvalToolbarWidget
from audioqas.ui.drop_zone import DropZoneWidget
from audioqas.ui.score_card import ScoreCardWidget
from audioqas.ui.metric_card import MetricCardWidget
from audioqas.ui.page_intro import PageIntroWidget
from audioqas.models.analysis import METRIC_LABELS, METRIC_DESCRIPTIONS


class AnalysisPageWidget(QWidget):
    add_file = Signal()
    compare = Signal()
    export = Signal()
    reset = Signal()
    files_dropped = Signal(list)
    cmp_file_a_selected = Signal(str)
    cmp_file_b_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")
        txt_ter = _color(t, "text", "tertiary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Shared toolbar
        self._toolbar = EvalToolbarWidget()
        self._toolbar.add_file.connect(self.add_file.emit)
        self._toolbar.compare.connect(self.compare.emit)
        self._toolbar.export.connect(self.export.emit)
        self._toolbar.reset.connect(self.reset.emit)
        layout.addWidget(self._toolbar)

        # Content
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(16)

        self._intro = PageIntroWidget(
            "综合音频分析",
            "面向人声+音乐、视频音轨、节目成品与混合内容，结合 AudioBox Aesthetics 与信号分析给出综合判断。",
        )
        self._content_layout.addWidget(self._intro)

        # Drop zone (single file mode)
        self._drop_zone = DropZoneWidget()
        self._drop_zone.set_texts(
            "拖拽综合音频或视频文件到此处",
            "适用于人声+音乐、视频音轨、节目成品与混合内容，可点击选择文件",
            "WAV / FLAC / MP3 / AAC / OGG / M4A",
            "MP4 / MKV / AVI / MOV (自动提取音轨)",
        )
        self._drop_zone.set_directory_enabled(False)
        self._drop_zone.files_dropped.connect(self.files_dropped.emit)
        self._content_layout.addWidget(self._drop_zone)

        # Comparison mode: A/B drop zones
        self._compare_zone = QWidget()
        cmp_layout = QHBoxLayout(self._compare_zone)
        cmp_layout.setContentsMargins(0, 0, 0, 0)
        cmp_layout.setSpacing(16)

        from audioqas.ui.compare_drop_zone import CompareDropZoneWidget
        self._cmp_zone_a = CompareDropZoneWidget("A")
        self._cmp_zone_a.file_selected.connect(self.cmp_file_a_selected.emit)
        cmp_layout.addWidget(self._cmp_zone_a)

        self._cmp_zone_b = CompareDropZoneWidget("B")
        self._cmp_zone_b.file_selected.connect(self.cmp_file_b_selected.emit)
        cmp_layout.addWidget(self._cmp_zone_b)

        self._compare_zone.setVisible(False)
        self._content_layout.addWidget(self._compare_zone)

        self._cmp_file_a = None
        self._cmp_file_b = None

        # Results area (hidden initially)
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(24)
        self._results_widget.setVisible(False)

        # File info
        self._file_info = QLabel("")
        self._file_info.setStyleSheet(f"font-size: 15px; color: {txt_sec}")
        self._results_layout.addWidget(self._file_info)

        # AES scores section title
        self._aes_title = QLabel("AudioBox Aesthetics · AI 评分")
        self._aes_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {txt_ter}; letter-spacing: 1px")
        self._results_layout.addWidget(self._aes_title)

        # AES score cards row
        self._aes_row = QWidget()
        self._aes_layout = QHBoxLayout(self._aes_row)
        self._aes_layout.setContentsMargins(0, 0, 0, 0)
        self._aes_layout.setSpacing(20)
        self._aes_cards = {}
        self._aes_layout.addStretch()
        self._results_layout.addWidget(self._aes_row)

        # Signal metrics section title
        self._metrics_title = QLabel("信号分析 · 技术指标")
        self._metrics_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {txt_ter}; letter-spacing: 1px")
        self._results_layout.addWidget(self._metrics_title)

        # Metric cards row
        self._metrics_row = QWidget()
        self._metrics_layout = QHBoxLayout(self._metrics_row)
        self._metrics_layout.setContentsMargins(0, 0, 0, 0)
        self._metrics_layout.setSpacing(12)
        self._metric_cards = {}
        for name in ["LUFS", "LRA", "TruePeak", "Clipping", "THD"]:
            card = MetricCardWidget(METRIC_LABELS[name])
            self._metrics_layout.addWidget(card)
            self._metric_cards[name] = card
        self._metrics_layout.addStretch()
        self._results_layout.addWidget(self._metrics_row)

        # Comparison results (for A/B mode)
        self._comparison_widget = None

        self._results_layout.addStretch()
        self._content_layout.addWidget(self._results_widget)
        layout.addWidget(content, 1)

        self._aes_result = None
        self._analysis_result = None
        self._comparison_mode = False

    def progress_label(self):
        return self._toolbar.progress_label()

    def enter_comparison_mode(self):
        self._comparison_mode = True
        self._cmp_file_a = None
        self._cmp_file_b = None
        self._drop_zone.setVisible(False)
        self._results_widget.setVisible(False)
        self._compare_zone.setVisible(True)
        self._cmp_zone_a._file_path = None
        self._cmp_zone_a._file_label.setText("拖拽或点击选择文件 A")
        self._cmp_zone_b._file_path = None
        self._cmp_zone_b._file_label.setText("拖拽或点击选择文件 B")
        self._cmp_zone_a.update()
        self._cmp_zone_b.update()
        self.progress_label().setText("对比模式 · 请分别添加文件 A 和 B")

    def set_cmp_file_a(self, path):
        self._cmp_file_a = path

    def set_cmp_file_b(self, path):
        self._cmp_file_b = path

    def get_cmp_files(self):
        if self._cmp_file_a and self._cmp_file_b:
            return [self._cmp_file_a, self._cmp_file_b]
        return None

    def show_aes_result(self, result):
        self._aes_result = result
        model_id = result['model_name']
        name = os.path.basename(result['file_path'])
        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_ter = _color(t, "text", "tertiary")

        sr_text = f"{result['original_sr']}Hz"
        ch_text = "Mono" if result['original_channels'] == 1 else "Stereo → Mono"
        dur_text = f"{result['duration']:.1f}s"

        self._file_info.setText(
            f'<span style="color:{txt_primary};font-weight:600">{name}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:13px;color:{txt_ter};background:rgba(48,54,61,0.4);padding:4px 10px;border-radius:6px">{sr_text}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:13px;color:{txt_ter};background:rgba(48,54,61,0.4);padding:4px 10px;border-radius:6px">{ch_text}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:13px;color:{txt_ter};background:rgba(48,54,61,0.4);padding:4px 10px;border-radius:6px">{dur_text}</span>'
        )

        current_dims = list(result['dimensions'].keys())
        if list(self._aes_cards.keys()) != current_dims:
            while self._aes_layout.count():
                item = self._aes_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._aes_cards.clear()
            for dim in current_dims:
                card = ScoreCardWidget(dim, model_id=model_id)
                self._aes_layout.addWidget(card)
                self._aes_cards[dim] = card
            self._aes_layout.addStretch()

        from audioqas.core.dimensions import DimensionRegistry
        for dim, info in result['dimensions'].items():
            dim_label = DimensionRegistry.dimension_label(model_id, dim)
            label = f"{dim} · {dim_label}"
            desc = DimensionRegistry.dimension_description(model_id, dim, info['grade'])
            if not desc:
                desc = info['description']
            self._aes_cards[dim].set_score(info['score'], label, desc)

        self._drop_zone.setVisible(False)
        self._compare_zone.setVisible(False)
        self._results_widget.setVisible(True)

    def show_analysis_result(self, result):
        self._analysis_result = result
        for name, metric in result['metrics'].items():
            if name in self._metric_cards:
                self._metric_cards[name].set_metric(
                    metric['value'], metric['unit'],
                    metric['grade'], metric['description'],
                )
        self._results_widget.setVisible(True)

    def show_comparison(self, results_a, results_b):
        """Show side-by-side comparison for A/B analysis."""
        self._aes_result = results_a[0]
        self._analysis_result = None
        self._drop_zone.setVisible(False)
        self._compare_zone.setVisible(False)
        self._results_widget.setVisible(True)
        self._file_info.setVisible(False)
        self._aes_title.setVisible(False)
        self._aes_row.setVisible(False)
        self._metrics_title.setVisible(False)
        self._metrics_row.setVisible(False)

        # Remove old comparison widget
        if self._comparison_widget is not None:
            self._results_layout.removeWidget(self._comparison_widget)
            self._comparison_widget.deleteLater()

        from audioqas.ui.comparison import ComparisonWidget
        self._comparison_widget = ComparisonWidget(results_a[0], results_b[0])
        self._results_layout.insertWidget(0, self._comparison_widget)

    def clear(self):
        self._aes_result = None
        self._analysis_result = None
        self._comparison_mode = False
        self._cmp_file_a = None
        self._cmp_file_b = None
        self._drop_zone.setVisible(True)
        self._compare_zone.setVisible(False)
        self._results_widget.setVisible(False)
        self._toolbar.progress_label().setText("")
        self._file_info.setVisible(True)
        self._aes_title.setVisible(True)
        self._aes_row.setVisible(True)
        self._metrics_title.setVisible(True)
        self._metrics_row.setVisible(True)
        if self._comparison_widget is not None:
            self._results_layout.removeWidget(self._comparison_widget)
            self._comparison_widget.deleteLater()
            self._comparison_widget = None
        for card in self._aes_cards.values():
            card._score = 0.0
            card._number.setText("--")
        for card in self._metric_cards.values():
            card._number.setText("--")
            card._grade_label.setText("")
            card._desc_label.setText("")
