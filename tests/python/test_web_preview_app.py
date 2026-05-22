from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "audioqas" / "web" / "static" / "web-preview.html"
APP_PATH = ROOT / "audioqas" / "web" / "static" / "web-preview-app.js"


def test_web_preview_app_file_exists():
    assert APP_PATH.exists()
    text = APP_PATH.read_text(encoding="utf-8")
    assert "const state = {" in text
    assert "renderCompareSection" in text
    assert "render();" in text


def test_web_preview_app_tracks_single_file_runtime_state():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "single:" in text
    assert 'status: "empty"' in text
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
    assert 'data-scene-trigger="eval:single"' in html
    assert 'data-single-btn="eval"' in html
    assert 'data-scene-trigger="eval:compare"' in html
    assert "对比评测" in html
    assert 'data-scene-trigger="analysis:single"' in html
    assert 'data-single-btn="analysis"' in html
    assert 'data-scene-trigger="analysis:compare"' in html
    assert "对比分析" in html


def test_web_preview_app_surfaces_render_errors():
    text = APP_PATH.read_text(encoding="utf-8")
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
    assert "status: {" in text
    assert 'eval: "empty"' in text
    assert 'analysis: "empty"' in text
    assert "error: {" in text


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


def test_app_has_state_branch_rendering_functions():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "function getSceneStatus(" in text
    assert "function getActiveSceneName(" in text
    assert "function renderStatePanels(" in text
    assert "function startCompareAction(" in text


def test_app_has_result_cache_and_key_helper():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "const resultCache = {};" in text
    assert "function getCacheKey(" in text


def test_app_no_remember_initial_markup():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "rememberInitialMarkup" not in text
    assert "initialMarkup" not in text


def test_app_compare_does_not_auto_trigger_on_upload():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "selected >= 2" not in text


def test_app_single_status_values_match_spec():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'status: "running"' in text
    assert 'status: "done"' in text
    assert 'status: "error"' in text
    assert 'status: "empty"' in text


def test_html_has_state_panels_and_compare_state_sub_panels():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-state-panel' in html
    assert 'data-compare-state' in html
    assert 'data-compare-start' in html
    assert 'data-compare-upload-group' in html


def test_html_empty_scene_is_default_active():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'class="scenario active" data-scene="empty"' in html


def test_app_single_upload_entry_uses_card_click():
    text = APP_PATH.read_text(encoding="utf-8")
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-single-upload-card="eval"' in html
    assert 'data-single-upload-card="analysis"' in html
    assert 'data-upload-trigger="eval:single"' not in html
    assert 'data-upload-trigger="analysis:single"' not in html
    assert 'data-upload-trigger="eval:single"' not in text
    assert 'data-upload-trigger="analysis:single"' not in text
    assert "[data-single-upload-card]" in text


def test_app_upload_with_progress_falls_back_to_fetch():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "function uploadWithProgress(" in text
    assert "XMLHttpRequest.prototype" in text
    assert "hasXHRProgress" in text
    assert "fetch(url, { method: \"POST\"" in text


def test_app_compare_upload_sets_ready_status():
    text = APP_PATH.read_text(encoding="utf-8")
    assert 'runtimeState.compare.status[kind] = "ready"' in text


def test_app_switch_model_caches_compare_context():
    text = APP_PATH.read_text(encoding="utf-8")
    assert "groups: runtimeState.compare.groups[scope]" in text
    assert "base: state.compare[scope].base" in text
    assert "requestId: runtimeState.requests[scope].compare" in text
    assert "cachedCompare.groups" in text
    assert "cachedCompare.base" in text
    assert "cachedCompare.requestId" in text


def test_html_has_error_banner_in_compare_done_panel():
    html = HTML_PATH.read_text(encoding="utf-8")
    assert 'data-error-banner="eval-compare"' in html
    assert 'data-error-banner="analysis-compare"' in html
