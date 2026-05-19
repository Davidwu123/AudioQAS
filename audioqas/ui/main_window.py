import os
import glob
import csv
import time

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QStackedWidget
from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QPainter, QColor

from audioqas.ui.theme import generate_qss, load_tokens, _color, score_description, score_grade
from audioqas.ui.sidebar import SidebarWidget
from audioqas.ui.drop_zone import DropZoneWidget
from audioqas.ui.score_card import ScoreCardWidget
from audioqas.ui.history_page import HistoryPageWidget
from audioqas.ui.settings_page import SettingsPageWidget
from audioqas.models.dnsmos import DNSMOSScorer
from audioqas.models.nisqa import NISQAScorer
from audioqas.models.audiobox_aesthetics import AudioBoxAestheticsScorer
from audioqas.models.analysis import AudioAnalyzer
from audioqas.ui.analysis_page import AnalysisPageWidget
from audioqas.ui.page_intro import PageIntroWidget
from audioqas.core.scorer import ScoringManager
from audioqas.core.history import HistoryManager
from audioqas.core.dimensions import DimensionRegistry


AUDIO_EXTS = {'.wav', '.flac', '.mp3', '.aac', '.ogg', '.m4a'}
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov'}


class ScoringWorker(QThread):
    progress = Signal(int, int, dict)
    finished = Signal(list, int)

    def __init__(self, mgr, files):
        super().__init__()
        self._mgr = mgr
        self._files = files

    def run(self):
        results = []
        total = len(self._files)
        start_ms = int(time.time() * 1000)
        for i, path in enumerate(self._files):
            result = self._mgr.score_file(path)
            results.append(result)
            self.progress.emit(i + 1, total, result)
        elapsed = int(time.time() * 1000) - start_ms
        self.finished.emit(results, elapsed)


class AnalysisWorker(QThread):
    progress_aes = Signal(int, int, dict)
    progress_analysis = Signal(int, int, dict)
    finished_aes = Signal(list, int)
    finished_analysis = Signal(dict)

    def __init__(self, aes_scorer, analyzer, files):
        super().__init__()
        self._aes_scorer = aes_scorer
        self._analyzer = analyzer
        self._files = files

    def run(self):
        # AES scoring
        aes_results = []
        total = len(self._files)
        start_ms = int(time.time() * 1000)
        for i, path in enumerate(self._files):
            result = self._aes_scorer.score(path)
            aes_results.append(result)
            self.progress_aes.emit(i + 1, total, result)
        elapsed = int(time.time() * 1000) - start_ms
        self.finished_aes.emit(aes_results, elapsed)

        # Signal analysis for first file
        if self._files:
            analysis_result = self._analyzer.analyze(self._files[0])
            self.finished_analysis.emit(analysis_result)


PAGE_INDEX = {"eval": 0, "analysis": 1, "history": 2, "settings": 3}


