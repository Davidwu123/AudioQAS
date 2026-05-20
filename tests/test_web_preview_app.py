from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "design" / "web-preview.html"
APP_PATH = ROOT / "design" / "web-preview-app.js"


def test_web_preview_app_file_exists():
    assert APP_PATH.exists()
    text = APP_PATH.read_text(encoding="utf-8")
    assert "const state = {" in text
    assert "renderCompareSection" in text
    assert "render();" in text


def test_web_preview_app_tracks_single_file_runtime_state():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "single:" in text
    assert 'status: "idle"' in text
    assert "result: null" in text
    assert "error: null" in text


def test_web_preview_app_no_batch_upload_ui_path():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "createHiddenBatchInput" not in text
    assert "evaluateUploadedBatch" not in text
    assert "/api/evaluate/upload-batch" not in text


def test_web_preview_html_references_external_app_script():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'load(base + `/web-preview-data.js?v=${assetVersion}`)' in html
    assert 'load(base + `/web-preview-app.js?v=${assetVersion}`)' in html


def test_web_preview_html_uses_explicit_single_file_entry_labels():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-upload-trigger="eval:batch"' not in html
    assert 'data-upload-trigger="analysis:batch"' not in html
    assert "+ 添加文件" not in html
    assert 'data-upload-trigger="eval:single">单文件测评' in html
    assert 'data-scene-trigger="eval:compare"' in html
    assert "对比评测" in html
    assert 'data-upload-trigger="analysis:single">单文件分析' in html
    assert 'data-scene-trigger="analysis:compare"' in html
    assert "对比分析" in html


def test_web_preview_app_surfaces_render_errors():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "页面渲染失败" in text
    assert "error instanceof Error ? error.message : String(error)" in text


def test_web_preview_html_places_advice_inside_overview_summary():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-eval-advice' in html
    assert 'data-analysis-advice' in html
    assert 'data-eval-advice-block' in html
    assert 'data-analysis-advice-block' in html
    assert html.count('<div class="overview-item">\n                      <strong>处理建议</strong>') == 0


def test_web_preview_html_uses_left_heavier_overview_layout():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert "grid-template-columns:1.25fr .75fr;" in html


def test_web_preview_html_has_analysis_single_runtime_hooks():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-analysis-file-summary' in html
    assert 'data-analysis-trace' in html


def test_web_preview_html_has_single_file_detail_tables():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-single-detail-table="eval"' in html
    assert 'data-single-detail-table="analysis"' in html


def test_web_preview_html_has_history_runtime_hooks():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-history-stack' in html
    assert 'data-history-empty' in html


def test_web_preview_html_has_settings_runtime_hooks():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-setting-value="default-eval-model"' in html
    assert 'data-setting-value="default-analysis-model"' in html


def test_runtime_compare_render_uses_current_selected_base_group():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'const activeBaseKey = compareState.base || payload.base_key || "A";' in text
    assert "buildRuntimeCompareSummary(kind, items, compareState.mode, activeBaseKey)" in text
    assert 'summary.querySelector(".compare-summary-alt strong").textContent = compareSummary.altHeadline;' in text
    assert "vs ${activeBaseKey}" in text


def test_settings_trace_toggle_drives_result_and_history_visibility():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'document.querySelectorAll("[data-trace-block]")' in text
    assert 'document.querySelectorAll("[data-history-trace]")' in text
    assert 'if (key === "trace") settingsState.trace = toggle.classList.contains("on");' in text


def test_settings_compare_default_drives_compare_scene_mode():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'settingsState.compareDefault = settingsState.compareDefault === "free" ? "base" : "free";' in text
    assert 'if (state[`${kind}Scene`] === "compare") state.compare[kind].mode = settingsState.compareDefault;' in text


def test_history_runtime_handles_empty_and_error_states():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'const showEmpty = runtimeState.history.status === "success" && items.length === 0;' in text
    assert 'empty.textContent = `历史加载失败：${runtimeState.history.error}`;' in text
    assert 'stack.innerHTML = "";' in text
