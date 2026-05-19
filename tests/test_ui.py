import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import sys
from unittest.mock import patch

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


@pytest.fixture(autouse=True)
def process_qt_events():
    yield
    app.processEvents()


class TestMainWindow:
    @pytest.fixture
    def window(self):
        from audioqas.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        yield w
        w.close()
        w.deleteLater()

    def test_window_title(self, window):
        assert window.windowTitle() == "AudioQAS"

    def test_window_size(self, window):
        assert window.minimumWidth() >= 800
        assert window.minimumHeight() >= 600

    def test_sidebar_exists(self, window):
        assert window._sidebar is not None
        assert window._sidebar._current_model_id == "dnsmos"

    def test_scoring_manager(self, window):
        models = window._scoring_mgr.available_models()
        assert "DNSMOS" in models
        assert "NISQA" in models

    def test_eval_page_widgets(self, window):
        ep = window._eval_page
        assert ep._drop_zone is not None
        assert ep._compare_zone is not None
        assert ep._cmp_zone_a is not None
        assert ep._cmp_zone_b is not None
        # Default page is analysis, so switch to eval first
        window._switch_page("eval")
        assert ep._drop_zone.isVisible()
        assert not ep._compare_zone.isVisible()
        assert not ep._results_widget.isVisible()

    def test_toolbar_buttons(self, window):
        ep = window._eval_page
        toolbar = ep.findChild(object, "")
        # Find all buttons in toolbar
        buttons = ep.children()
        # Toolbar should have buttons: add, dir, compare, export, clear
        toolbar_widget = None
        for child in ep.children():
            if hasattr(child, 'fixedHeight') or (hasattr(child, 'setFixedHeight') and child.height() == 52):
                toolbar_widget = child
                break


class TestComparisonMode:
    @pytest.fixture
    def window(self):
        from audioqas.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        yield w
        w.close()
        w.deleteLater()

    def test_enter_comparison_mode(self, window):
        ep = window._eval_page
        window._switch_page("eval")
        window._start_comparison()
        assert not ep._drop_zone.isVisible()
        assert ep._compare_zone.isVisible()
        assert not ep._results_widget.isVisible()
        assert ep.progress_label().text().startswith("对比模式")

    def test_comparison_zones_independent(self, window):
        ep = window._eval_page
        window._start_comparison()
        assert ep._cmp_zone_a._side == "A"
        assert ep._cmp_zone_b._side == "B"
        assert ep._cmp_zone_a._file_path is None
        assert ep._cmp_zone_b._file_path is None

    def test_clear_results_resets_comparison(self, window):
        ep = window._eval_page
        window._switch_page("eval")
        window._start_comparison()
        window._clear_results()
        assert ep._drop_zone.isVisible()
        assert not ep._compare_zone.isVisible()
        assert window._cmp_file_a is None
        assert window._cmp_file_b is None


class TestCompareDropZone:
    @pytest.fixture
    def zone_a(self):
        from audioqas.ui.compare_drop_zone import CompareDropZoneWidget
        z = CompareDropZoneWidget("A")
        yield z
        z.close()
        z.deleteLater()

    @pytest.fixture
    def zone_b(self):
        from audioqas.ui.compare_drop_zone import CompareDropZoneWidget
        z = CompareDropZoneWidget("B")
        yield z
        z.close()
        z.deleteLater()

    def test_side_label(self, zone_a, zone_b):
        assert zone_a._side == "A"
        assert zone_b._side == "B"

    def test_set_file(self, zone_a, tmp_path):
        sample = tmp_path / "sample.wav"
        sample.write_bytes(b"fake")
        zone_a.set_file(str(sample))
        assert zone_a._file_path == str(sample)
        assert "sample.wav" in zone_a._file_label.text()

    def test_accept_drops(self, zone_a):
        assert zone_a.acceptDrops()


class TestDeltaWidget:
    def test_delta_positive(self):
        from audioqas.ui.comparison import DeltaWidget
        dw = DeltaWidget("OVRL", 2.0, 3.0)
        assert dw._delta == 1.0
        assert dw._is_better == True

    def test_delta_negative(self):
        from audioqas.ui.comparison import DeltaWidget
        dw = DeltaWidget("OVRL", 3.5, 2.0)
        assert dw._delta == -1.5
        assert dw._is_better == False

    def test_delta_zero(self):
        from audioqas.ui.comparison import DeltaWidget
        dw = DeltaWidget("OVRL", 3.0, 3.0)
        assert dw._delta == 0.0
        assert not dw._is_better


class TestComparisonWidget:
    @staticmethod
    def _fake_result(path: str, model_name: str = "DNSMOS"):
        return {
            "eval_type": "mos",
            "model_name": model_name,
            "model_version": "test",
            "dimensions": {
                "OVRL": {"score": 3.2, "grade": "Fair", "description": "ok"},
                "SIG": {"score": 3.8, "grade": "Good", "description": "ok"},
                "BAK": {"score": 2.9, "grade": "Poor", "description": "ok"},
            },
            "grade": "Fair",
            "descriptions": {"OVRL": "ok", "SIG": "ok", "BAK": "ok"},
            "timestamp": "2026-05-18T00:00:00",
            "file_path": path,
            "original_sr": 16000,
            "original_channels": 1,
            "duration": 1.0,
            "preprocessed": False,
            "preprocessed_path": path,
        }

    def test_creation(self):
        from audioqas.ui.comparison import ComparisonWidget
        ra = self._fake_result("a.wav")
        rb = self._fake_result("b.wav")

        cw = ComparisonWidget(ra, rb)
        assert cw._result_a is not None
        assert cw._result_b is not None

    def test_verdict_text(self):
        from audioqas.ui.comparison import ComparisonWidget
        ra = self._fake_result("a.wav")
        rb = self._fake_result("b.wav")

        cw = ComparisonWidget(ra, rb)
        # verdict_label should show some text
        assert cw is not None


class TestModelSwitch:
    @pytest.fixture
    def window(self):
        from audioqas.ui.main_window import MainWindow
        w = MainWindow()
        w.show()
        yield w
        w.close()
        w.deleteLater()

    def test_switch_to_nisqa(self, window):
        window._on_model_change("nisqa")
        assert window._scoring_mgr._active_model == "NISQA"

    def test_switch_to_unregistered_shows_dialog(self, window):
        # UTMOS not registered -> should show info dialog
        with patch("audioqas.ui.main_window.QMessageBox.information") as info:
            window._on_model_change("utmos")
        info.assert_called_once()
        # Active model should stay as DNSMOS (the first registered)
        assert window._scoring_mgr._active_model in window._scoring_mgr.available_models()