class EvalPageWidget(QWidget):
    def __init__(self, main_window: 'MainWindow'):
        super().__init__()
        self._main = main_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from audioqas.ui.toolbar import EvalToolbarWidget
        self._toolbar = EvalToolbarWidget()
        self._toolbar.add_file.connect(main_window._toolbar_add_file)
        self._toolbar.compare.connect(main_window._start_comparison)
        self._toolbar.export.connect(main_window._export_csv)
        self._toolbar.reset.connect(main_window._clear_results)
        layout.addWidget(self._toolbar)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 24)
        self._content_layout.setSpacing(16)

        self._intro = PageIntroWidget(
            "纯人声评测",
            "适用于通话、口播、会议、纯人声录音，支持人声质量评测与信号分析。",
        )
        self._content_layout.addWidget(self._intro)

        # Single-file mode: one drop zone
        self._drop_zone = DropZoneWidget()
        self._drop_zone.set_texts(
            "拖拽纯人声音频到此处",
            "适用于通话、口播、会议、纯人声录音",
            "WAV / FLAC / MP3 / AAC / OGG / M4A",
            "MP4 / MKV / AVI / MOV (如为纯人声视频可自动提取音轨)",
        )
        self._drop_zone.files_dropped.connect(main_window._on_files)
        self._drop_zone.dir_selected.connect(main_window._on_dir)
        self._content_layout.addWidget(self._drop_zone)

        # Comparison mode: two drop zones side by side
        self._compare_zone = QWidget()
        cmp_layout = QHBoxLayout(self._compare_zone)
        cmp_layout.setContentsMargins(0, 0, 0, 0)
        cmp_layout.setSpacing(16)

        from audioqas.ui.compare_drop_zone import CompareDropZoneWidget
        self._cmp_zone_a = CompareDropZoneWidget("A")
        self._cmp_zone_a.file_selected.connect(main_window._on_cmp_file_a)
        cmp_layout.addWidget(self._cmp_zone_a)

        self._cmp_zone_b = CompareDropZoneWidget("B")
        self._cmp_zone_b.file_selected.connect(main_window._on_cmp_file_b)
        cmp_layout.addWidget(self._cmp_zone_b)

        self._compare_zone.setVisible(False)
        self._content_layout.addWidget(self._compare_zone)

        self._results_data = []
        self._batch_widget = None

        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")

        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(16)
        self._results_widget.setVisible(False)

        self._detail_area = QWidget()
        detail_layout = QVBoxLayout(self._detail_area)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(24)

        self._file_info = QLabel("")
        self._file_info.setStyleSheet(f"font-size: 15px; color: {txt_sec}")
        detail_layout.addWidget(self._file_info)

        self._cards_row = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_row)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(20)
        self._cards = {}

        self._cards_layout.addStretch()
        detail_layout.addWidget(self._cards_row)
        self._results_layout.addWidget(self._detail_area)
        self._results_layout.addStretch()

        self._content_layout.addWidget(self._results_widget)
        layout.addWidget(content, 1)

    def progress_label(self):
        return self._toolbar.progress_label()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AudioQAS")
        self.setMinimumSize(QSize(800, 600))

        qss = generate_qss()
        self.setStyleSheet(qss)

        central = QWidget()
        self.setCentralWidget(central)
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self._sidebar = SidebarWidget()
        self._sidebar.page_changed.connect(self._switch_page)
        self._sidebar.model_changed.connect(self._on_model_change)
        central_layout.addWidget(self._sidebar)

        self._scoring_mgr = ScoringManager()
        self._scoring_mgr.register(DNSMOSScorer())
        try:
            self._scoring_mgr.register(NISQAScorer())
        except Exception:
            pass
        self._aes_scorer = AudioBoxAestheticsScorer()
        self._analyzer = AudioAnalyzer()
        self._worker = None
        self._analysis_worker = None
        self._results = []
        self._history_mgr = HistoryManager()
        self._cmp_files = None
        self._cmp_file_a = None
        self._cmp_file_b = None

        self._stacked = QStackedWidget()
        central_layout.addWidget(self._stacked, 1)

        self._eval_page = EvalPageWidget(self)
        self._analysis_page = AnalysisPageWidget()
        self._analysis_page.add_file.connect(self._on_analysis_add_file)
        self._analysis_page.compare.connect(self._on_analysis_compare)
        self._analysis_page.export.connect(self._on_analysis_export)
        self._analysis_page.reset.connect(self._on_analysis_reset)
        self._analysis_page.files_dropped.connect(self._on_analysis_files_dropped)
        self._analysis_page.cmp_file_a_selected.connect(self._on_analysis_cmp_file_a)
        self._analysis_page.cmp_file_b_selected.connect(self._on_analysis_cmp_file_b)
        self._history_page = HistoryPageWidget()
        self._settings_page = SettingsPageWidget()

        self._stacked.addWidget(self._eval_page)
        self._stacked.addWidget(self._analysis_page)
        self._stacked.addWidget(self._history_page)
        self._stacked.addWidget(self._settings_page)

        # Default to audio analysis page
        self._stacked.setCurrentIndex(1)
        self._sidebar.set_active_page("analysis")

        self._start_time_ms = 0

    def _switch_page(self, page_id):
        idx = PAGE_INDEX.get(page_id, 0)
        self._stacked.setCurrentIndex(idx)
        self._sidebar.set_active_page(page_id)
        if page_id == "history":
            self._history_page._refresh()

    def _on_model_change(self, model_id):
        upper_id = model_id.upper()
        if upper_id in self._scoring_mgr.available_models():
            self._scoring_mgr.set_active_model(upper_id)
        else:
            available = self._scoring_mgr.available_models()
            QMessageBox.information(
                self, "模型未安装",
                f"{model_id.upper()} 模型尚未实现，当前可用：{', '.join(available)}"
            )
            self._sidebar._current_model_id = self._scoring_mgr._active_model
            for item in self._sidebar._model_items:
                item.set_selected(item._model["id"] == self._scoring_mgr._active_model)

    def _on_analysis_add_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频/视频文件", "",
            "Audio/Video (*.wav *.flac *.mp3 *.aac *.ogg *.m4a *.mp4 *.mkv *.avi *.mov);;All (*)"
        )
        valid = [f for f in files if os.path.splitext(f)[1].lower() in AUDIO_EXTS | VIDEO_EXTS]
        if valid:
            self._start_analysis(valid)

    def _start_analysis(self, files):
        ap = self._analysis_page
        ap._drop_zone.setVisible(False)
        ap._results_widget.setVisible(True)
        ap.progress_label().setText(f"分析中 · AudioBox · 0/{len(files)}")
        self._analysis_worker = AnalysisWorker(self._aes_scorer, self._analyzer, files)
        self._analysis_worker.progress_aes.connect(self._on_aes_progress)
        self._analysis_worker.finished_aes.connect(self._on_aes_finished)
        self._analysis_worker.finished_analysis.connect(self._on_analysis_finished)
        self._analysis_worker.start()

    def _on_aes_progress(self, done, total, result):
        ap = self._analysis_page
        name = os.path.basename(result['file_path'])
        ap.progress_label().setText(f"分析中 · AudioBox Aesthetics · {done}/{total} · {name}")

    def _on_aes_finished(self, results, elapsed_ms):
        if not results:
            return
        elapsed_s = elapsed_ms / 1000.0
        ap = self._analysis_page
        ap.progress_label().setText(f"AI评分完成 · {elapsed_s:.1f}s · 信号分析进行中...")
        ap.show_aes_result(results[0])
        self._show_analysis_toast(f"AudioBox Aesthetics 评分完成 · {len(results)} 文件 · {elapsed_s:.1f}s")

    def _on_analysis_finished(self, result):
        ap = self._analysis_page
        ap.show_analysis_result(result)
        ap.progress_label().setText("分析完成")
        self._show_analysis_toast("分析完成")

    def _show_analysis_toast(self, message: str):
        ap = self._analysis_page
        t = load_tokens()
        overlay = _color(t, "base", "overlay")
        accent = _color(t, "accent", "primary")

        toast = QLabel(message)
        toast.setStyleSheet(f"""
            background: {overlay};
            color: {accent};
            font-size: 13px;
            padding: 10px 20px;
            border-radius: 10px;
            border: 1px solid rgba(88,166,255,0.3);
        """)
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()

        from PySide6.QtCore import QTimer
        ap._content_layout.addWidget(toast)
        QTimer.singleShot(3000, lambda: (ap._content_layout.removeWidget(toast), toast.deleteLater()))

    def _on_analysis_compare(self):
        self._analysis_page.enter_comparison_mode()

    def _on_analysis_cmp_file_a(self, path):
        self._cmp_file_a = path
        if self._cmp_file_b:
            self._run_analysis_comparison()

    def _on_analysis_cmp_file_b(self, path):
        self._cmp_file_b = path
        if self._cmp_file_a:
            self._run_analysis_comparison()

    def _on_analysis_files_dropped(self, paths):
        valid = [p for p in paths if os.path.splitext(p)[1].lower() in AUDIO_EXTS | VIDEO_EXTS]
        if valid:
            self._start_analysis(valid)

    def _run_analysis_comparison(self):
        files = [self._cmp_file_a, self._cmp_file_b]
        ap = self._analysis_page
        ap._compare_zone.setVisible(False)
        ap._results_widget.setVisible(True)
        ap.progress_label().setText(f"对比分析中 · AudioBox Aesthetics · 0/2")
        self._analysis_worker = AnalysisWorker(self._aes_scorer, self._analyzer, files)
        self._analysis_worker.progress_aes.connect(self._on_aes_cmp_progress)
        self._analysis_worker.finished_aes.connect(self._on_aes_cmp_finished)
        self._analysis_worker.finished_analysis.connect(self._on_analysis_cmp_analysis)
        self._analysis_worker.start()

    def _on_aes_cmp_progress(self, done, total, result):
        ap = self._analysis_page
        name = os.path.basename(result['file_path'])
        ap.progress_label().setText(f"对比分析中 · AudioBox Aesthetics · {done}/{total} · {name}")

    def _on_aes_cmp_finished(self, results, elapsed_ms):
        if not results or len(results) < 2:
            self._analysis_page.progress_label().setText("对比分析失败")
            return
        elapsed_s = elapsed_ms / 1000.0
        ap = self._analysis_page
        ap.progress_label().setText(f"AI评分完成 · {elapsed_s:.1f}s · 信号分析进行中...")
        ap.show_comparison([results[0]], [results[1]])
        self._show_analysis_toast(f"对比分析完成 · {elapsed_s:.1f}s")

    def _on_analysis_cmp_analysis(self, result):
        # In comparison mode, signal analysis is for first file only - skip individual display
        self._analysis_page.progress_label().setText("对比分析完成")

    def _on_analysis_export(self):
        if not self._analysis_page._aes_result:
            QMessageBox.information(self, "提示", "没有可导出的分析结果")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", "analysis_results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        aes_result = self._analysis_page._aes_result
        analysis_result = self._analysis_page._analysis_result
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # AES scores header
            header = ["文件名", "时长(s)", "原始采样率", "原始声道数"]
            for dim in aes_result['dimensions'].keys():
                header.extend([f"{dim}分数", f"{dim}等级", f"{dim}描述"])
            if analysis_result:
                for name in analysis_result['metrics'].keys():
                    header.extend([f"{name}值", f"{name}等级"])
            writer.writerow(header)

            row = [os.path.basename(aes_result['file_path']),
                   f"{aes_result['duration']:.1f}",
                   aes_result['original_sr'],
                   aes_result['original_channels']]
            for dim, info in aes_result['dimensions'].items():
                row.extend([f"{info['score']:.2f}", info['grade'], info['description']])
            if analysis_result:
                for name, metric in analysis_result['metrics'].items():
                    row.extend([f"{metric['value']:.2f} {metric['unit']}", metric['grade']])
            writer.writerow(row)
        QMessageBox.information(self, "导出成功", f"已导出到\n{path}")

    def _on_analysis_reset(self):
        self._analysis_page.clear()
        self._cmp_file_a = None
        self._cmp_file_b = None

    def _on_files(self, paths):
        valid = [p for p in paths if os.path.splitext(p)[1].lower() in AUDIO_EXTS | VIDEO_EXTS]
        if valid:
            self._start_scoring(valid)
        elif paths:
            skipped = [os.path.basename(p) for p in paths if os.path.splitext(p)[1].lower() not in AUDIO_EXTS | VIDEO_EXTS]
            msg = f"不支持的格式：{', '.join(skipped[:5])}"
            if len(skipped) > 5:
                msg += f" 等 {len(skipped)} 个文件"
            self._show_toast(msg)

    def _on_dir(self, dir_path):
        files = []
        for ext in AUDIO_EXTS | VIDEO_EXTS:
            files.extend(glob.glob(os.path.join(dir_path, f'*{ext}')))
        if files:
            self._start_scoring(sorted(files))
        else:
            self._show_toast(f"目录中没有支持的音频/视频文件")

    def _show_toast(self, message: str):
        ep = self._eval_page
        t = load_tokens()
        txt_sec = _color(t, "text", "secondary")
        overlay = _color(t, "base", "overlay")
        accent = _color(t, "accent", "primary")

        toast = QLabel(message)
        toast.setStyleSheet(f"""
            background: {overlay};
            color: {accent};
            font-size: 13px;
            padding: 10px 20px;
            border-radius: 10px;
            border: 1px solid rgba(88,166,255,0.3);
        """)
        toast.setAlignment(Qt.AlignCenter)
        toast.adjustSize()

        from PySide6.QtCore import QTimer
        ep._content_layout.addWidget(toast)
        QTimer.singleShot(3000, lambda: (ep._content_layout.removeWidget(toast), toast.deleteLater()))

    def _start_scoring(self, files, comparison=False):
        ep = self._eval_page
        if not comparison:
            self._cmp_files = None
            ep._drop_zone.setVisible(False)
            ep._compare_zone.setVisible(False)
        ep._results_widget.setVisible(True)
        ep._file_info.setText("")
        for card in ep._cards.values():
            card._score = 0.0
            card._number.setText("--")
        if ep._batch_widget is not None:
            ep._results_layout.removeWidget(ep._batch_widget)
            ep._batch_widget.deleteLater()
            ep._batch_widget = None
        model = self._scoring_mgr._active_model or "DNSMOS"
        ep.progress_label().setText(f"评分中 · {model} · 0/{len(files)}")
        self._start_time_ms = int(time.time() * 1000)
        self._worker = ScoringWorker(self._scoring_mgr, files)
        self._worker.progress.connect(self._on_score_progress)
        self._worker.finished.connect(self._on_score_finished)
        self._worker.start()

    def _on_score_progress(self, done, total, result):
        ep = self._eval_page
        model = result['model_name']
        name = os.path.basename(result['file_path'])
        ep.progress_label().setText(f"评分中 · {model} · {done}/{total} · {name}")
        if done == 1 and not self._cmp_files:
            self._show_single_result(result)

    def _on_score_finished(self, results, elapsed_ms):
        if not results:
            return
        self._results = results
        ep = self._eval_page
        ep._results_data = results
        elapsed_s = elapsed_ms / 1000.0
        model = results[0]['model_name']

        if self._cmp_files:
            ep.progress_label().setText(f"对比完成 · {model} · {elapsed_s:.1f}s")
            ep._file_info.setVisible(False)
            self._show_comparison_view(results)
        else:
            ep.progress_label().setText(f"评分完成 · {model} · {len(results)} 文件 · {elapsed_s:.1f}s")
            self._show_single_result(results[0])
            if len(results) > 1:
                self._show_batch_view(results)
            self._show_toast(f"评分完成 · {len(results)} 文件 · {elapsed_s:.1f}s")

        self._history_mgr.save_evaluation(results, elapsed_ms)

    def _show_single_result(self, result):
        ep = self._eval_page
        model_id = result['model_name']
        name = os.path.basename(result['file_path'])
        t = load_tokens()
        txt_primary = _color(t, "text", "primary")
        txt_ter = _color(t, "text", "tertiary")
        txt_sec = _color(t, "text", "secondary")

        sr_text = f"{result['original_sr']}Hz"
        preprocess_tag = ""
        if result['preprocessed']:
            target_sr = "16kHz" if model_id == "DNSMOS" else "48kHz"
            sr_text += f" → {target_sr}"
            pp_path = result.get('preprocessed_path', '')
            pp_name = os.path.basename(pp_path) if pp_path else ''
            if pp_name:
                preprocess_tag = f'&nbsp;&nbsp;<span style="font-size:12px;color:{txt_sec};background:rgba(88,166,255,0.1);padding:4px 10px;border-radius:6px">预处理: {pp_name}</span>'
        ch_text = "Mono" if result['original_channels'] == 1 else "Stereo → Mono"
        dur_text = f"{result['duration']:.1f}s"

        ep._file_info.setText(
            f'<span style="color:{txt_primary};font-weight:600">{name}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:13px;color:{txt_ter};background:rgba(48,54,61,0.4);padding:4px 10px;border-radius:6px">{sr_text}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:13px;color:{txt_ter};background:rgba(48,54,61,0.4);padding:4px 10px;border-radius:6px">{ch_text}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size:13px;color:{txt_ter};background:rgba(48,54,61,0.4);padding:4px 10px;border-radius:6px">{dur_text}</span>'
            f'{preprocess_tag}'
        )

        # Rebuild cards if dimensions changed
        current_dims = list(result['dimensions'].keys())
        if list(ep._cards.keys()) != current_dims:
            while ep._cards_layout.count():
                item = ep._cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            ep._cards.clear()
            for dim in current_dims:
                card = ScoreCardWidget(dim, model_id=model_id)
                ep._cards_layout.addWidget(card)
                ep._cards[dim] = card
            ep._cards_layout.addStretch()

        for dim, info in result['dimensions'].items():
            dim_label = DimensionRegistry.dimension_label(model_id, dim)
            label = f"{dim} · {dim_label}"
            desc = DimensionRegistry.dimension_description(model_id, dim, info['grade'])
            if not desc:
                desc = info['description']
            ep._cards[dim].set_score(info['score'], label, desc)

    def _show_batch_view(self, results):
        ep = self._eval_page
        stretch_item = ep._results_layout.takeAt(ep._results_layout.count() - 1)

        if ep._batch_widget is not None:
            ep._results_layout.removeWidget(ep._batch_widget)
            ep._batch_widget.deleteLater()

        try:
            from audioqas.ui.batch_table import BatchResultWidget
            ep._batch_widget = BatchResultWidget(results)
            ep._batch_widget.row_clicked.connect(self._on_batch_row_clicked)
            ep._results_layout.addWidget(ep._batch_widget)
        except ImportError:
            pass

        ep._results_layout.addStretch()

    def _show_comparison_view(self, results):
        ep = self._eval_page
        stretch_item = ep._results_layout.takeAt(ep._results_layout.count() - 1)

        if ep._batch_widget is not None:
            ep._results_layout.removeWidget(ep._batch_widget)
            ep._batch_widget.deleteLater()

        from audioqas.ui.comparison import ComparisonWidget
        ep._batch_widget = ComparisonWidget(results[0], results[1])
        ep._results_layout.addWidget(ep._batch_widget)
        ep._results_layout.addStretch()

    def _on_batch_row_clicked(self, result):
        self._show_single_result(result)

    def _clear_results(self):
        ep = self._eval_page
        ep._drop_zone.setVisible(True)
        ep._compare_zone.setVisible(False)
        ep._results_widget.setVisible(False)
        ep.progress_label().setText("")
        ep._results_data = []
        self._results = []
        self._cmp_files = None
        self._cmp_file_a = None
        self._cmp_file_b = None
        for card in ep._cards.values():
            card._score = 0.0
            card._number.setText("--")
        if ep._batch_widget is not None:
            ep._results_layout.removeWidget(ep._batch_widget)
            ep._batch_widget.deleteLater()
            ep._batch_widget = None

    def _toolbar_add_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择音频/视频文件", "",
            "Audio/Video (*.wav *.flac *.mp3 *.aac *.ogg *.m4a *.mp4 *.mkv *.avi *.mov);;All (*)"
        )
        valid = [f for f in files if os.path.splitext(f)[1].lower() in AUDIO_EXTS | VIDEO_EXTS]
        if valid:
            self._start_scoring(valid)

    def _start_comparison(self):
        ep = self._eval_page
        self._cmp_files = None
        ep._drop_zone.setVisible(False)
        ep._compare_zone.setVisible(True)
        ep._results_widget.setVisible(False)
        ep._cmp_zone_a._file_path = None
        ep._cmp_zone_a._file_label.setText("拖拽或点击选择文件")
        ep._cmp_zone_b._file_path = None
        ep._cmp_zone_b._file_label.setText("拖拽或点击选择文件")
        ep._cmp_zone_a.update()
        ep._cmp_zone_b.update()
        ep.progress_label().setText("对比模式 · 请分别添加文件 A 和 B")

    def _on_cmp_file_a(self, path):
        self._cmp_file_a = path
        if hasattr(self, '_cmp_file_b') and self._cmp_file_b:
            self._run_comparison()

    def _on_cmp_file_b(self, path):
        self._cmp_file_b = path
        if hasattr(self, '_cmp_file_a') and self._cmp_file_a:
            self._run_comparison()

    def _run_comparison(self):
        self._cmp_files = [self._cmp_file_a, self._cmp_file_b]
        ep = self._eval_page
        ep._compare_zone.setVisible(False)
        ep._results_widget.setVisible(True)
        ep._detail_area.setVisible(True)
        ep._file_info.setVisible(True)
        ep._file_info.setText("正在评分对比文件...")
        model = self._scoring_mgr._active_model or "DNSMOS"
        ep.progress_label().setText(f"对比评分中 · {model} · 0/2")
        self._start_time_ms = int(time.time() * 1000)
        self._worker = ScoringWorker(self._scoring_mgr, self._cmp_files)
        self._worker.progress.connect(self._on_cmp_progress)
        self._worker.finished.connect(self._on_cmp_finished)
        self._worker.start()

    def _on_cmp_progress(self, done, total, result):
        ep = self._eval_page
        name = os.path.basename(result['file_path'])
        model = result['model_name']
        ep.progress_label().setText(f"对比评分中 · {model} · {done}/{total} · {name}")
        ep._file_info.setText(f"已完成 {done}/{total}：{name}")

    def _on_cmp_finished(self, results, elapsed_ms):
        if not results or len(results) < 2:
            ep = self._eval_page
            ep.progress_label().setText("对比评分失败")
            ep._file_info.setText("评分出错，请检查文件格式")
            return

        self._results = results
        ep = self._eval_page
        ep._results_data = results
        elapsed_s = elapsed_ms / 1000.0
        model = results[0]['model_name']
        ep.progress_label().setText(f"对比完成 · {model} · {elapsed_s:.1f}s")
        ep._file_info.setVisible(False)
        self._show_comparison_view(results)
        self._show_toast(f"对比评测完成 · {elapsed_s:.1f}s")

        self._history_mgr.save_evaluation(results, elapsed_ms)

    def _export_csv(self):
        if not self._results:
            QMessageBox.information(self, "提示", "没有可导出的评分结果")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出CSV", "mos_results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        model_id = self._results[0]['model_name']
        dim_names = list(self._results[0]['dimensions'].keys())
        header = ["文件名", "时长(s)", "原始采样率", "原始声道数", "预处理"]
        for dim in dim_names:
            header.extend([f"{dim}分数", f"{dim}等级", f"{dim}描述"])
        header.append("模型")

        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for r in self._results:
                dims = r['dimensions']
                row = [
                    os.path.basename(r['file_path']),
                    f"{r['duration']:.1f}",
                    r['original_sr'],
                    r['original_channels'],
                    "是" if r['preprocessed'] else "否",
                ]
                for dim in dim_names:
                    info = dims[dim]
                    row.extend([
                        f"{info['score']:.2f}", info['grade'], info['description'],
                    ])
                row.append(f"{r['model_name']} {r['model_version']}")
                writer.writerow(row)
        QMessageBox.information(self, "导出成功", f"已导出 {len(self._results)} 条结果到\n{path}")
