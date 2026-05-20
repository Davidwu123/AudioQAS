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
    assert "buildCompareSummaryViewModel(kind, compareState.mode, activeBaseGroup, sorted[0], best, compareSummary)" in text
    assert "buildCompareRankingViewModel(kind, displaySorted, compareState.mode, activeBaseKey)" in text
    assert "buildCompareTableViewModel(kind, displayItems, view, compareState.mode, state.models, activeBaseKey)" in text
    assert "applyCompareSummary(summary, summaryView, compareState.mode);" in text


def test_settings_trace_toggle_drives_result_and_history_visibility():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'document.querySelectorAll("[data-trace-block]")' in text
    assert 'document.querySelectorAll("[data-history-trace]")' in text
    assert "function toggleSettingAction(" in text
    assert 'if (key === "trace") runtimeState.settings.trace = isOn;' in text


def test_settings_compare_default_drives_compare_scene_mode():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'runtimeState.settings.compareDefault = runtimeState.settings.compareDefault === "free" ? "base" : "free";' in text
    assert 'if (state[`${kind}Scene`] === "compare") state.compare[kind].mode = runtimeState.settings.compareDefault;' in text


def test_history_runtime_handles_empty_and_error_states():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'const showEmpty = runtimeState.history.status === "success" && items.length === 0;' in text
    assert 'empty.textContent = `历史加载失败：${runtimeState.history.error}`;' in text
    assert 'stack.innerHTML = "";' in text


def test_runtime_result_styles_follow_preview_status_semantics():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "const view = buildSingleFileViewModel(page, payload, fileName);" in text
    assert "heroGrade.setAttribute(\"style\", view.hero.gradeStyle);" in text
    assert "<div class=\"bar\"><span style=\"${card.barStyle}\"></span></div>" in text
    assert 'background:var(--accent)' not in text


def test_single_runtime_render_uses_shared_dom_helper():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "function applySingleOverview(" in text
    assert "function applySingleMetricCards(" in text
    assert "function applySingleDetailTable(" in text
    assert text.count("const title = document.querySelector(") <= 1


def test_app_layer_continues_shedding_display_semantics():
    text = APP_PATH.read_text(encoding="utf-8")
    assert text.count("模型: ") <= 2
    assert text.count("自由对比") <= 2
    assert text.count("基准对比") <= 2


def test_runtime_state_has_explicit_compare_slice():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "compare: {" in text
    assert "groups:" in text
    assert "results:" in text


def test_runtime_state_has_explicit_settings_slice():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "settings: {" in text
    assert "trace:" in text
    assert "compareDefault:" in text


def test_event_layer_uses_action_helpers_for_settings_and_history():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "function applySettingsPayload(" in text
    assert "function openSingleUploadAction(" in text
    assert "function changeSceneAction(" in text
    assert "function changeCompareModeAction(" in text
    assert "function toggleSettingAction(" in text
    assert "function updateCompareDefaultAction(" in text
    assert "function updateExportFormatAction(" in text
    assert "function updateHistoryRetentionAction(" in text
    assert "function applyHistoryFilterAction(" in text
    assert "function showHistoryDetailAction(" in text
    assert "function exportPageAction(" in text
    assert "function resetPageAction(" in text
    assert "function switchModelAction(" in text
    assert "function toggleDefaultEvalModelAction(" in text
    assert "function changeCompareDetailViewAction(" in text
    assert "function changeSingleDetailViewAction(" in text
    assert "function addCompareGroupAction(" in text


def test_compact_five_model_cards_keep_stronger_visual_weight_than_signal_cards():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert ".four-col.compact-five .number{" in html
    assert "font-size:38px;" in html
    assert "grid-template-columns:repeat(5, minmax(0,1fr));" in html
